"""Compile the broad planning context into a bounded Writer input packet."""

from __future__ import annotations

from typing import Any

from ..contracts.novel_chapter import ChapterPlan
from ..contracts.novel_director_guidance import DirectorGuidance
from ..contracts.novel_ledger import LedgerItem
from ..contracts.novel_write_packet import NovelWritePacket


class NovelWriterContextCompiler:
    """Deterministic boundary between the heavy Plan Agent and the Writer."""

    HISTORY_CHAPTER_LIMIT = 3
    WORLD_RULE_LIMIT = 3
    WORLD_RULE_CHAR_LIMIT = 2000

    def compile(
        self,
        *,
        chapter_plan: ChapterPlan,
        ledger_items: list[LedgerItem],
        prev_chapter_ending: str,
        global_summaries: str,
        character_states: dict[str, Any],
        director_guidance: DirectorGuidance,
        project_root: str = "",
        active_memory_context: list[dict[str, Any]] | None = None,
        memory_recall: list[dict[str, Any]] | None = None,
    ) -> NovelWritePacket:
        allowed_cast = self._allowed_cast(chapter_plan, character_states)
        selected_characters = {
            name: character_states[name]
            for name in allowed_cast
            if name in character_states
        }
        world_constraints = self._world_constraints(ledger_items)
        relevant_items = self._relevant_ledger(
            chapter_plan, ledger_items, allowed_cast
        )

        return NovelWritePacket(
            packet_id=f"pkt-{chapter_plan.chapter_id}",
            project_id=chapter_plan.project_id,
            chapter_id=chapter_plan.chapter_id,
            project_root=project_root,
            chapter_plan=chapter_plan,
            prev_chapter_ending=prev_chapter_ending,
            global_summaries=global_summaries,
            relevant_ledger_items=relevant_items,
            character_states=selected_characters,
            active_memory_context=list(active_memory_context or []),
            memory_recall=list(memory_recall or []),
            foreshadowing_items=[
                item.to_dict()
                for item in relevant_items
                if item.section == "foreshadowing"
            ],
            world_constraints=world_constraints,
            director_guidance=director_guidance,
            allowed_cast=allowed_cast,
            chapter_contract=self._chapter_contract(chapter_plan, allowed_cast),
            history_context=self._bounded_history(global_summaries),
        )

    @staticmethod
    def _allowed_cast(
        plan: ChapterPlan, character_states: dict[str, Any]
    ) -> tuple[str, ...]:
        planned = tuple(plan.character_appearance.appearance_order)
        if planned:
            return tuple(name for name in planned if name in character_states)
        return tuple(character_states.keys())

    def _world_constraints(self, items: list[LedgerItem]) -> list[str]:
        rules = []
        for item in items:
            if item.section != "world_rules" or item.entity == "outline":
                continue
            content = (item.content or "").strip()
            if content:
                rules.append(content[: self.WORLD_RULE_CHAR_LIMIT])
            if len(rules) >= self.WORLD_RULE_LIMIT:
                break
        return rules

    @staticmethod
    def _plan_text(plan: ChapterPlan) -> str:
        return " ".join(
            [
                plan.title,
                plan.opening_hook,
                plan.main_payoff,
                plan.content_summary.cause,
                plan.content_summary.development,
                plan.content_summary.turning_point,
                plan.content_summary.climax,
                plan.content_summary.ending,
                *(beat.description for beat in plan.scene_beats),
            ]
        )

    def _relevant_ledger(
        self,
        plan: ChapterPlan,
        items: list[LedgerItem],
        allowed_cast: tuple[str, ...],
    ) -> list[LedgerItem]:
        plan_text = self._plan_text(plan)
        selected = []
        for item in items:
            if item.section in {"chapter_summary", "world_rules"}:
                continue
            if item.status in {"resolved", "stale", "contradicted"}:
                continue
            entity = (item.entity or "").strip()
            content = item.content or ""
            if (
                (entity and entity in allowed_cast)
                or (entity and entity in plan_text)
                or any(name in content for name in allowed_cast)
            ):
                selected.append(item)
        return selected[:20]

    def _bounded_history(self, summaries: str) -> str:
        lines = [line.strip() for line in (summaries or "").splitlines() if line.strip()]
        if len(lines) <= self.HISTORY_CHAPTER_LIMIT:
            return "\n".join(lines)
        omitted = len(lines) - self.HISTORY_CHAPTER_LIMIT
        return (
            f"（更早 {omitted} 章已由 Plan Agent 吸收，Writer 仅保留最近"
            f" {self.HISTORY_CHAPTER_LIMIT} 章。）\n"
            + "\n".join(lines[-self.HISTORY_CHAPTER_LIMIT :])
        )

    @staticmethod
    def _chapter_contract(plan: ChapterPlan, allowed_cast: tuple[str, ...]) -> str:
        lines = [
            f"标题: {plan.title}",
            f"章节定位: {plan.chapter_position}",
            f"目标情绪: {plan.target_emotion}",
            f"目标字数: {plan.target_chars}",
            f"允许出场角色: {'、'.join(allowed_cast)}",
            f"开场状态: {plan.opening_hook or plan.content_summary.cause}",
        ]
        summary = plan.content_summary
        moves = []
        opening_move = "".join(
            part for part in (summary.cause, summary.development) if part
        )
        if opening_move:
            moves.append(opening_move)
        if summary.turning_point:
            moves.append(summary.turning_point)
        if summary.climax:
            moves.append(summary.climax)
        if moves:
            lines.append("叙事动作（只约束事件与局面变化，不规定具体对白和段落格式）:")
            lines.extend(
                f"叙事动作{index}: {move}"
                for index, move in enumerate(moves, start=1)
            )
        if summary.turning_point:
            lines.append(f"必须发生的转折: {summary.turning_point}")
        if summary.climax:
            lines.append(f"必须兑现的核心行动: {summary.climax}")
        if plan.main_payoff:
            lines.append(f"本章回报: {plan.main_payoff}")
        if plan.plot_arrangement.emotion_line:
            lines.append(f"关系变化: {plan.plot_arrangement.emotion_line}")
        lines.extend(
            f"关系变化要求: {change}"
            for change in plan.character_appearance.relationship_changes
        )
        ending = plan.ending_design
        if summary.ending:
            lines.append(f"章末事件: {summary.ending}")
        if ending.closing_state:
            lines.append(f"章末状态: {ending.closing_state}")
        if ending.hook_detail:
            lines.append(f"收束画面: {ending.hook_detail}")
        if ending.next_chapter_push:
            lines.append(f"不可提前展开，只作尾部推动: {ending.next_chapter_push}")
        return "\n".join(line for line in lines if not line.endswith(": "))
