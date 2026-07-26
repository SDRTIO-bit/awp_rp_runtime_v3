"""NovelWritePacketBuilder — Build NovelWritePacket with oh-story's write-before-three-steps.

Implements: 状态筛选 → 模块召回 → 意图确认
"""

from __future__ import annotations

from typing import Any

from ..contracts.novel_write_packet import NovelWritePacket
from ..contracts.novel_chapter import ChapterPlan
from ..contracts.novel_authoring import AuthorChapterPlan
from ..contracts.novel_ledger import LedgerItem
from ..contracts.novel_director_guidance import DirectorGuidance
from .novel_writer_context import NovelWriterContextCompiler
from .novel_author_plan_compiler import AuthorPlanCompiler
from .novel_authoring_service import NovelAuthoringService


def writer_safe_guidance(guidance: DirectorGuidance) -> DirectorGuidance:
    """Return a Writer-facing copy of the guidance with private NPC internals stripped.

    The Writer only ever needs beat details, fact anchors, foreshadowing/subplot
    scheduling and the already-selected visible consequences. The internal
    ``selected_npc_actions`` (which carry ``reasoning``) and any Director
    ``reasoning`` never cross the boundary. If a guidance populates only the
    ``selected_npc_actions`` (legacy shape) the surviving visible consequences
    are lifted onto the packet before the private actions are stripped.
    """

    visible = guidance.visible_consequences or tuple(
        action.visible_consequence for action in guidance.selected_npc_actions
    )
    return DirectorGuidance(
        schema_id=guidance.schema_id,
        schema_version=guidance.schema_version,
        guidance_id=guidance.guidance_id,
        character_anchor=guidance.character_anchor,
        timeline_anchor=guidance.timeline_anchor,
        beat_details=guidance.beat_details,
        outline_enhancements=guidance.outline_enhancements,
        foreshadowing_schedule=guidance.foreshadowing_schedule,
        subplot_status=guidance.subplot_status,
        visible_consequences=visible,
        selected_npc_actions=(),  # private to the Director/Curator path
        risk_flags=guidance.risk_flags,
        opportunities=guidance.opportunities,
        reasoning="",
    )


class NovelWritePacketBuilder:
    """Build NovelWritePacket implementing oh-story's write-before-three-steps."""

    def __init__(self, registry):
        self._registry = registry
        self._context_compiler = NovelWriterContextCompiler()

    def build(
        self,
        chapter_plan: ChapterPlan,
        ledger_items: list[LedgerItem],
        prev_chapter_ending: str,
        global_summaries: str,
        character_states: dict[str, Any],
        director_guidance: DirectorGuidance,
        active_memory_context: list[dict[str, Any]] | None = None,
        memory_recall: list[dict[str, Any]] | None = None,
        reference_books: list[dict] | None = None,
    ) -> NovelWritePacket:
        """Build a NovelWritePacket with write-before-three-steps.

        Step 1: 状态筛选 — 只保留"不知道就会写错"的信息
        Step 2: 模块召回 — 从对标书找情绪/节奏/文风参考
        Step 3: 意图确认 — 一句话概括本章写作目标
        """
        project_root = ""
        if self._registry is not None:
            try:
                project = self._registry.novel_project_store.load(chapter_plan.project_id)
                config = getattr(project, "config", {}) or {}
                project_root = str(config.get("novel_dir", "") or "")
            except (AttributeError, TypeError):
                project_root = ""

        # Step 2: 模块召回
        ref_books = reference_books or []
        emotion_module = self._recall_emotion_module(chapter_plan, ref_books)
        rhythm_reference = self._recall_rhythm(chapter_plan, ref_books)
        style_profile = self._recall_style(ref_books)

        # Step 3: 意图确认
        writing_intent = self._confirm_intent(
            chapter_plan, emotion_module, rhythm_reference, director_guidance
        )

        packet = self._context_compiler.compile(
            chapter_plan=chapter_plan,
            ledger_items=ledger_items,
            prev_chapter_ending=prev_chapter_ending,
            global_summaries=global_summaries,
            character_states=character_states,
            director_guidance=writer_safe_guidance(director_guidance),
            project_root=project_root,
            active_memory_context=active_memory_context,
            memory_recall=memory_recall,
        )
        packet.writing_intent = writing_intent
        packet.emotion_module = emotion_module
        packet.rhythm_reference = rhythm_reference
        packet.style_profile = style_profile
        author_contract = self._approved_author_contract(
            chapter_plan, project_root
        )
        if author_contract:
            packet.chapter_contract = author_contract
        return packet

    def build_beat_packet(
        self,
        beat: Any,
        accumulated_text: str,
        chapter_plan: ChapterPlan,
        director_guidance: DirectorGuidance,
        ledger_items: list[LedgerItem],
        active_memory_context: list[dict[str, Any]] | None = None,
        memory_recall: list[dict[str, Any]] | None = None,
        sibling_outlines: list[str] | None = None,
    ) -> NovelWritePacket:
        """Build a packet for a single beat."""
        relevant_items = self._filter_relevant_ledger(
            chapter_plan, ledger_items, beat=beat,
            chapter_index=getattr(chapter_plan, 'chapter_index', 0),
        )
        foreshadowing_items = [
            i.to_dict() for i in relevant_items if i.section == "foreshadowing"
        ]
        world_constraints = [
            i.content for i in ledger_items if i.section == "world_rules"
        ]

        safe_guidance = writer_safe_guidance(director_guidance)
        project_root = self._project_root(chapter_plan)
        return NovelWritePacket(
            packet_id=f"pkt-{chapter_plan.chapter_id}-{beat.beat_id}",
            project_id=chapter_plan.project_id,
            chapter_id=chapter_plan.chapter_id,
            chapter_plan=chapter_plan,
            relevant_ledger_items=relevant_items,
            active_memory_context=list(active_memory_context or []),
            memory_recall=list(memory_recall or []),
            foreshadowing_items=foreshadowing_items,
            world_constraints=world_constraints,
            director_guidance=safe_guidance,
            visible_consequences=safe_guidance.visible_consequences,
            current_scene_beat=beat,
            accumulated_text=accumulated_text,
            sibling_outlines=list(sibling_outlines or []),
            project_root=project_root,
            chapter_contract=self._approved_author_contract(
                chapter_plan, project_root
            ),
        )

    def _project_root(self, chapter_plan: ChapterPlan) -> str:
        if self._registry is None:
            return ""
        try:
            project = self._registry.novel_project_store.load(
                chapter_plan.project_id
            )
            return str((getattr(project, "config", {}) or {}).get("novel_dir", "") or "")
        except (AttributeError, TypeError):
            return ""

    @staticmethod
    def _approved_author_contract(
        chapter_plan: ChapterPlan, project_root: str
    ) -> str:
        if not project_root:
            return ""
        try:
            context = NovelAuthoringService(
                project_root, chapter_plan.project_id
            ).authoring_context(chapter_plan.chapter_index)
            candidates = [
                AuthorChapterPlan.model_validate(raw)
                for raw in context["plans"]
                if raw.get("status") in {"approved", "executed"}
            ]
            if not candidates:
                return ""
            latest = max(candidates, key=lambda item: item.revision)
            return AuthorPlanCompiler().render_writer_contract(latest)
        except (FileNotFoundError, OSError, ValueError, KeyError, TypeError):
            return ""

    def _filter_relevant_ledger(
        self, plan: ChapterPlan, items: list[LedgerItem],
        beat: Any = None,
        chapter_index: int = 0,
    ) -> list[LedgerItem]:
        """按需加载：用相关性评分替代硬截断。

        Args:
            plan: 当前章节计划
            items: 全部账本条项
            beat: 若提供则做 beat 级细粒度过滤（阈值更高）
            chapter_index: 当前章节编号，用于优先级排序
        """
        plan_text = f"{plan.content_summary.cause} {plan.content_summary.development}"
        beat_text = ""
        if beat is not None:
            beat_text = f"{getattr(beat, 'description', '')} {getattr(beat, 'function_tag', '')}"

        scored: list[tuple[int, LedgerItem]] = []
        for item in items:
            entity = item.entity
            score = 0

            # 实体命中当前 beat 描述 → 最高权重
            if beat_text and entity and entity in beat_text:
                score += 10
            # 实体命中章节计划文本
            elif entity and entity in plan_text:
                score += 5
            # 状态加成
            if item.status == "active":
                score += 3
            elif item.status in ("resolved", "stale"):
                score -= 2  # 仍需出现但下调优先级
            else:
                score += 1  # open, pending 等中间状态

            # 章节距离加成：距当前章节越近优先级越高
            if chapter_index and item.source_chapter:
                distance = chapter_index - item.source_chapter
                if distance <= 1:
                    score += 2
                elif distance <= 3:
                    score += 1

            # beat 级阈值更高（>=5），章节级放宽（>=3）
            threshold = 5 if beat is not None else 3
            if score >= threshold:
                scored.append((-score, item))  # 负号用于降序排列

        scored.sort(key=lambda x: x[0])
        return [item for _, item in scored]

    def _filter_relevant_characters(
        self, plan: ChapterPlan, character_states: dict[str, Any]
    ) -> dict[str, Any]:
        """只保留本章涉及的角色状态。"""
        if not character_states:
            return {}
        # Include all for now; could filter by appearance_order
        return character_states

    def _recall_emotion_module(
        self, plan: ChapterPlan, reference_books: list[dict]
    ) -> dict[str, Any]:
        """从对标书找情绪模块。"""
        if not reference_books:
            return {}
        # Simple implementation: find first matching emotion
        target_emotion = plan.target_emotion
        for book in reference_books:
            for module in book.get("emotion_modules", []):
                if target_emotion in str(module):
                    return module
        return {}

    def _recall_rhythm(
        self, plan: ChapterPlan, reference_books: list[dict]
    ) -> dict[str, Any]:
        """从对标书找节奏参考。"""
        if not reference_books:
            return {}
        # Return first book's rhythm profile
        for book in reference_books:
            if book.get("rhythm_profile"):
                return book["rhythm_profile"]
        return {}

    def _recall_style(
        self, reference_books: list[dict]
    ) -> dict[str, Any]:
        """从对标书找文风参考。"""
        if not reference_books:
            return {}
        # Return first book's style profile
        for book in reference_books:
            if book.get("style_profile"):
                return {"description": book["style_profile"]}
        return {}

    def _confirm_intent(
        self,
        plan: ChapterPlan,
        emotion_module: dict[str, Any],
        rhythm: dict[str, Any],
        guidance: DirectorGuidance,
    ) -> str:
        """一句话写作意图。"""
        parts = []
        parts.append(f"目标情绪: {plan.target_emotion}")
        if getattr(guidance, 'timeline_anchor', None):
            parts.append(f"时间: {guidance.timeline_anchor}")
        beat_details = getattr(guidance, 'beat_details', None) or ()
        if beat_details:
            beats_summary = " → ".join(bd.emotion_shift for bd in beat_details if getattr(bd, 'emotion_shift', ''))
            if beats_summary:
                parts.append(f"情绪弧线: {beats_summary}")
        if emotion_module:
            parts.append(f"情绪模块: {emotion_module.get('name', '无')}")
        if rhythm:
            parts.append(f"节奏参考: {rhythm.get('name', '无')}")
        return " | ".join(parts)
