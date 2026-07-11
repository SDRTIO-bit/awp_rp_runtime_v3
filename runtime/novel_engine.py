"""NovelEngine — Novel chapter generation engine.

Independent from PersistentTurnEngine, shares infrastructure (LLM adapters, storage, contracts).
"""

from __future__ import annotations

import time
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
from .novel_trace import (
    NovelStreamCallbacks,
    safe_on_phase,
    safe_on_beat,
    safe_on_chunk,
    safe_on_error,
)


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

    def __init__(self, registry: SessionRuntimeStoreRegistry, profile: str = "production",
                 callbacks: NovelStreamCallbacks | None = None):
        self._registry = registry
        self._profile = profile
        self._packet_builder = NovelWritePacketBuilder(registry)
        self._quality_pipeline = NovelQualityPipeline(registry)
        self._callbacks = callbacks or NovelStreamCallbacks()

    def _safe_on_phase(self, event: str, name: str, payload: dict[str, Any]) -> None:
        safe_on_phase(self._callbacks.on_phase, event, name, payload)

    def _safe_on_beat(self, event: str, beat_index: int, payload: dict[str, Any]) -> None:
        safe_on_beat(self._callbacks.on_beat, event, beat_index, payload)

    def _safe_on_chunk(self, text: str) -> None:
        safe_on_chunk(self._callbacks.on_chunk, text)

    def _safe_on_error(self, phase: str, message: str) -> None:
        safe_on_error(self._callbacks.on_error, phase, message)

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

        # Load architect prompt override from project config
        project_config = getattr(project, "config", {}) or {}
        architect_prompt_name = project_config.get("architect_prompt", "architect")

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

        # Load character states — only characters that have appeared
        all_characters = self._registry.novel_character_store.list_by_project(project_id)
        characters = [c for c in all_characters if c.first_appearance <= chapter_index]
        character_states = self._build_character_context(characters)

        # Call Architect
        plan = self._call_architect(
            project_id, chapter_index, volume_plan,
            completed_chapters, ledger_items, character_states,
            task_description, architect_prompt_name=architect_prompt_name,
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
        write_guidance: str = "",
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

        # Load project config for writer_prompt / genre overrides
        project = self._registry.novel_project_store.load(project_id)
        project_config = getattr(project, "config", {}) or {}
        writer_prompt_name = project_config.get("writer_prompt", "writer")
        skip_drumbeat = writer_prompt_name != "writer"

        # Load context
        ledger_items = self._registry.novel_ledger_store.list_by_project(project_id)
        all_characters = self._registry.novel_character_store.list_by_project(project_id)
        characters = [c for c in all_characters if c.first_appearance <= chapter_index]
        character_states = self._build_character_context(characters)
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
            writer_prompt_name=writer_prompt_name,
            write_guidance=write_guidance,
        )

        # Quality gate + targeted rewrite loop (no more whole-chapter re-rolls).
        # 检测 → 命中硬错误则定向改写 → 复检，最多 2 轮，仍命中则降级接受。
        quality_decision, text = self._quality_pipeline.run_chapter(text, plan, skip_drumbeat_check=skip_drumbeat)

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
        *,
        writer_prompt_name: str = "writer",
        write_guidance: str = "",
    ) -> str:
        """Generate chapter text beat by beat (sequential, 3 beats)."""
        if not plan.scene_beats:
            try:
                return self._call_writer(packet, writer_prompt_name=writer_prompt_name, write_guidance=write_guidance)
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
                    beat_text = self._call_writer_beat(beat_packet, writer_prompt_name=writer_prompt_name, write_guidance=write_guidance)
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
        task_description, architect_prompt_name="architect",
    ) -> ChapterPlan:
        """Call Architect agent."""
        from .novel_architect_adapter import NovelArchitectAdapter
        adapter = NovelArchitectAdapter(self._registry, architect_prompt_name=architect_prompt_name)
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

    def _build_character_context(self, characters: list) -> dict:
        """Build rich character context for Writer/Architect/Director.

        Includes personality, voice, relationships, motivations —
        everything needed to write accurate character interactions.
        Not just the thin 'location + emotion' from current_state.
        """
        context = {}
        for c in characters:
            info = {}
            info["role"] = c.role or ""
            info["personality"] = c.personality or ""
            info["voice_style"] = c.voice_style or ""
            info["core_motivation"] = c.core_motivation or ""
            info["weakness"] = c.weakness or ""
            info["arc_phase"] = c.arc_phase or ""
            info["first_appearance"] = c.first_appearance

            state = getattr(c, "current_state", {}) or {}
            info["location"] = state.get("location", "")
            info["emotion"] = state.get("emotion", "")

            relationships = getattr(c, "relationships", None) or []
            rels = []
            for r in relationships:
                rels.append(f"{r.target_name}({r.relation_type}, tension={r.tension})")
            info["relationships"] = ", ".join(rels) if rels else ""

            context[c.name] = info
        return context

    def _build_completed_chapters_summary(
        self, project_id: str, chapter_index: int
    ) -> str:
        """Build a concise summary of chapters before chapter_index for Director.

        Uses chapter_summary ledger items (narrative summaries written by the
        LedgerCurator after each chapter completes). Falls back to plan data
        if no summaries exist yet.
        """
        ledger_items = self._registry.novel_ledger_store.list_by_project(project_id)
        summaries: dict[int, str] = {}
        for item in ledger_items:
            if item.section == "chapter_summary" and item.entity and item.content:
                try:
                    ch = int(item.entity.replace("ch", ""))
                    summaries[ch] = item.content
                except ValueError:
                    pass

        plans = self._registry.novel_chapter_plan_store.list_by_project(project_id)
        prior = [p for p in plans if p.chapter_index < chapter_index]
        if not prior:
            return "（尚无已完成章节，本章为开篇。）"
        prior.sort(key=lambda p: p.chapter_index)
        lines = []
        for p in prior[-5:]:
            ch = p.chapter_index
            summary = summaries.get(ch)
            if summary:
                lines.append(f"第{ch}章: {summary}")
            else:
                tail = f"标题:{p.title} 情绪:{p.target_emotion}"
                lines.append(f"第{ch}章（无总结）: {tail}")
        return "\n".join(lines)

    def _build_global_summaries(
        self, project_id: str, chapter_index: int
    ) -> str:
        """Build all-chapter summaries for Writer context.

        Reads chapter_summary ledger items (narrative summaries produced
        by LedgerCurator after each chapter). Falls back to plan data.
        """
        ledger_items = self._registry.novel_ledger_store.list_by_project(project_id)
        summaries: dict[int, str] = {}
        for item in ledger_items:
            if item.section == "chapter_summary" and item.entity and item.content:
                try:
                    ch = int(item.entity.replace("ch", ""))
                    summaries[ch] = item.content
                except ValueError:
                    pass

        plans = self._registry.novel_chapter_plan_store.list_by_project(project_id)
        prior = [p for p in plans if p.chapter_index < chapter_index]
        if not prior:
            return "（开篇章节，前无正文。）"
        prior.sort(key=lambda p: p.chapter_index)
        lines = []
        for p in prior:
            ch = p.chapter_index
            summary = summaries.get(ch)
            if summary:
                lines.append(f"- 第{ch}章《{p.title}》: {summary}")
            else:
                cs = p.content_summary
                end_snip = cs.ending[:150].rstrip("。！？，") + "。"
                lines.append(f"- 第{ch}章《{p.title}》({p.target_emotion}) [plan]: {end_snip}")
        return "\n".join(lines)

    def _call_writer(self, packet: NovelWritePacket, *, writer_prompt_name: str = "writer", write_guidance: str = "") -> str:
        """Call Writer agent."""
        from .novel_writer_adapter import NovelWriterAdapter
        adapter = NovelWriterAdapter(self._registry, writer_prompt_name=writer_prompt_name)
        return adapter.generate_chapter(packet, write_guidance=write_guidance)

    def _call_writer_beat(self, packet: NovelWritePacket, *, writer_prompt_name: str = "writer", write_guidance: str = "") -> str:
        """Call Writer for a single beat."""
        from .novel_writer_adapter import NovelWriterAdapter
        adapter = NovelWriterAdapter(self._registry, writer_prompt_name=writer_prompt_name)
        return adapter.generate_beat(packet, write_guidance=write_guidance)

    def _call_writer_beat_stream(self, packet: NovelWritePacket, on_chunk, *, writer_prompt_name: str = "writer", write_guidance: str = "") -> str:
        """Call Writer for a single beat with streaming callback."""
        from .novel_writer_adapter import NovelWriterAdapter
        adapter = NovelWriterAdapter(self._registry, writer_prompt_name=writer_prompt_name)
        return adapter.generate_beat_stream(packet, on_chunk, write_guidance=write_guidance)

    def _generate_with_beats_stream(
        self,
        plan: ChapterPlan,
        packet: NovelWritePacket,
        director_guidance: DirectorGuidance,
        ledger_items: list[LedgerItem],
        active_memory_context: list[dict[str, Any]] | None = None,
        memory_recall: list[dict[str, Any]] | None = None,
        *,
        writer_prompt_name: str = "writer",
        write_guidance: str = "",
    ) -> str:
        """Generate chapter text beat by beat with streaming callbacks."""
        if not plan.scene_beats:
            try:
                text = self._call_writer(packet, writer_prompt_name=writer_prompt_name, write_guidance=write_guidance)
                self._safe_on_chunk(text)
                return text
            except RuntimeError:
                return ""

        beat_count = len(plan.scene_beats)
        accumulated_text = ""
        for i, beat in enumerate(plan.scene_beats):
            beat_idx = i + 1
            self._safe_on_beat("start", beat_idx, {
                "beat_count": beat_count,
                "budget_chars": beat.budget_chars,
                "description": beat.description[:80],
                "density": beat.density,
            })

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
                    t_start = time.time()
                    beat_text = self._call_writer_beat_stream(
                        beat_packet, self._safe_on_chunk,
                        writer_prompt_name=writer_prompt_name,
                        write_guidance=write_guidance,
                    )
                    duration_ms = int((time.time() - t_start) * 1000)
                    if beat_text and beat_text.strip():
                        self._safe_on_beat("end", beat_idx, {
                            "duration_ms": duration_ms,
                            "char_count": len(beat_text),
                            "attempt": attempt + 1,
                        })
                        break
                except RuntimeError:
                    duration_ms = int((time.time() - t_start) * 1000)
                    self._safe_on_beat("error", beat_idx, {
                        "duration_ms": duration_ms,
                        "attempt": attempt + 1,
                        "message": "LLM returned empty output",
                    })
                    beat_text = ""
                    continue
            accumulated_text += beat_text or ""

        return accumulated_text

    def write_chapter_stream(
        self,
        *,
        project_id: str,
        chapter_index: int,
        revision: int = 1,
        write_guidance: str = "",
    ) -> ChapterDraft:
        """Streaming variant of write_chapter — emits phase/beat/chunk callbacks.

        Identical to write_chapter in logic, but fires callbacks at each
        pipeline stage so a TUI consumer can render progress in real time.
        """
        plan = self._registry.novel_chapter_plan_store.load_by_index(project_id, chapter_index)
        if not plan:
            raise ValueError(f"Chapter plan not found: {project_id} ch{chapter_index}")

        project = self._registry.novel_project_store.load(project_id)
        project_config = getattr(project, "config", {}) or {}
        writer_prompt_name = project_config.get("writer_prompt", "writer")

        ledger_items = self._registry.novel_ledger_store.list_by_project(project_id)
        all_characters = self._registry.novel_character_store.list_by_project(project_id)
        characters = [c for c in all_characters if c.first_appearance <= chapter_index]
        character_states = self._build_character_context(characters)
        active_memory_context, memory_recall = self._recall_novel_memory(
            project_id=project_id, plan=plan, characters=characters,
        )

        prev_plan = self._registry.novel_chapter_plan_store.load_by_index(project_id, chapter_index - 1)
        prev_chapter_ending = ""
        if prev_plan:
            prev_draft = self._registry.novel_chapter_draft_store.load_latest(prev_plan.chapter_id)
            if prev_draft:
                prev_chapter_ending = prev_draft.text[-500:]

        global_summaries = self._build_global_summaries(project_id, chapter_index)
        completed_chapters_summary = self._build_completed_chapters_summary(project_id, chapter_index)
        foreshadowing_list = [i for i in ledger_items if i.section == "foreshadowing"]
        subplot_status = [i for i in ledger_items if i.section == "open_threads"]

        # Phase: director
        self._safe_on_phase("start", "director", {"ch": chapter_index, "thinking": "high"})
        t = time.time()
        director_guidance = self._call_director(
            project_id, plan, ledger_items, character_states,
            prev_chapter_ending,
            completed_chapters_summary=completed_chapters_summary,
            foreshadowing_list=foreshadowing_list,
            subplot_status=subplot_status,
        )
        self._safe_on_phase("end", "director", {
            "ch": chapter_index,
            "duration_ms": int((time.time() - t) * 1000),
            "character_anchor": director_guidance.character_anchor[:200] if director_guidance.character_anchor else "",
            "timeline_anchor": director_guidance.timeline_anchor[:200] if director_guidance.timeline_anchor else "",
            "beat_details": [{"id": b.beat_id, "goal": b.narrative_strategy[:80] if hasattr(b, 'narrative_strategy') else b.content_outline[:80]} for b in (director_guidance.beat_details or [])],
        })

        packet = self._packet_builder.build(
            chapter_plan=plan, ledger_items=ledger_items,
            prev_chapter_ending=prev_chapter_ending,
            global_summaries=global_summaries,
            character_states=character_states,
            active_memory_context=active_memory_context,
            memory_recall=memory_recall,
            director_guidance=director_guidance,
        )

        # Phase: writer (with streaming beats)
        self._safe_on_phase("start", "writer", {"ch": chapter_index, "thinking": "medium"})
        t = time.time()
        text = self._generate_with_beats_stream(
            plan, packet, director_guidance, ledger_items,
            active_memory_context=active_memory_context,
            memory_recall=memory_recall,
            writer_prompt_name=writer_prompt_name,
            write_guidance=write_guidance,
        )
        self._safe_on_phase("end", "writer", {
            "ch": chapter_index,
            "duration_ms": int((time.time() - t) * 1000),
            "total_chars": len(text),
        })

        skip_drumbeat = writer_prompt_name != "writer"

        # Phase: quality
        self._safe_on_phase("start", "quality", {"ch": chapter_index})
        t = time.time()
        quality_decision, text = self._quality_pipeline.run_chapter(text, plan, skip_drumbeat_check=skip_drumbeat)
        self._safe_on_phase("end", "quality", {
            "ch": chapter_index,
            "duration_ms": int((time.time() - t) * 1000),
            "verdict": quality_decision.verdict.value,
            "blocking_reasons": list(getattr(quality_decision, "blocking_reasons", [])),
            "warnings": [w[:120] for w in getattr(quality_decision, "warnings", [])],
        })

        # Phase: continuity
        self._safe_on_phase("start", "continuity", {"ch": chapter_index})
        t = time.time()
        continuity_issues = self._check_continuity(
            text=text, chapter_plan=plan, ledger_items=ledger_items,
            character_states=character_states, prev_chapter_ending=prev_chapter_ending,
        )
        if continuity_issues:
            quality_decision.warnings.extend(continuity_issues)
        self._safe_on_phase("end", "continuity", {
            "ch": chapter_index,
            "duration_ms": int((time.time() - t) * 1000),
            "issue_count": len(continuity_issues),
            "issues": continuity_issues[:5],
        })

        verdict_value = quality_decision.verdict.value
        status = "accepted" if verdict_value == "accept" else "rejected"

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

        # Phase: ledger
        self._safe_on_phase("start", "ledger", {"ch": chapter_index})
        t = time.time()
        self._update_ledger(
            project_id, plan, text, ledger_items, characters, quality_decision
        )
        self._safe_on_phase("end", "ledger", {
            "ch": chapter_index,
            "duration_ms": int((time.time() - t) * 1000),
        })

        return draft

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
        if quality_decision is None or not quality_decision.is_accepted():
            return

        from .novel_evolution_curator import NovelEvolutionCurator
        try:
            curator = NovelEvolutionCurator(self._registry)
            curator.curate(
                chapter_text=text,
                chapter_plan=plan,
                current_ledger_items=current_ledger,
                characters=characters,
                quality_decision=quality_decision,
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
        project = self._registry.novel_project_store.load(project_id)
        project_config = getattr(project, "config", {}) or {}
        writer_prompt_name = project_config.get("writer_prompt", "writer")
        skip_drumbeat = writer_prompt_name != "writer"
        ledger_items = self._registry.novel_ledger_store.list_by_project(project_id)
        characters = self._registry.novel_character_store.list_by_project(project_id)
        character_states = self._build_character_context(characters)

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
        quality_decision, text = self._quality_pipeline.run_chapter(text, plan, skip_drumbeat_check=skip_drumbeat)
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
        failures: list[tuple[int, str]] = []

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
                error_message = str(e)[:200]
                failures.append((chapter_index, error_message))
                progress = BatchProgress(
                    batch_id=batch_id,
                    project_id=project_id,
                    chapter_start=chapter_start,
                    chapter_end=chapter_end,
                    chapter_index=chapter_index,
                    status="failed",
                    failed_chapters=tuple(index for index, _ in failures),
                    error_message=error_message,
                )
                self._registry.novel_batch_progress_store.save(progress)
                continue

        if not failures:
            final_status = "completed"
        elif drafts:
            final_status = "completed_with_failures"
        else:
            final_status = "failed"

        # Persist the aggregate final outcome after all chapters have run.
        progress = BatchProgress(
            batch_id=batch_id,
            project_id=project_id,
            chapter_start=chapter_start,
            chapter_end=chapter_end,
            chapter_index=chapter_end,
            status=final_status,
            failed_chapters=tuple(index for index, _ in failures),
            error_message="; ".join(
                f"chapter {index}: {error_message}"[:200]
                for index, error_message in failures
            ),
        )
        self._registry.novel_batch_progress_store.save(progress)

        return drafts
