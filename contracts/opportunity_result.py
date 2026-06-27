"""OpportunityResult — result of opportunity analysis.

schemaId: awp.rp.opportunity-result.v1
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .opportunity_candidate import OpportunityCandidate

SCHEMA_ID = "awp.rp.opportunity-result.v1"
SCHEMA_VERSION = 1

class OpportunityStatus(str, Enum):
    SUCCESS = "success"
    NO_TRIGGER = "no_trigger"
    DEGRADED = "degraded"
    FAILED = "failed"

@dataclass
class RejectedCandidate:
    candidate_id: str = ""
    reason: str = ""
    violated_policy: str = ""
    evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id, "reason": self.reason,
            "violated_policy": self.violated_policy,
            "evidence_refs": self.evidence_refs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RejectedCandidate:
        return cls(
            candidate_id=data.get("candidate_id", ""),
            reason=data.get("reason", ""),
            violated_policy=data.get("violated_policy", ""),
            evidence_refs=data.get("evidence_refs", []),
        )

@dataclass
class OpportunityResult:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    result_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    task_run_id: str = ""
    status: OpportunityStatus = OpportunityStatus.SUCCESS
    candidates: list[OpportunityCandidate] = field(default_factory=list)
    rejected_candidates: list[RejectedCandidate] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    degraded_reasons: list[str] = field(default_factory=list)
    recommended_opportunity_ids: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "result_id": self.result_id, "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id, "task_run_id": self.task_run_id,
            "status": self.status.value,
            "candidates": [c.to_dict() for c in self.candidates],
            "rejected_candidates": [r.to_dict() for r in self.rejected_candidates],
            "conflicts": self.conflicts,
            "degraded_reasons": self.degraded_reasons,
            "recommended_opportunity_ids": self.recommended_opportunity_ids,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpportunityResult:
        status_raw = data.get("status", "success")
        try:
            status = OpportunityStatus(status_raw)
        except ValueError:
            status = OpportunityStatus.SUCCESS
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            result_id=data.get("result_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            task_run_id=data.get("task_run_id", ""),
            status=status,
            candidates=[OpportunityCandidate.from_dict(c) for c in data.get("candidates", [])],
            rejected_candidates=[RejectedCandidate.from_dict(r) for r in data.get("rejected_candidates", [])],
            conflicts=data.get("conflicts", []),
            degraded_reasons=data.get("degraded_reasons", []),
            recommended_opportunity_ids=data.get("recommended_opportunity_ids", []),
            created_at=data.get("created_at", ""),
        )
