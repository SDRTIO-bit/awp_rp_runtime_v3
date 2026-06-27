"""DirectorPlan — Director's structured output for the current turn.

schemaId: awp.rp.director-plan.v1

Director produces this after reading RoundSnapshot.
DirectorPlan is the formal contract between Director and all downstream consumers.
Director does NOT produce player-visible text, write state, or write memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.director-plan.v1"
SCHEMA_VERSION = 1


@dataclass
class DirectorPlan:
    """Director's structured plan for the current turn.

    Director reads RoundSnapshot and produces this plan.
    Director does NOT produce final player text, write state, or write memory.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    plan_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    card_id: str = ""
    session_id: str = ""

    # Core narrative decisions
    player_intent: str = ""
    turn_goal: str = ""
    scene_focus: str = ""

    # Characters
    active_character_refs: list[str] = field(default_factory=list)
    relationship_tensions: list[str] = field(default_factory=list)

    # Facts
    base_card_state_revision: int = 0
    must_preserve_facts: list[str] = field(default_factory=list)
    must_not_do: list[str] = field(default_factory=list)

    # Opportunities and threads
    narrative_opportunities: list[str] = field(default_factory=list)
    unresolved_threads: list[str] = field(default_factory=list)

    # Pacing
    pacing_guidance: str = ""

    # Writer constraints (structured, not prose)
    writer_constraints: list[str] = field(default_factory=list)

    # References to downstream plans
    tool_plan_ref: str = ""
    delegation_plan_ref: str = ""

    # Risk
    risk_flags: list[str] = field(default_factory=list)

    # Timestamp
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "player_intent": self.player_intent,
            "turn_goal": self.turn_goal,
            "scene_focus": self.scene_focus,
            "active_character_refs": self.active_character_refs,
            "relationship_tensions": self.relationship_tensions,
            "base_card_state_revision": self.base_card_state_revision,
            "must_preserve_facts": self.must_preserve_facts,
            "must_not_do": self.must_not_do,
            "narrative_opportunities": self.narrative_opportunities,
            "unresolved_threads": self.unresolved_threads,
            "pacing_guidance": self.pacing_guidance,
            "writer_constraints": self.writer_constraints,
            "tool_plan_ref": self.tool_plan_ref,
            "delegation_plan_ref": self.delegation_plan_ref,
            "risk_flags": self.risk_flags,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DirectorPlan:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            plan_id=data.get("plan_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            player_intent=data.get("player_intent", ""),
            turn_goal=data.get("turn_goal", ""),
            scene_focus=data.get("scene_focus", ""),
            active_character_refs=data.get("active_character_refs", []),
            relationship_tensions=data.get("relationship_tensions", []),
            base_card_state_revision=data.get("base_card_state_revision", 0),
            must_preserve_facts=data.get("must_preserve_facts", []),
            must_not_do=data.get("must_not_do", []),
            narrative_opportunities=data.get("narrative_opportunities", []),
            unresolved_threads=data.get("unresolved_threads", []),
            pacing_guidance=data.get("pacing_guidance", ""),
            writer_constraints=data.get("writer_constraints", []),
            tool_plan_ref=data.get("tool_plan_ref", ""),
            delegation_plan_ref=data.get("delegation_plan_ref", ""),
            risk_flags=data.get("risk_flags", []),
            created_at=data.get("created_at", ""),
        )
