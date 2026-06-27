"""RevisionResult — result of a revision attempt.

schemaId: awp.rp.revision-result.v1

Produced by Reviser after attempting to fix QualityIssues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.revision-result.v1"
SCHEMA_VERSION = 1


@dataclass
class RevisionResult:
    """Result of a revision attempt."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    result_id: str = ""
    request_id: str = ""
    trace_id: str = ""

    # Result
    revised_text: str = ""
    revision_number: int = 0
    success: bool = False

    # What was fixed
    issues_addressed: list[str] = field(default_factory=list)
    issues_remaining: list[str] = field(default_factory=list)

    # Timestamp
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "revised_text": self.revised_text,
            "revision_number": self.revision_number,
            "success": self.success,
            "issues_addressed": self.issues_addressed,
            "issues_remaining": self.issues_remaining,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RevisionResult:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            result_id=data.get("result_id", ""),
            request_id=data.get("request_id", ""),
            trace_id=data.get("trace_id", ""),
            revised_text=data.get("revised_text", ""),
            revision_number=data.get("revision_number", 0),
            success=data.get("success", False),
            issues_addressed=data.get("issues_addressed", []),
            issues_remaining=data.get("issues_remaining", []),
            created_at=data.get("created_at", ""),
        )
