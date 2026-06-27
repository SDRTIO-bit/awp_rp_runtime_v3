"""ContinuityResult — result of continuity analysis.

schemaId: awp.rp.continuity-result.v1

Contains issues, conflicts, writer constraints, and director recommendations.
Cannot contain new facts, state modifications, timeline advances, or relationship changes.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .continuity_issue import ContinuityIssue
from .continuity_conflict import ContinuityConflict

SCHEMA_ID = "awp.rp.continuity-result.v1"
SCHEMA_VERSION = 1


class ContinuityStatus(str, Enum):
    SUCCESS = "success"
    NO_TRIGGER = "no_trigger"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass
class ContinuityResult:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    result_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    task_run_id: str = ""
    status: ContinuityStatus = ContinuityStatus.SUCCESS
    issues: list[ContinuityIssue] = field(default_factory=list)
    blocking_issues: list[ContinuityIssue] = field(default_factory=list)
    warnings: list[ContinuityIssue] = field(default_factory=list)
    informational_notes: list[ContinuityIssue] = field(default_factory=list)
    conflicts: list[ContinuityConflict] = field(default_factory=list)
    writer_constraints: list[str] = field(default_factory=list)
    director_recommendations: list[str] = field(default_factory=list)
    degraded_reasons: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "result_id": self.result_id, "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id, "task_run_id": self.task_run_id,
            "status": self.status.value,
            "issues": [i.to_dict() for i in self.issues],
            "blocking_issues": [i.to_dict() for i in self.blocking_issues],
            "warnings": [i.to_dict() for i in self.warnings],
            "informational_notes": [i.to_dict() for i in self.informational_notes],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "writer_constraints": self.writer_constraints,
            "director_recommendations": self.director_recommendations,
            "degraded_reasons": self.degraded_reasons,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContinuityResult:
        status_raw = data.get("status", "success")
        try:
            status = ContinuityStatus(status_raw)
        except ValueError:
            status = ContinuityStatus.SUCCESS
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            result_id=data.get("result_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            task_run_id=data.get("task_run_id", ""),
            status=status,
            issues=[ContinuityIssue.from_dict(i) for i in data.get("issues", [])],
            blocking_issues=[ContinuityIssue.from_dict(i) for i in data.get("blocking_issues", [])],
            warnings=[ContinuityIssue.from_dict(i) for i in data.get("warnings", [])],
            informational_notes=[ContinuityIssue.from_dict(i) for i in data.get("informational_notes", [])],
            conflicts=[ContinuityConflict.from_dict(c) for c in data.get("conflicts", [])],
            writer_constraints=data.get("writer_constraints", []),
            director_recommendations=data.get("director_recommendations", []),
            degraded_reasons=data.get("degraded_reasons", []),
            created_at=data.get("created_at", ""),
        )
