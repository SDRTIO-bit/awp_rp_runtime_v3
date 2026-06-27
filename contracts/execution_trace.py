"""ExecutionTrace — audit trail for the entire turn.

schemaId: awp.rp.execution-trace.v1

Every action in a turn leaves a trace. This is for debugging,
replay, and compliance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.execution-trace.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class TraceEvent:
    """A single trace event."""
    event_id: str = ""
    event_type: str = ""  # snapshot_built | director_called | delegation_planned | subagent_called | suggestions_merged | writer_called | quality_checked | state_proposed | state_committed | turn_committed | memory_committed
    timestamp: str = ""
    actor: str = ""  # Which runtime/agent produced this
    duration_ms: int = 0
    details: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str | None = None


@dataclass
class ExecutionTrace:
    """Complete audit trail for a turn.

    Every action leaves a trace. Used for debugging, replay, and compliance.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    trace_id: str = ""
    turn_id: str = ""
    card_id: str = ""
    session_id: str = ""

    # Events in chronological order
    events: list[TraceEvent] = field(default_factory=list)

    # Summary
    total_duration_ms: int = 0
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    success: bool = True

    def add_event(self, event: TraceEvent) -> None:
        self.events.append(event)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "events": [
                {
                    "event_id": e.event_id, "event_type": e.event_type,
                    "timestamp": e.timestamp, "actor": e.actor,
                    "duration_ms": e.duration_ms, "details": e.details,
                    "success": e.success, "error": e.error,
                }
                for e in self.events
            ],
            "total_duration_ms": self.total_duration_ms,
            "total_llm_calls": self.total_llm_calls,
            "total_tool_calls": self.total_tool_calls,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionTrace:
        events = []
        for e_data in data.get("events", []):
            events.append(TraceEvent(**e_data))
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            trace_id=data.get("trace_id", ""),
            turn_id=data.get("turn_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            events=events,
            total_duration_ms=data.get("total_duration_ms", 0),
            total_llm_calls=data.get("total_llm_calls", 0),
            total_tool_calls=data.get("total_tool_calls", 0),
            success=data.get("success", True),
        )
