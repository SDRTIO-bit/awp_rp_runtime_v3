"""RevisionRequest — request for Writer to revise a draft.

schemaId: awp.rp.revision-request.v1

Created when QualityPipeline returns 'revise'.
Contains the specific QualityIssues that must be fixed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .quality_issue import QualityIssue

SCHEMA_ID = "awp.rp.revision-request.v1"
SCHEMA_VERSION = 1


@dataclass
class RevisionRequest:
    """Request for Writer to revise a draft."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    request_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    writer_draft_id: str = ""

    # Revision details
    current_revision: int = 0
    max_revisions: int = 1

    # Issues to fix
    issues: list[QualityIssue] = field(default_factory=list)

    # Original text
    original_text: str = ""

    # Timestamp
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id,
            "writer_draft_id": self.writer_draft_id,
            "current_revision": self.current_revision,
            "max_revisions": self.max_revisions,
            "issues": [i.to_dict() for i in self.issues],
            "original_text": self.original_text,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RevisionRequest:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            request_id=data.get("request_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            writer_draft_id=data.get("writer_draft_id", ""),
            current_revision=data.get("current_revision", 0),
            max_revisions=data.get("max_revisions", 1),
            issues=[QualityIssue.from_dict(i) for i in data.get("issues", [])],
            original_text=data.get("original_text", ""),
            created_at=data.get("created_at", ""),
        )
