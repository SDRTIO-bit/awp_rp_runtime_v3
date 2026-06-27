"""WorkflowTestFailure — a single failed assertion in a scenario.

schemaId: awp.rp.workflow-test-failure.v1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.workflow-test-failure.v1"
SCHEMA_VERSION = 1


@dataclass
class WorkflowTestFailure:
    """A single failed assertion."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    failure_id: str = ""
    scenario_id: str = ""
    node_id: str = ""
    assertion_name: str = ""

    # What was expected vs what happened
    expected: Any = None
    actual: Any = None

    # Context
    message: str = ""
    severity: str = "error"  # error | warning

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "failure_id": self.failure_id,
            "scenario_id": self.scenario_id,
            "node_id": self.node_id,
            "assertion_name": self.assertion_name,
            "expected": self.expected,
            "actual": self.actual,
            "message": self.message,
            "severity": self.severity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowTestFailure:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            failure_id=data.get("failure_id", ""),
            scenario_id=data.get("scenario_id", ""),
            node_id=data.get("node_id", ""),
            assertion_name=data.get("assertion_name", ""),
            expected=data.get("expected"),
            actual=data.get("actual"),
            message=data.get("message", ""),
            severity=data.get("severity", "error"),
        )
