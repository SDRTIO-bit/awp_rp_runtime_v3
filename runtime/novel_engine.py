"""NovelEngine — Novel chapter generation engine.

Independent from PersistentTurnEngine, shares infrastructure (LLM adapters, storage, contracts).
"""

from __future__ import annotations

from typing import Any, Callable

from ..contracts.novel_project import NovelProject
from ..contracts.novel_volume import VolumePlan
from ..contracts.novel_chapter import ChapterPlan, BeatDetail
from ..contracts.novel_draft import ChapterDraft
from ..contracts.novel_ledger import LedgerItem
from ..contracts.novel_director_guidance import DirectorGuidance
from ..contracts.novel_write_packet import NovelWritePacket
from ..contracts.memory_recall_request import MemoryRecallRequest
from .session_runtime_registry import SessionRuntimeStoreRegistry
from .novel_write_packet_builder import NovelWritePacketBuilder
from .novel_quality_pipeline import NovelQualityPipeline
from .active_memory_recall_runtime import ActiveMemoryRecallRuntime
from .rag_recall_runtime import RagMemoryRecallRuntime
from .novel_evolution_curator import novel_memory_scope


class NovelEngine:
    """小说章节生成引擎。独立于 PersistentTurnEngine，共享底层基础设施。

    共享的基础设施：
    - SessionRuntimeStoreRegistry（存储层）
    - RuntimeStoreFactory（工厂）
    - DeepSeekAdapter（LLM 调用）
    - ModelProfileRegistry（profile 管理）
    - QualityIssue / QualityDecision（质量契约）

    不共享的：
    - PersistentTurnEngine（RP 专用单体引擎）
    - QualityPipelineRuntime（RP 专用门控逻辑）
    - WriterInputBundleV2Builder（RP 专用 bundle 构建）
    - SubAgentLLMRunner（RP 的 thinking 被硬编码禁用）
    """

    def __init__(self, registry: SessionRuntimeStoreRegistry, profile: str = "production"):
        self._registry = registry
        self._profile = profile
        self._packet_builder = NovelWritePacketBuilder(registry)
        self._quality_pipeline = NovelQualityPipeline(registry)

    def plan_chapter(
        self,
        *,
        project_id: str,
        chapter_index: int,
        task_description: str = "",
    ) -> ChapterPlan:
        """Phase 1: Architect 规划章节。

        1. 加载 NovelProject + VolumePlan
        2. 加载已完成章节摘要
        3. 加载相关 LedgerItem
        4. 调用 Architect Agent（LLM）
        5. 验证 ChapterPlan 必填字段
        6. 持久化 ChapterPlan
        """
        # Load project
        project = self._registry.novel_project_store.load(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        # Load volume plan (if exists)
        volumes = self._registry.novel_volume_store.list_by_project(project_id)
        volume_plan = volumes[0] if volumes else None

        # Load completed chapters summary
        completed_plans = self._registry.novel_chapter_plan_store.list_by_project(project_id)
        completed_chapters = [
            p.to_dict() for p in completed_plans if p.chapter_index < chapter_index
        ]

        # Load relevant ledger items
        ledger_items = self._registry.novel_ledger_store.list_by_project(project_id)

        # Load character states
        characters = self._registry.novel_character_store.list_by_project(project_id)
        character_states = {c.name: c.current_state for c in characters}

        # Call Architect (placeholder - would use LLM adapter)
        plan = self._call_architect(
            project_id, chapter_index, volume_plan,
            completed_chapters, ledger_items, character_states,
            task_description,
        )

        # Clean drumbeat patterns from plan text before storing
        from .novel_style_cleaner import NovelStyleCleaner
        plan = NovelStyleCleaner.clean_plan(plan)

        # Persist
        self._registry.novel_chapter_plan_store.save(plan)

        return plan

    def write_chapter(
        self,
        *,
        project_id: str,
        chapter_index: int,
        revision: int = 1,
    ) -> ChapterDraft:
        """Phase 2: Director 优化 + 分 beat 生成章节正文。

        1. 加载 ChapterPlan
        2. 加载全书上下文（大纲、已完成章节、账本、伏笔、支线）
        3. 调用 Director Agent（LLM, thinking=high）
        4. 构建 NovelWritePacket（含 DirectorGuidance）
        5. 分 beat 生成
        6. 质量门控
        7. 如果拒绝，重试（最多 2 次，只重写失败的 beat）
        8. 持久化 ChapterDraft
        9. 调用 Ledger Curator
        10. 更新 Ledger
        """
        # Load chapter plan
        plan = self._registry.novel_chapter_plan_store.load_by_index(project_id, chapter_index)
        if not plan:
            raise ValueError(f"Chapter plan not found: {project_id} ch{chapter_index}")

        # Load context
        ledger_items = self._registry.novel_ledger_store.list_by_project(project_id)
        all_characters = self._registry.novel_character_store.list_by_project(project_id)
        characters = [c for c in all_characters if c.first_appearance <= chapter_index]
        character_states = {c.name: c.current_state for c in characters}
        active_memory_context, memory_recall = self._recall_novel_memory(
            project_id=project_id,
            plan=plan,
            characters=characters,
        )

        # Load previous chapter ending (hook continuity, not full summary)
        prev_plan = self._registry.novel_chapter_plan_store.load_by_index(project_id, chapter_index - 1)
        prev_chapter_ending = ""
        if prev_plan:
            prev_draft = self._registry.novel_chapter_draft_store.load_latest(prev_plan.chapter_id)
            if prev_draft:
                prev_chapter_ending = prev_draft.text[-500:]

        # Build global chapter summaries (lightweight, no plan detail)
        global_summaries = self._build_global_summaries(project_id, chapter_index)

        # Build completed-chapters summary + foreshadowing + subplot for Director's
        # global view. Previously these were all empty, so Director's "全局优化"
        # role was a no-op that still burned thinking tokens.
        completed_chapters_summary = self._build_completed_chapters_summary(project_id, chapter_index)
        foreshadowing_list = [
            i for i in ledger_items if i.section == "foreshadowing"
        ]
        subplot_status = [
            i for i in ledger_items if i.section == "open_threads"
        ]

        # Call Director (placeholder)
        director_guidance = self._call_director(
            project_id, plan, ledger_items, character_states,
            prev_chapter_ending,
            completed_chapters_summary=completed_chapters_summary,
            foreshadowing_list=foreshadowing_list,
            subplot_status=subplot_status,
        )

        # Build packet
        packet = self._packet_builder.build(
            chapter_plan=plan,
            ledger_items=ledger_items,
            prev_chapter_ending=prev_chapter_ending,
            global_summaries=global_summaries,
            character_states=character_states,
            active_memory_context=active_memory_context,
            memory_recall=memory_recall,
            director_guidance=director_guidance,
        )

        # Generate with beat-by-beat approach
        text = self._generate_with_beats(
            plan,
            packet,
            director_guidance,
            ledger_items,
            active_memory_context=active_memory_context,
            memory_recall=memory_recall,
        )

        # Quality gate + targeted rewrite loop (no more whole-chapter re-rolls).
        # 检测 → 命中硬错误则定向改写 → 复检，最多 2 轮，仍命中则降级接受。
        quality_decision, text = self._quality_pipeline.run_chapter(text, plan)

        # Continuity check: 检查遗忘的伏笔/承诺、断层、角色矛盾。
        # 结果作为 informational warnings 注入，不阻塞存盘。
        continuity_issues = self._check_continuity(
            text=text,
            chapter_plan=plan,
            ledger_items=ledger_items,
            character_states=character_states,
            prev_chapter_ending=prev_chapter_ending,
        )
        if continuity_issues:
            quality_decision.warnings.extend(continuity_issues)

        # 降级接受：即便残留 blocking 也存盘，避免 Writer 被无限重抽签烧 token。
        # status 仍如实标记，便于事后筛选。
        verdict_value = quality_decision.verdict.value
        status = "accepted" if verdict_value == "accept" else "rejected"
        if verdict_value != "accept":
            # 降级接受：保留产出版本，但标记为 rejected 以示存疑
            #（仍存盘，不丢弃）
            status = "rejected"

        # Persist draft
        draft = ChapterDraft(
            draft_id=f"draft-{plan.chapter_id}-r{revision}",
            chapter_id=plan.chapter_id,
            revision=revision,
            text=text,
            char_count=len(text),
            status=status,
            quality_decision_id=quality_decision.trace_id,
        )
        self._registry.novel_chapter_draft_store.save(draft)

        self._update_ledger(
            project_id, plan, text, ledger_items, characters, quality_decision
        )

        return draft

    def _generate_with_beats(
        self,
        plan: ChapterPlan,
        packet: NovelWritePacket,
        director_guidance: DirectorGuidance,
        ledger_items: list[LedgerItem],
        active_memory_context: list[dict[str, Any]] | None = None,
        memory_recall: list[dict[str, Any]] | None = None,
    ) -> str:
        """Generate chapter text beat by beat (sequential, 3 beats)."""
        if not plan.scene_beats:
            try:
                return self._call_writer(packet)
            except RuntimeError:
                return ""

        accumulated_text = ""
        for beat in plan.scene_beats:
            beat_text = ""
            for attempt in range(3):
                beat_packet = self._packet_builder.build_beat_packet(
                    beat=beat,
                    accumulated_text=accumulated_text,
                    chapter_plan=plan,
                    director_guidance=director_guidance,
                    ledger_items=ledger_items,
                    active_memory_context=active_memory_context,
                    memory_recall=memory_recall,
                )
                try:
                    beat_text = self._call_writer_beat(beat_packet)
                    if beat_text and beat_text.strip():
                        break
                except RuntimeError:
                    beat_text = ""
                    continue
            accumulated_text += beat_text or ""

        return accumulated_text

    def _call_architect(
        self, project_id, chapter_index, volume_plan,
        completed_chapters, ledger_items, character_states,
        task_description,
    ) -> ChapterPlan:
        """Call Architect agent."""
        from .novel_architect_adapter import NovelArchitectAdapter
        adapter = NovelArchitectAdapter(self._registry)
        return adapter.plan_chapter(
            project_id=project_id,
            chapter_index=chapter_index,
            volume_plan=volume_plan,
            completed_chapters=completed_chapters,
            ledger_items=ledger_items,
            character_states=character_states,
            task_description=task_description,
        )

    def _call_director(
        self, project_id, plan, ledger_items, character_states,
        prev_chapter_ending,
        completed_chapters_summary: str = "",
        foreshadowing_list: list | None = None,
        subplot_status: list | None = None,
    ) -> DirectorGuidance:
        """Call Director agent."""
        from .novel_director_adapter import NovelDirectorAdapter
        adapter = NovelDirectorAdapter(self._registry)
        return adapter.generate_guidance(
            project_id=project_id,
            chapter_plan=plan,
            completed_chapters_summary=completed_chapters_summary,
            ledger_items=ledger_items,
            character_states=character_states,
            foreshadowing_list=foreshadowing_list or [],
            subplot_status=subplot_status or [],
            previous_chapter_ending=prev_chapter_ending,
        )

    def _check_continuity(
        self,
        *,
        text: str,
        chapter_plan: ChapterPlan,
        ledger_items: list[LedgerItem],
        character_states: dict,
        prev_chapter_ending: str,
    ) -> list[str]:
        """Run continuity checker. Returns list of warning messages."""
        try:
            from .novel_continuity_checker import NovelContinuityChecker
            checker = NovelContinuityChecker(self._registry)
            result = checker.check_chapter(
                chapter_text=text,
                chapter_plan=chapter_plan,
                ledger_items=ledger_items,
                character_states=character_states,
                prev_chapter_ending=prev_chapter_ending,
            )
            issues = result.get("issues", [])
            severity = result.get("severity", "info")
            warnings: list[str] = []
            for issue in issues:
                label = f"[continuity:{severity}] {issue}"
                warnings.append(label)
            if result.get("suggestions"):
                for s in result["suggestions"]:
                    warnings.append(f"[continuity:suggestion] {s}")
            return warnings
        except Exception:
            return []

    def _build_completed_chapters_summary(
        self, project_id: str, chapter_index: int
    ) -> str:
        """Build a concise summary of chapters before chapter_index for Director."""
        plans = self._registry.novel_chapter_plan_store.list_by_project(project_id)
        prior = [p for p in plans if p.chapter_index < chapter_index]
        if not prior:
            return "（尚无已完成章节，本章为开篇。）"
        prior.sort(key=lambda p: p.chapter_index)
        lines = []
        for p in prior[-5:]:
            draft = self._registry.novel_chapter_draft_store.load_latest(p.chapter_id)
            tail = (draft.text[:200] + "...") if draft and draft.text else ""
            lines.append(
                f"第{p.chapter_index}章《{p.title}》[{p.chapter_position}/{p.target_emotion}]"
                f"主线:{p.plot_arrangement.main_line or '未记'}"
                + (f" 摘要:{tail}" if tail else "")
            )
        return "\n".join(lines)

    def _build_global_summaries(
        self, project_id: str, chapter_index: int
    ) -> str:
        """Build all-chapter summaries for Writer context. Lightweight:
        only title + emotion + ending_snippet per chapter."""
        plans = self._registry.novel_chapter_plan_store.list_by_project(project_id)
        prior = [p for p in plans if p.chapter_index < chapter_index]
        if not prior:
            return "（开篇章节，前无正文。）"
        prior.sort(key=lambda p: p.chapter_index)
        lines = []
        for p in prior:
            cs = p.content_summary
            # Use ending for setting/vehicle continuity
            end_snip = cs.ending[:150].rstrip("。！？，") + "。"
            lines.append(
                f"- ch{p.chapter_index}《{p.title}》({p.target_emotion}) 结尾: {end_snip}"
            )
        return "\n".join(lines)

    def _call_writer(self, packet: NovelWritePacket) -> str:
        """Call Writer agent."""
        from .novel_writer_adapter import NovelWriterAdapter
        adapter = NovelWriterAdapter(self._registry)
        return adapter.generate_chapter(packet)

    def _call_writer_beat(self, packet: NovelWritePacket) -> str:
        """Call Writer for a single beat."""
        from .novel_writer_adapter import NovelWriterAdapter
        adapter = NovelWriterAdapter(self._registry)
        return adapter.generate_beat(packet)

    def _recall_novel_memory(
        self,
        *,
        project_id: str,
        plan: ChapterPlan,
        characters: list,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        card_id, session_id = novel_memory_scope(project_id)
        query = self._build_memory_recall_query(plan, characters)
        entity_refs = [
            c.name for c in characters
            if c.name and (c.name in query or c.name in str(plan.to_dict()))
        ]
        request = MemoryRecallRequest(
            card_id=card_id,
            session_id=session_id,
            query=query,
            entity_refs=entity_refs,
            limit=8,
            min_confidence=0.0,
            min_importance=0.0,
        )

        active_result = ActiveMemoryRecallRuntime(
            self._registry.active_memory_store
        ).recall(request)
        rag_result = RagMemoryRecallRuntime(
            self._registry.rag_memory_store
        ).recall(request)

        if query and not active_result.hits:
            active_result = ActiveMemoryRecallRuntime(
                self._registry.active_memory_store
            ).recall(MemoryRecallRequest(card_id=card_id, session_id=session_id, limit=8))
        if query and not rag_result.hits:
            rag_result = RagMemoryRecallRuntime(
                self._registry.rag_memory_store
            ).recall(MemoryRecallRequest(card_id=card_id, session_id=session_id, limit=8))

        return (
            [self._recall_hit_to_prompt_item(h) for h in active_result.hits],
            [self._recall_hit_to_prompt_item(h) for h in rag_result.hits],
        )

    def _build_memory_recall_query(self, plan: ChapterPlan, characters: list) -> str:
        parts = [
            plan.title,
            plan.opening_hook,
            plan.main_payoff,
            plan.target_emotion,
            plan.content_summary.cause,
            plan.content_summary.development,
            plan.content_summary.turning_point,
            plan.content_summary.climax,
            plan.content_summary.ending,
            plan.plot_arrangement.main_line,
            plan.plot_arrangement.sub_line,
            plan.plot_arrangement.event_line,
            plan.plot_arrangement.emotion_line,
            plan.ending_design.next_chapter_push,
            plan.ending_design.hook_detail,
        ]
        parts.extend(c.name for c in characters if getattr(c, "name", ""))
        query = " ".join(str(p) for p in parts if p)
        return query[:500]

    def _recall_hit_to_prompt_item(self, hit) -> dict[str, Any]:
        return {
            "source": hit.layer,
            "layer": hit.layer,
            "memory_id": hit.memory_id,
            "content": hit.content or hit.summary,
            "summary": hit.summary,
            "importance": hit.importance,
            "confidence": hit.confidence,
            "entity_refs": list(hit.entity_refs),
            "source_refs": list(hit.source_refs),
            "hit_reasons": list(hit.hit_reasons),
        }

    def _update_ledger(
        self, project_id: str, plan: ChapterPlan,
        text: str, current_ledger: list[LedgerItem],
        characters: list,
        quality_decision,
    ) -> None:
        """Update ledger and memory after chapter writing."""
        from .novel_evolution_curator import NovelEvolutionCurator
        from ..contracts.quality_decision import QualityDecision, QualityVerdict
        try:
            side_effect_decision = quality_decision
            if text and (
                quality_decision is None or not quality_decision.is_accepted()
            ):
                side_effect_decision = QualityDecision(
                    verdict=QualityVerdict.ACCEPTED,
                    candidate_text=text,
                    warnings=(
                        list(getattr(quality_decision, "blocking_reasons", []))
                        + list(getattr(quality_decision, "warnings", []))
                    ) if quality_decision else [],
                    acceptance_notes=[
                        "novel_persisted_draft_memory_indexing",
                    ],
                )
            curator = NovelEvolutionCurator(self._registry)
            curator.curate(
                chapter_text=text,
                chapter_plan=plan,
                current_ledger_items=current_ledger,
                characters=characters,
                quality_decision=side_effect_decision,
            )
        except Exception:
            pass  # Don't fail the chapter write if evolution update fails

    def revise_chapter(
        self,
        *,
        project_id: str,
        chapter_index: int,
        feedback: str = "",
    ) -> ChapterDraft:
        """Phase 3: 修订章节。"""
        plan = self._registry.novel_chapter_plan_store.load_by_index(project_id, chapter_index)
        if not plan:
            raise ValueError(f"Chapter plan not found: {project_id} ch{chapter_index}")

        current_draft = self._registry.novel_chapter_draft_store.load_latest(plan.chapter_id)
        if not current_draft:
            raise ValueError(f"No draft to revise: {plan.chapter_id}")

        # Load context and regenerate
        ledger_items = self._registry.novel_ledger_store.list_by_project(project_id)
        characters = self._registry.novel_character_store.list_by_project(project_id)
        character_states = {c.name: c.current_state for c in characters}

        director_guidance = DirectorGuidance(
            guidance_id=f"guid-revise-{plan.chapter_id}",
            character_anchor="",
            timeline_anchor=f"第{plan.chapter_index}章, 修订",
            beat_details=(),
        )

        packet = self._packet_builder.build(
            chapter_plan=plan,
            ledger_items=ledger_items,
            prev_chapter_ending="",
            global_summaries="",
            character_states=character_states,
            director_guidance=director_guidance,
        )

        text = self._generate_with_beats(plan, packet, director_guidance, ledger_items)
        quality_decision, text = self._quality_pipeline.run_chapter(text, plan)
        status = "accepted" if quality_decision.verdict.value == "accept" else "rejected"

        new_revision = current_draft.revision + 1
        draft = ChapterDraft(
            draft_id=f"draft-{plan.chapter_id}-r{new_revision}",
            chapter_id=plan.chapter_id,
            revision=new_revision,
            text=text,
            char_count=len(text),
            status=status,
            quality_decision_id=quality_decision.trace_id,
        )
        self._registry.novel_chapter_draft_store.save(draft)

        return draft

    def batch_write(
        self,
        *,
        project_id: str,
        chapter_start: int,
        chapter_end: int,
        on_chapter_complete: Callable[[int, ChapterDraft], None] | None = None,
    ) -> list[ChapterDraft]:
        """Phase 4: 批量连续生成，带容错。

        关键约束（从 oh-story 吸收）：
        - 串行执行，不并发（上一章正文是下一章的输入）
        - 每章写完立即更新 Ledger
        - 每 3 章做一次中途快照
        - 细纲不存在时自动补建
        """
        from ..contracts.novel_batch import BatchProgress
        import uuid

        if chapter_start > chapter_end:
            raise ValueError(f"chapter_start ({chapter_start}) must be <= chapter_end ({chapter_end})")

        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        drafts: list[ChapterDraft] = []

        # Initialize batch progress
        progress = BatchProgress(
            batch_id=batch_id,
            project_id=project_id,
            chapter_start=chapter_start,
            chapter_end=chapter_end,
            status="in_progress",
        )
        self._registry.novel_batch_progress_store.save(progress)

        for chapter_index in range(chapter_start, chapter_end + 1):
            try:
                # Rate limit: delay between chapters to avoid API throttling
                if chapter_index > chapter_start:
                    import time
                    time.sleep(5)
                # Check if plan exists, create if not
                plan = self._registry.novel_chapter_plan_store.load_by_index(
                    project_id, chapter_index
                )
                if plan is None:
                    plan = self.plan_chapter(
                        project_id=project_id, chapter_index=chapter_index
                    )

                # Write chapter
                draft = self.write_chapter(
                    project_id=project_id, chapter_index=chapter_index
                )
                drafts.append(draft)

                # Update progress
                progress = BatchProgress(
                    batch_id=batch_id,
                    project_id=project_id,
                    chapter_start=chapter_start,
                    chapter_end=chapter_end,
                    chapter_index=chapter_index,
                    status="in_progress",
                )
                self._registry.novel_batch_progress_store.save(progress)

                # Callback
                if on_chapter_complete:
                    on_chapter_complete(chapter_index, draft)

            except Exception as e:
                # Mark failed and continue
                progress = BatchProgress(
                    batch_id=batch_id,
                    project_id=project_id,
                    chapter_start=chapter_start,
                    chapter_end=chapter_end,
                    chapter_index=chapter_index,
                    status="failed",
                    error_message=str(e)[:200],
                )
                self._registry.novel_batch_progress_store.save(progress)
                continue

        # Mark completed
        progress = BatchProgress(
            batch_id=batch_id,
            project_id=project_id,
            chapter_start=chapter_start,
            chapter_end=chapter_end,
            chapter_index=chapter_end,
            status="completed",
        )
        self._registry.novel_batch_progress_store.save(progress)

        return drafts
