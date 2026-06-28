"""First Turn Context -- assembled context for Director/Writer in first formal turn."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.first-turn-context.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class OpeningContext:
    """Controlled projection of OpeningRecord for Writer consumption.

    OpeningContext is NOT a TurnRecord. It provides the greeting context
    without allowing Writer to confuse it with a previous turn output.
    """

    schema_id: str = "awp.rp.opening-context.v1"
    schema_version: int = 1
    opening_record_id: str = ""
    greeting_id: str = ""
    safe_display_content: str = ""
    source_greeting_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "opening_record_id": self.opening_record_id,
            "greeting_id": self.greeting_id,
            "safe_display_content": self.safe_display_content,
            "source_greeting_ref": self.source_greeting_ref,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpeningContext:
        return cls(
            schema_id=data.get("schema_id", "awp.rp.opening-context.v1"),
            schema_version=data.get("schema_version", 1),
            opening_record_id=data.get("opening_record_id", ""),
            greeting_id=data.get("greeting_id", ""),
            safe_display_content=data.get("safe_display_content", ""),
            source_greeting_ref=data.get("source_greeting_ref", ""),
        )


@dataclass(frozen=True)
class SessionBoundWorldbookRetrievalResult:
    """Result of session-bound worldbook retrieval.

    All entry references are scoped to the current Session's WorldbookBinding.
    Never reads from global card library or other sessions.
    """

    schema_id: str = "awp.rp.session-bound-worldbook-retrieval-result.v1"
    schema_version: int = 1
    retrieval_id: str = ""
    session_id: str = ""
    worldbook_binding_id: str = ""
    candidate_entry_ids: list[str] = field(default_factory=list)
    activated_entry_ids: list[str] = field(default_factory=list)
    rejected_entry_ids_with_reasons: dict[str, str] = field(default_factory=dict)
    deferred_entry_ids: list[str] = field(default_factory=list)
    disabled_entry_ids: list[str] = field(default_factory=list)
    budget_dropped_entry_ids: list[str] = field(default_factory=list)
    branch_selections: list[dict[str, Any]] = field(default_factory=list)
    chunk_parent_entry_ids: list[str] = field(default_factory=list)
    activated_content: list[dict[str, Any]] = field(default_factory=list)
    total_budget_used: int = 0
    max_budget: int = 4000
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "retrieval_id": self.retrieval_id,
            "session_id": self.session_id,
            "worldbook_binding_id": self.worldbook_binding_id,
            "candidate_entry_ids": list(self.candidate_entry_ids),
            "activated_entry_ids": list(self.activated_entry_ids),
            "rejected_entry_ids_with_reasons": dict(self.rejected_entry_ids_with_reasons),
            "deferred_entry_ids": list(self.deferred_entry_ids),
            "disabled_entry_ids": list(self.disabled_entry_ids),
            "budget_dropped_entry_ids": list(self.budget_dropped_entry_ids),
            "branch_selections": list(self.branch_selections),
            "chunk_parent_entry_ids": list(self.chunk_parent_entry_ids),
            "activated_content": list(self.activated_content),
            "total_budget_used": self.total_budget_used,
            "max_budget": self.max_budget,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionBoundWorldbookRetrievalResult:
        return cls(
            schema_id=data.get("schema_id", "awp.rp.session-bound-worldbook-retrieval-result.v1"),
            schema_version=data.get("schema_version", 1),
            retrieval_id=data.get("retrieval_id", ""),
            session_id=data.get("session_id", ""),
            worldbook_binding_id=data.get("worldbook_binding_id", ""),
            candidate_entry_ids=list(data.get("candidate_entry_ids", [])),
            activated_entry_ids=list(data.get("activated_entry_ids", [])),
            rejected_entry_ids_with_reasons=dict(data.get("rejected_entry_ids_with_reasons", {})),
            deferred_entry_ids=list(data.get("deferred_entry_ids", [])),
            disabled_entry_ids=list(data.get("disabled_entry_ids", [])),
            budget_dropped_entry_ids=list(data.get("budget_dropped_entry_ids", [])),
            branch_selections=list(data.get("branch_selections", [])),
            chunk_parent_entry_ids=list(data.get("chunk_parent_entry_ids", [])),
            activated_content=list(data.get("activated_content", [])),
            total_budget_used=data.get("total_budget_used", 0),
            max_budget=data.get("max_budget", 4000),
            created_at=data.get("created_at", ""),
        )


@dataclass(frozen=True)
class FirstTurnContext:
    """Complete assembled context for the first formal RP turn.

    Contains all inputs needed by Director and Writer for turn execution.
    recentAcceptedTurns is intentionally empty for the first turn.
    activeMemories and ragRecall are intentionally empty for the first turn.
    """

    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    context_id: str = ""
    trace_id: str = ""
    session_id: str = ""
    logical_card_id: str = ""
    card_version: int = 0
    source_hash: str = ""
    # Session binding reference
    card_session_binding_id: str = ""
    # CardState at turn start
    card_state_revision: int = 0
    card_state: dict[str, Any] = field(default_factory=dict)
    # Opening context (NOT a TurnRecord)
    opening_context: dict[str, Any] = field(default_factory=dict)
    # Player input
    player_input: str = ""
    # Worldbook retrieval
    worldbook_retrieval: dict[str, Any] = field(default_factory=dict)
    # RoundSnapshot reference
    round_snapshot_id: str = ""
    round_snapshot: dict[str, Any] = field(default_factory=dict)
    # First turn markers
    is_first_turn: bool = True
    recent_accepted_turn_count: int = 0
    active_memory_count: int = 0
    rag_recall_count: int = 0
    # Trace correlation
    workflow_run_id: str = ""
    turn_id: str = ""
    attempt_id: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "context_id": self.context_id,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "logical_card_id": self.logical_card_id,
            "card_version": self.card_version,
            "source_hash": self.source_hash,
            "card_session_binding_id": self.card_session_binding_id,
            "card_state_revision": self.card_state_revision,
            "card_state": dict(self.card_state),
            "opening_context": dict(self.opening_context),
            "player_input": self.player_input,
            "worldbook_retrieval": dict(self.worldbook_retrieval),
            "round_snapshot_id": self.round_snapshot_id,
            "round_snapshot": dict(self.round_snapshot),
            "is_first_turn": self.is_first_turn,
            "recent_accepted_turn_count": self.recent_accepted_turn_count,
            "active_memory_count": self.active_memory_count,
            "rag_recall_count": self.rag_recall_count,
            "workflow_run_id": self.workflow_run_id,
            "turn_id": self.turn_id,
            "attempt_id": self.attempt_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FirstTurnContext:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            context_id=data.get("context_id", ""),
            trace_id=data.get("trace_id", ""),
            session_id=data.get("session_id", ""),
            logical_card_id=data.get("logical_card_id", ""),
            card_version=data.get("card_version", 0),
            source_hash=data.get("source_hash", ""),
            card_session_binding_id=data.get("card_session_binding_id", ""),
            card_state_revision=data.get("card_state_revision", 0),
            card_state=dict(data.get("card_state", {})),
            opening_context=dict(data.get("opening_context", {})),
            player_input=data.get("player_input", ""),
            worldbook_retrieval=dict(data.get("worldbook_retrieval", {})),
            round_snapshot_id=data.get("round_snapshot_id", ""),
            round_snapshot=dict(data.get("round_snapshot", {})),
            is_first_turn=data.get("is_first_turn", True),
            recent_accepted_turn_count=data.get("recent_accepted_turn_count", 0),
            active_memory_count=data.get("active_memory_count", 0),
            rag_recall_count=data.get("rag_recall_count", 0),
            workflow_run_id=data.get("workflow_run_id", ""),
            turn_id=data.get("turn_id", ""),
            attempt_id=data.get("attempt_id", ""),
            created_at=data.get("created_at", ""),
        )
