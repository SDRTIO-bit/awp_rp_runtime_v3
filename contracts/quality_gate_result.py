"""QualityGateResult — result of a single quality gate check.

schemaId: awp.rp.quality-gate-result.v1

Each gate (identity, scene, length, format) produces one of these.
They are aggregated by QualityAggregator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .quality_issue import QualityIssue

SCHEMA_ID = "awp.rp.quality-gate-result.v1"
SCHEMA_VERSION = 1


@dataclass
class QualityGateResult:
    """Result of a single quality gate check."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    gate_result_id: str = ""
    gate_name: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    writer_draft_id: str = ""

    # Result
    passed: bool = True
    issues: list[QualityIssue] = field(default_factory=list)

    # Metrics
    error_count: int = 0
    warning_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "gate_result_id": self.gate_result_id,
            "gate_name": self.gate_name,
            "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id,
            "writer_draft_id": self.writer_draft_id,
            "passed": self.passed,
            "issues": [i.to_dict() for i in self.issues],
            "error_count": self.error_count,
            "warning_count": self.warning_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualityGateResult:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            gate_result_id=data.get("gate_result_id", ""),
            gate_name=data.get("gate_name", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            writer_draft_id=data.get("writer_draft_id", ""),
            passed=data.get("passed", True),
            issues=[QualityIssue.from_dict(i) for i in data.get("issues", [])],
            error_count=data.get("error_count", 0),
            warning_count=data.get("warning_count", 0),
        )
