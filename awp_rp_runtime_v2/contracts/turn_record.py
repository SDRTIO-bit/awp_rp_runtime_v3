"""TurnRecord — the formal turn ledger, not chat history.

schemaId: awp.rp.turn-record.v1

A TurnRecord is written ONLY after QualityGate accepts.
It binds the CardState revision before and after commit.
It can replay the entire turn's state transitions.
It never stores raw model chain-of-thought or system prompts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.turn-record.v1"
SCHEMA_VERSION = 1


class TurnMode(str, Enum):
    """Mode of the turn."""
    NORMAL = "normal"
    CONTINUE = "continue"
    RETRY = "retry"


@dataclass
class TurnRecord:
    """Complete record of one accepted turn.

    Written only after QualityGate accept.
    Binds baseCardStateRevision → resultCardStateRevision.
    turnIndex is strictly increasing within cardId+sessionId.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    turn_id: str = ""
    trace_id: str = ""
    card_id: str = ""
    session_id: str = ""

    # Turn ordering
    turn_index: int = 0
    parent_turn_id: str = ""  # For retry: which turn this retries

    # Mode
    mode: TurnMode = TurnMode.NORMAL

    # Input
    player_input: str = ""

    # References to execution artifacts (stored as JSON refs or inline)
    round_snapshot_ref: str = ""  # snapshot_id
    director_brief_ref: str = ""
    delegation_plan_ref: str = ""
    suggestion_merge_ref: str = ""

    # Accepted output
    writer_output: str = ""

    # Quality gate
    quality_decision_ref: str = ""  # trace_id from QualityDecision

    # State commit binding
    state_commit_ref: str = ""  # patch_id
    base_card_state_revision: int = 0
    result_card_state_revision: int = 0

    # Memory commit refs
    memory_commit_refs: list[str] = field(default_factory=list)

    # Timestamps
    created_at: str = ""
    accepted_at: str = ""

    # Audit (no raw CoT, no system prompts)
    execution_trace_summary: dict[str, Any] = field(default_factory=dict)
    tool_summaries: list[dict[str, Any]] = field(default_factory=list)
    subagent_summaries: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "turn_id": self.turn_id,
            "trace_id": self.trace_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "turn_index": self.turn_index,
            "parent_turn_id": self.parent_turn_id,
            "mode": self.mode.value,
            "player_input": self.player_input,
            "round_snapshot_ref": self.round_snapshot_ref,
            "director_brief_ref": self.director_brief_ref,
            "delegation_plan_ref": self.delegation_plan_ref,
            "suggestion_merge_ref": self.suggestion_merge_ref,
            "writer_output": self.writer_output,
            "quality_decision_ref": self.quality_decision_ref,
            "state_commit_ref": self.state_commit_ref,
            "base_card_state_revision": self.base_card_state_revision,
            "result_card_state_revision": self.result_card_state_revision,
            "memory_commit_refs": self.memory_commit_refs,
            "created_at": self.created_at,
            "accepted_at": self.accepted_at,
            "execution_trace_summary": self.execution_trace_summary,
            "tool_summaries": self.tool_summaries,
            "subagent_summaries": self.subagent_summaries,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TurnRecord:
        mode_raw = data.get("mode", "normal")
        mode = TurnMode(mode_raw) if mode_raw in [m.value for m in TurnMode] else TurnMode.NORMAL

        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            turn_id=data.get("turn_id", ""),
            trace_id=data.get("trace_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            turn_index=data.get("turn_index", 0),
            parent_turn_id=data.get("parent_turn_id", ""),
            mode=mode,
            player_input=data.get("player_input", ""),
            round_snapshot_ref=data.get("round_snapshot_ref", ""),
            director_brief_ref=data.get("director_brief_ref", ""),
            delegation_plan_ref=data.get("delegation_plan_ref", ""),
            suggestion_merge_ref=data.get("suggestion_merge_ref", ""),
            writer_output=data.get("writer_output", ""),
            quality_decision_ref=data.get("quality_decision_ref", ""),
            state_commit_ref=data.get("state_commit_ref", ""),
            base_card_state_revision=data.get("base_card_state_revision", 0),
            result_card_state_revision=data.get("result_card_state_revision", 0),
            memory_commit_refs=data.get("memory_commit_refs", []),
            created_at=data.get("created_at", ""),
            accepted_at=data.get("accepted_at", ""),
            execution_trace_summary=data.get("execution_trace_summary", {}),
            tool_summaries=data.get("tool_summaries", []),
            subagent_summaries=data.get("subagent_summaries", []),
            evidence=data.get("evidence", []),
        )
