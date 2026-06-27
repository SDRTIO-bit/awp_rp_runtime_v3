"""ActiveMemoryProposal — proposed L2 changes from a Memory Curator.

schemaId: awp.rp.active-memory-proposal.v1

A proposal is NOT a write. Only the ActiveMemoryCommitRuntime may turn a
proposal into a committed record, and only after the gate accepts. In M1 the
proposal is produced by a deterministic fixture / FakeMemoryCurationAdapter —
the Memory Curator is NOT a free dynamic subagent yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .active_memory import ActiveMemoryRecord

SCHEMA_ID = "awp.rp.active-memory-proposal.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ActiveMemoryProposal:
    """Proposed new / updated / resolved active memories for one turn."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    turn_id: str = ""
    card_id: str = ""
    session_id: str = ""
    trace_id: str = ""

    new_entries: list[ActiveMemoryRecord] = field(default_factory=list)
    updated_entries: list[ActiveMemoryRecord] = field(default_factory=list)
    resolved_ids: list[str] = field(default_factory=list)

    # Why each change is proposed (write reasons for provenance)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "turn_id": self.turn_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "new_entries": [e.to_dict() for e in self.new_entries],
            "updated_entries": [e.to_dict() for e in self.updated_entries],
            "resolved_ids": list(self.resolved_ids),
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActiveMemoryProposal:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            turn_id=data.get("turn_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            trace_id=data.get("trace_id", ""),
            new_entries=[ActiveMemoryRecord.from_dict(e) for e in data.get("new_entries", [])],
            updated_entries=[ActiveMemoryRecord.from_dict(e) for e in data.get("updated_entries", [])],
            resolved_ids=list(data.get("resolved_ids", [])),
            reasons=list(data.get("reasons", [])),
        )
