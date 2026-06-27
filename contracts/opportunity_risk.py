"""OpportunityRisk — risk assessment for opportunity candidates.

schemaId: awp.rp.opportunity-risk.v1
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.opportunity-risk.v1"
SCHEMA_VERSION = 1

class OpportunityRiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class OpportunityRisk:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    risk_id: str = ""
    risk_level: OpportunityRiskLevel = OpportunityRiskLevel.NONE
    description: str = ""
    entity_refs: list[str] = field(default_factory=list)
    violated_policy: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "risk_id": self.risk_id, "risk_level": self.risk_level.value,
            "description": self.description, "entity_refs": self.entity_refs,
            "violated_policy": self.violated_policy, "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpportunityRisk:
        level_raw = data.get("risk_level", "none")
        try:
            level = OpportunityRiskLevel(level_raw)
        except ValueError:
            level = OpportunityRiskLevel.NONE
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            risk_id=data.get("risk_id", ""),
            risk_level=level,
            description=data.get("description", ""),
            entity_refs=data.get("entity_refs", []),
            violated_policy=data.get("violated_policy", ""),
            created_at=data.get("created_at", ""),
        )
