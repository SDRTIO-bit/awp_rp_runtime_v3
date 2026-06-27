"""ContinuityConflict — conflict between evidence sources.

schemaId: awp.rp.continuity-conflict.v1

Records when two evidence sources disagree on the same fact.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.continuity-conflict.v1"
SCHEMA_VERSION = 1


class ConflictResolution(str, Enum):
    HIGHER_PRIORITY_WINS = "higher_priority_wins"
    CARD_STATE_AUTHORITY = "card_state_authority"
    REJECTED_LOW_PRIORITY = "rejected_low_priority"
    UNRESOLVED = "unresolved"


@dataclass
class ContinuityConflict:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    conflict_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    higher_priority_evidence_id: str = ""
    lower_priority_evidence_id: str = ""
    higher_priority_source: str = ""
    lower_priority_source: str = ""
    fact_description: str = ""
    resolution: ConflictResolution = ConflictResolution.UNRESOLVED
    resolution_reason: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "conflict_id": self.conflict_id, "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id,
            "higher_priority_evidence_id": self.higher_priority_evidence_id,
            "lower_priority_evidence_id": self.lower_priority_evidence_id,
            "higher_priority_source": self.higher_priority_source,
            "lower_priority_source": self.lower_priority_source,
            "fact_description": self.fact_description,
            "resolution": self.resolution.value,
            "resolution_reason": self.resolution_reason,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContinuityConflict:
        res_raw = data.get("resolution", "unresolved")
        try:
            resolution = ConflictResolution(res_raw)
        except ValueError:
            resolution = ConflictResolution.UNRESOLVED
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            conflict_id=data.get("conflict_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            higher_priority_evidence_id=data.get("higher_priority_evidence_id", ""),
            lower_priority_evidence_id=data.get("lower_priority_evidence_id", ""),
            higher_priority_source=data.get("higher_priority_source", ""),
            lower_priority_source=data.get("lower_priority_source", ""),
            fact_description=data.get("fact_description", ""),
            resolution=resolution,
            resolution_reason=data.get("resolution_reason", ""),
            created_at=data.get("created_at", ""),
        )
