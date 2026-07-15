"""Contracts for private NPC agendas and their public consequences."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, field_validator


_FACT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class VisibleConsequence(BaseModel):
    """The writer-visible result of a private NPC agenda."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agenda_id: str
    beat_id: str
    observable_event: str
    observable_clue: str
    affected_characters: tuple[str, ...]


class NpcAgenda(BaseModel):
    """A private NPC plan, including the safe consequence exposed downstream."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    agenda_id: str
    thread_key: str
    npc: str
    private_goal: str
    known_fact_ids: tuple[str, ...]
    resources: tuple[str, ...]
    cost: str
    next_action: str
    trigger: str
    risk: str
    visible_consequence: VisibleConsequence
    deadline: str

    @field_validator("known_fact_ids")
    @classmethod
    def known_fact_ids_must_be_identifiers(cls, fact_ids: tuple[str, ...]) -> tuple[str, ...]:
        """Keep private agenda inputs as references, never embedded fact content."""

        if any(not _FACT_ID_PATTERN.fullmatch(fact_id) for fact_id in fact_ids):
            raise ValueError("known_fact_ids must contain fact identifiers only")
        return fact_ids
