"""ContinuityRisk — a detected risk to narrative continuity.

schemaId: awp.rp.continuity-risk.v1

Identifies conflicts, ambiguities, or missing information that could
break narrative continuity if not addressed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.continuity-risk.v1"
SCHEMA_VERSION = 1


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ContinuityRisk:
    """A detected risk to narrative continuity."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    risk_id: str = ""
    risk_level: RiskLevel = RiskLevel.NONE
    description: str = ""
    entity_refs: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    resolution_hint: str = ""  # Suggested resolution

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "risk_id": self.risk_id,
            "risk_level": self.risk_level.value,
            "description": self.description,
            "entity_refs": list(self.entity_refs),
            "evidence_refs": list(self.evidence_refs),
            "resolution_hint": self.resolution_hint,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContinuityRisk:
        level_raw = data.get("risk_level", "none")
        try:
            level = RiskLevel(level_raw)
        except ValueError:
            level = RiskLevel.NONE
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            risk_id=data.get("risk_id", ""),
            risk_level=level,
            description=data.get("description", ""),
            entity_refs=list(data.get("entity_refs", [])),
            evidence_refs=list(data.get("evidence_refs", [])),
            resolution_hint=data.get("resolution_hint", ""),
        )
