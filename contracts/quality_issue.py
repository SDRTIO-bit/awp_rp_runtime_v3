"""QualityIssue — a structured quality issue found by a gate.

schemaId: awp.rp.quality-issue.v1

Each gate produces a list of these. They are aggregated
by QualityAggregator into an AggregateQualityDecision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.quality-issue.v1"
SCHEMA_VERSION = 1


class IssueSeverity:
    ERROR = "error"      # Must fix, blocks accept
    WARNING = "warning"  # Should fix, may trigger revise
    INFO = "info"        # Informational only


class IssueCategory:
    IDENTITY = "identity"
    SCENE = "scene"
    PLAYER_AGENCY = "player_agency"
    FACT_PRESERVATION = "fact_preservation"
    PROHIBITED_ACTION = "prohibited_action"
    LENGTH = "length"
    FORMAT = "format"
    CONTENT_LEAK = "content_leak"


@dataclass
class QualityIssue:
    """A structured quality issue found by a gate."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    issue_id: str = ""
    gate_name: str = ""

    # Issue details
    category: str = ""
    severity: str = IssueSeverity.ERROR
    description: str = ""
    evidence: str = ""  # Specific text or data that triggered this issue

    # Resolution
    fixable: bool = True
    fix_guidance: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "issue_id": self.issue_id,
            "gate_name": self.gate_name,
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "evidence": self.evidence,
            "fixable": self.fixable,
            "fix_guidance": self.fix_guidance,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityIssue:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            issue_id=data.get("issue_id", ""),
            gate_name=data.get("gate_name", ""),
            category=data.get("category", ""),
            severity=data.get("severity", IssueSeverity.ERROR),
            description=data.get("description", ""),
            evidence=data.get("evidence", ""),
            fixable=data.get("fixable", True),
            fix_guidance=data.get("fix_guidance", ""),
        )
