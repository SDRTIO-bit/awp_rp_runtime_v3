"""CuratorRequest — input for TurnEvolutionCurator.

schemaId: awp.rp.curator-request.v1

All context the curator needs to produce a TurnEvolutionProposal.
Read-only input — curator cannot write to any store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.curator-request.v1"
SCHEMA_VERSION = 1


@dataclass
class CuratorRequest:
    """Input for the TurnEvolutionCurator.

    Contains all context needed to propose state changes, memory candidates,
    and event/relationship summaries. Read-only.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    request_id: str = ""
    turn_id: str = ""
    session_id: str = ""
    trace_id: str = ""

    # Turn content (the accepted text)
    player_input: str = ""
    accepted_writer_output: str = ""

    # Pre-turn state
    pre_turn_card_state: dict[str, Any] = field(default_factory=dict)

    # Director's plan for this turn
    final_turn_brief: dict[str, Any] = field(default_factory=dict)

    # Recent turns (L1, most recent first)
    recent_turns: list[dict[str, Any]] = field(default_factory=list)

    # Active memory snapshot (L2)
    active_memory: list[dict[str, Any]] = field(default_factory=list)

    # Resolved worldbook context
    resolved_worldbook_context: list[dict[str, Any]] = field(default_factory=list)

    # Agent suggestions (from D1-D5)
    agent_suggestions: list[dict[str, Any]] = field(default_factory=list)

    # Turn metadata
    turn_kind: str = ""  # "first" or "continuation"
    base_card_state_revision: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "turn_id": self.turn_id,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "player_input": self.player_input,
            "accepted_writer_output": self.accepted_writer_output,
            "pre_turn_card_state": dict(self.pre_turn_card_state),
            "final_turn_brief": dict(self.final_turn_brief),
            "recent_turns": list(self.recent_turns),
            "active_memory": list(self.active_memory),
            "resolved_worldbook_context": list(self.resolved_worldbook_context),
            "agent_suggestions": list(self.agent_suggestions),
            "turn_kind": self.turn_kind,
            "base_card_state_revision": self.base_card_state_revision,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CuratorRequest:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            request_id=data.get("request_id", ""),
            turn_id=data.get("turn_id", ""),
            session_id=data.get("session_id", ""),
            trace_id=data.get("trace_id", ""),
            player_input=data.get("player_input", ""),
            accepted_writer_output=data.get("accepted_writer_output", ""),
            pre_turn_card_state=data.get("pre_turn_card_state", {}),
            final_turn_brief=data.get("final_turn_brief", {}),
            recent_turns=data.get("recent_turns", []),
            active_memory=data.get("active_memory", []),
            resolved_worldbook_context=data.get("resolved_worldbook_context", []),
            agent_suggestions=data.get("agent_suggestions", []),
            turn_kind=data.get("turn_kind", ""),
            base_card_state_revision=data.get("base_card_state_revision", 0),
        )
