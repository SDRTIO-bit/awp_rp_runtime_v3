"""WorkflowTestResult — machine-readable outcome of a single scenario run.

schemaId: awp.rp.workflow-test-result.v1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.workflow-test-result.v1"
SCHEMA_VERSION = 1


@dataclass
class WorkflowTestResult:
    """Result of a single workflow test scenario."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    scenario_id: str = ""
    scenario_name: str = ""
    workflow_run_id: str = ""
    prompt_id: str = ""

    # Outcome
    passed: bool = False
    exit_code: int = 1  # 0=pass, 1=fail, 2=env_missing

    # Timing
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0

    # Node results
    node_records: list[dict[str, Any]] = field(default_factory=list)

    # Assertions
    total_assertions: int = 0
    passed_assertions: int = 0
    failed_assertions: int = 0

    # Failures
    failures: list[dict[str, Any]] = field(default_factory=list)

    # State diffs
    state_diff: dict[str, Any] = field(default_factory=dict)
    memory_diff: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "workflow_run_id": self.workflow_run_id,
            "prompt_id": self.prompt_id,
            "passed": self.passed,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "node_records": self.node_records,
            "total_assertions": self.total_assertions,
            "passed_assertions": self.passed_assertions,
            "failed_assertions": self.failed_assertions,
            "failures": self.failures,
            "state_diff": self.state_diff,
            "memory_diff": self.memory_diff,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowTestResult:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            scenario_id=data.get("scenario_id", ""),
            scenario_name=data.get("scenario_name", ""),
            workflow_run_id=data.get("workflow_run_id", ""),
            prompt_id=data.get("prompt_id", ""),
            passed=data.get("passed", False),
            exit_code=data.get("exit_code", 1),
            started_at=data.get("started_at", ""),
            finished_at=data.get("finished_at", ""),
            duration_ms=data.get("duration_ms", 0),
            node_records=data.get("node_records", []),
            total_assertions=data.get("total_assertions", 0),
            passed_assertions=data.get("passed_assertions", 0),
            failed_assertions=data.get("failed_assertions", 0),
            failures=data.get("failures", []),
            state_diff=data.get("state_diff", {}),
            memory_diff=data.get("memory_diff", {}),
        )
