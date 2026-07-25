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
            visible_consequences=(
                director_guidance.visible_consequences
                or tuple(
                    action.visible_consequence
                    for action in getattr(
                        director_guidance, "selected_npc_actions", ()
                    )
                )
            ),
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
        """Build a lightweight chapter brief — events and direction, not a template."""

        summary = plan.content_summary
        parts = [f"【本章】{plan.title}　情绪基调：{plan.target_emotion}"]

        if plan.opening_hook:
            parts.append(f"开篇切入点：{plan.opening_hook}")

        cause_dev = "".join(p for p in (summary.cause, summary.development) if p)
        if cause_dev:
            parts.append(f"事件：{cause_dev}")

        if summary.turning_point:
            parts.append(f"转折：{summary.turning_point}")

        if summary.climax:
            parts.append(f"核心场面：{summary.climax}")
        elif plan.main_payoff:
            parts.append(f"核心场面：{plan.main_payoff}")

        if summary.ending:
            parts.append(f"收尾方向：{summary.ending}")

        return "\n".join(parts)
