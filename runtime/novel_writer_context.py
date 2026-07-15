"""Compile the broad planning context into a bounded Writer input packet."""

from __future__ import annotations

from typing import Any
import re

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
            # Private NPC agendas/actions never cross the Writer boundary.
            if item.section in {"chapter_summary", "world_rules", "npc_agenda", "npc_action"}:
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
        def short(value: str, limit: int) -> str:
            text = re.sub(r"\s+", " ", value or "").strip()
            dialogue_replacements = {
                "说": "简短说明",
                "问": "追问",
                "喊": "喊了一声",
                "宣布": "说明了处理结果",
                "自嘲": "自嘲了一句",
                "回应": "简短回应",
            }
            text = re.sub(
                r"(说|问|喊|宣布|自嘲|回应)(?:道)?[：，]?\s*[‘“\"][^’”\"]+[’”\"]",
                lambda match: dialogue_replacements[match.group(1)] + "，",
                text,
            )
            text = re.sub(r"：\s*[‘“\"][^’”\"]+[’”\"]", "", text)
            text = re.sub(r"[，；：]+([。！？])", r"\1", text)
            text = re.sub(r"\s+([，。；：！？])", r"\1", text).strip(" ，；：")
            text = re.sub(r"([，。；：！？])\s+", r"\1", text)
            text = text.replace("，同时，", "。同时，")
            if len(text) <= limit:
                return text
            candidate = text[:limit]
            boundaries = sorted(
                (index for index, char in enumerate(candidate) if char in "。！？；，"),
                reverse=True,
            )
            dependent_endings = ("时", "后", "却", "但", "并", "而", "因为", "如果", "虽然", "同时")
            for boundary in boundaries:
                clause = candidate[:boundary].rstrip()
                if boundary >= limit // 2 and not clause.endswith(dependent_endings):
                    ending = candidate[boundary]
                    return clause + (ending if ending in "。！？" else "。")
            return candidate.rstrip("，；：") + "。"

        summary = plan.content_summary
        entry = "".join(part for part in (summary.cause, summary.development) if part)
        relationship = (
            plan.character_appearance.relationship_changes[0]
            if plan.character_appearance.relationship_changes
            else plan.plot_arrangement.emotion_line
        )
        lines = [
            f"标题: {plan.title}",
            f"目标字数: {plan.target_chars}",
            f"允许出场角色: {'、'.join(allowed_cast)}",
            f"写作目标: {short(plan.chapter_position + '；' + plan.target_emotion, 55)}",
            f"入场与发展: {short(entry, 100)}",
        ]
        if summary.turning_point:
            lines.append(f"局面转折: {short(summary.turning_point, 65)}")
        if summary.climax:
            lines.append(f"核心行动: {short(summary.climax, 65)}")
        elif plan.main_payoff:
            lines.append(f"核心行动: {short(plan.main_payoff, 65)}")
        if relationship:
            lines.append(f"关系落点: {short(relationship, 60)}")
        if summary.ending:
            lines.append(f"章末状态: {short(summary.ending, 65)}")
        ending = plan.ending_design
        if ending.next_chapter_push:
            lines.append(f"禁止提前展开: {short(ending.next_chapter_push, 40)}")
        return "\n".join(line for line in lines if not line.endswith(": "))
