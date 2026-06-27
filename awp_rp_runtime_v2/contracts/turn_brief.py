"""TurnBrief — Director's structured output for the current turn.

schemaId: awp.rp.turn-brief.v1

Director produces this. It does NOT produce player-visible text.
Must NOT contain final RP prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.turn-brief.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class NarrativeGoal:
    goal_id: str = ""
    description: str = ""
    priority: float = 0.5
    category: str = ""  # plot | character | atmosphere | world


@dataclass
class TurnBrief:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    brief_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    card_id: str = ""
    session_id: str = ""
    base_card_state_revision: int = 0

    # Narrative intent
    turn_goal: str = ""
    player_intent: str = ""
    scene_summary: str = ""

    # Characters
    active_characters: list[str] = field(default_factory=list)
    relationship_tensions: list[str] = field(default_factory=list)

    # Facts
    known_facts: list[str] = field(default_factory=list)
    must_preserve_facts: list[str] = field(default_factory=list)
    must_not_do: list[str] = field(default_factory=list)

    # Opportunities and threads
    narrative_opportunities: list[str] = field(default_factory=list)
    unresolved_threads: list[str] = field(default_factory=list)

    # Guidance
    suggested_pacing: str = ""
    suggested_focus: str = ""
    risk_flags: list[str] = field(default_factory=list)
    writer_constraints: list[str] = field(default_factory=list)

    # Goals (backward compat)
    goals: list[NarrativeGoal] = field(default_factory=list)

    # Timestamps
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "brief_id": self.brief_id, "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id, "card_id": self.card_id,
            "session_id": self.session_id,
            "base_card_state_revision": self.base_card_state_revision,
            "turn_goal": self.turn_goal, "player_intent": self.player_intent,
            "scene_summary": self.scene_summary,
            "active_characters": self.active_characters,
            "relationship_tensions": self.relationship_tensions,
            "known_facts": self.known_facts,
            "must_preserve_facts": self.must_preserve_facts,
            "must_not_do": self.must_not_do,
            "narrative_opportunities": self.narrative_opportunities,
            "unresolved_threads": self.unresolved_threads,
            "suggested_pacing": self.suggested_pacing,
            "suggested_focus": self.suggested_focus,
            "risk_flags": self.risk_flags,
            "writer_constraints": self.writer_constraints,
            "goals": [{"goal_id": g.goal_id, "description": g.description,
                       "priority": g.priority, "category": g.category}
                      for g in self.goals],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TurnBrief:
        goals = [NarrativeGoal(**g) for g in data.get("goals", [])]
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            brief_id=data.get("brief_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            base_card_state_revision=data.get("base_card_state_revision", 0),
            turn_goal=data.get("turn_goal", ""),
            player_intent=data.get("player_intent", ""),
            scene_summary=data.get("scene_summary", ""),
            active_characters=data.get("active_characters", []),
            relationship_tensions=data.get("relationship_tensions", []),
            known_facts=data.get("known_facts", []),
            must_preserve_facts=data.get("must_preserve_facts", []),
            must_not_do=data.get("must_not_do", []),
            narrative_opportunities=data.get("narrative_opportunities", []),
            unresolved_threads=data.get("unresolved_threads", []),
            suggested_pacing=data.get("suggested_pacing", ""),
            suggested_focus=data.get("suggested_focus", ""),
            risk_flags=data.get("risk_flags", []),
            writer_constraints=data.get("writer_constraints", []),
            goals=goals,
            created_at=data.get("created_at", ""),
        )
