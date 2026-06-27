"""MemoryEvidence — provenance evidence for a memory record.

schemaId: awp.rp.memory-evidence.v1

Every memory must be traceable to a source turn, a CardState revision, and a
write reason. This contract captures that provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.memory-evidence.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MemoryEvidence:
    """Provenance evidence binding a memory to its source turn & state revision."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    source_turn_id: str = ""
    source_snapshot_id: str = ""
    source_card_state_revision: int = 0
    trace_id: str = ""
    memory_commit_id: str = ""
    write_reason: str = ""  # why this memory was written (e.g. "promise_made")
    quote: str = ""  # optional short evidence quote from accepted output

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "source_turn_id": self.source_turn_id,
            "source_snapshot_id": self.source_snapshot_id,
            "source_card_state_revision": self.source_card_state_revision,
            "trace_id": self.trace_id,
            "memory_commit_id": self.memory_commit_id,
            "write_reason": self.write_reason,
            "quote": self.quote,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEvidence:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            source_turn_id=data.get("source_turn_id", ""),
            source_snapshot_id=data.get("source_snapshot_id", ""),
            source_card_state_revision=data.get("source_card_state_revision", 0),
            trace_id=data.get("trace_id", ""),
            memory_commit_id=data.get("memory_commit_id", ""),
            write_reason=data.get("write_reason", ""),
            quote=data.get("quote", ""),
        )
