"""CardImportIssue — a structured issue found during card import.

schemaId: awp.rp.card-import-issue.v1

Each issue captures a single finding from the import pipeline.
Issues are aggregated into the CardImportReport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-import-issue.v1"
SCHEMA_VERSION = 1


class IssueSeverity:
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class IssueCategory:
    FORMAT = "format"
    SECURITY = "security"
    CONTENT = "content"
    WORLDBOOK = "worldbook"
    GREETING = "greeting"
    VARIABLE = "variable"
    STRUCTURE = "structure"
    QUARANTINE = "quarantine"


@dataclass(frozen=True)
class CardImportIssue:
    """A structured issue found during card import."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    issue_id: str = ""
    severity: str = IssueSeverity.INFO
    category: str = IssueCategory.FORMAT
    message: str = ""
    source_path: str = ""
    evidence_preview: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "issue_id": self.issue_id,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "source_path": self.source_path,
            "evidence_preview": self.evidence_preview,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardImportIssue:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            issue_id=data.get("issue_id", ""),
            severity=data.get("severity", IssueSeverity.INFO),
            category=data.get("category", IssueCategory.FORMAT),
            message=data.get("message", ""),
            source_path=data.get("source_path", ""),
            evidence_preview=data.get("evidence_preview", ""),
        )
