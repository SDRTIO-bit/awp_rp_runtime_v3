"""NodeContractCheck — declarative contract check definition for a node.

schemaId: awp.rp.node-contract-check.v1

Separates enforced checks (business rules that block execution)
from observational checks (diagnostic rules that only mark warnings).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.node-contract-check.v1"
SCHEMA_VERSION = 1


@dataclass
class NodeContractCheck:
    """A single contract check definition."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    check_id: str = ""
    check_name: str = ""
    check_type: str = "observational"  # observational | enforced
    description: str = ""
    severity: str = "info"  # info | warning | violation

    # What this check validates
    invariant: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "check_id": self.check_id,
            "check_name": self.check_name,
            "check_type": self.check_type,
            "description": self.description,
            "severity": self.severity,
            "invariant": self.invariant,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeContractCheck:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            check_id=data.get("check_id", ""),
            check_name=data.get("check_name", ""),
            check_type=data.get("check_type", "observational"),
            description=data.get("description", ""),
            severity=data.get("severity", "info"),
            invariant=data.get("invariant", ""),
        )
