"""WriterDraft — Writer's output for quality review.

schemaId: awp.rp.writer-draft.v1

Writer produces this. It is NOT a state update, NOT a memory write,
NOT a tool result. It is pure narrative text for quality review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.writer-draft.v1"
SCHEMA_VERSION = 1


@dataclass
class WriterDraft:
    """Writer's output for quality review.

    Writer produces this from WriterInputBundle.
    It contains ONLY player-visible RP text.
    No JSON, no debug info, no system statements, no tool call text.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    draft_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    writer_input_bundle_id: str = ""

    # The narrative text
    text: str = ""

    # Metadata
    character_count: int = 0
    revision_number: int = 0  # 0 = first draft, 1+ = revisions

    # Timestamp
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "draft_id": self.draft_id,
            "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id,
            "writer_input_bundle_id": self.writer_input_bundle_id,
            "text": self.text,
            "character_count": self.character_count,
            "revision_number": self.revision_number,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WriterDraft:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            draft_id=data.get("draft_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            writer_input_bundle_id=data.get("writer_input_bundle_id", ""),
            text=data.get("text", ""),
            character_count=data.get("character_count", 0),
            revision_number=data.get("revision_number", 0),
            created_at=data.get("created_at", ""),
        )
