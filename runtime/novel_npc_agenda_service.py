"""Deterministic selection and lifecycle rules for autonomous NPC agendas."""

from __future__ import annotations

import json
from dataclasses import replace

from ..contracts.novel_npc_agenda import NpcAgenda


MAX_ACTIVE_AGENDAS = 8
MAX_CANDIDATE_NPCS = 5


class NpcAgendaService:
    def active(self, items, chapter_index: int):
        agendas = []
        updates = []
        for item in items:
            if item.section != "npc_agenda" or item.status not in {"active", "advanced"}:
                continue
            try:
                agenda = NpcAgenda.model_validate(json.loads(item.content))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            deadline = _deadline_index(agenda.deadline)
            if deadline is not None and deadline < chapter_index:
                updates.append(replace(item, status="stale"))
            else:
                agendas.append(agenda)
        return tuple(agendas[:MAX_ACTIVE_AGENDAS]), tuple(updates)

    def eligible_characters(self, characters, plan, chapter_index: int):
        text = " ".join((plan.title, plan.content_summary.cause, plan.content_summary.development))
        related = [
            character for character in characters
            if character.first_appearance and character.first_appearance <= chapter_index
            and (
                character.name in text
                or (character.core_motivation and character.core_motivation in text)
            )
        ]
        return tuple(sorted(related, key=lambda c: (c.first_appearance, c.name))[:MAX_CANDIDATE_NPCS])


def _deadline_index(value: str) -> int | None:
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None
