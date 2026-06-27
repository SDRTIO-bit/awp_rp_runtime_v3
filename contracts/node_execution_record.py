"""NodeExecutionRecord — per-node execution trace with three-layer status.

schemaId: awp.rp.node-execution-record.v1

Three status groups:
  executionStatus:       executed | cached | failed | blocked_by_upstream_failure | cancelled | not_reached
  businessDisposition:   produced_result | noop | not_required | skipped_by_policy | skipped_by_budget | degraded
  semanticHealth:        passed | warning | violation | not_checked
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.node-execution-record.v1"
SCHEMA_VERSION = 1


class ExecutionStatus(str, Enum):
    EXECUTED = "executed"
    CACHED = "cached"
    FAILED = "failed"
    BLOCKED_BY_UPSTREAM_FAILURE = "blocked_by_upstream_failure"
    CANCELLED = "cancelled"
    NOT_REACHED = "not_reached"


class BusinessDisposition(str, Enum):
    PRODUCED_RESULT = "produced_result"
    NOOP = "noop"
    NOT_REQUIRED = "not_required"
    SKIPPED_BY_POLICY = "skipped_by_policy"
    SKIPPED_BY_BUDGET = "skipped_by_budget"
    DEGRADED = "degraded"


class SemanticHealth(str, Enum):
    PASSED = "passed"
    WARNING = "warning"
    VIOLATION = "violation"
    NOT_CHECKED = "not_checked"


@dataclass
class ContractCheck:
    """A single observational or enforced contract check result."""
    check_id: str = ""
    check_name: str = ""
    check_type: str = "observational"  # observational | enforced
    passed: bool = True
    severity: str = "info"  # info | warning | violation
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "check_name": self.check_name,
            "check_type": self.check_type,
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContractCheck:
        return cls(
            check_id=data.get("check_id", ""),
            check_name=data.get("check_name", ""),
            check_type=data.get("check_type", "observational"),
            passed=data.get("passed", True),
            severity=data.get("severity", "info"),
            message=data.get("message", ""),
            details=data.get("details", {}),
        )


@dataclass
class NodeExecutionRecord:
    """Complete per-node execution trace.

    Must be strictly serializable. Unknown fields must be rejected.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    trace_id: str = ""
    workflow_run_id: str = ""
    prompt_id: str = ""
    turn_id: str = ""
    attempt_id: str = ""

    # Node identity
    node_id: str = ""
    node_class: str = ""
    node_label: str = ""
    node_version: str = ""

    # Three-layer status
    execution_status: str = ExecutionStatus.NOT_REACHED.value
    business_disposition: str = BusinessDisposition.NOT_REQUIRED.value
    semantic_health: str = SemanticHealth.NOT_CHECKED.value

    # Timing
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0

    # Topology
    upstream_node_ids: list[str] = field(default_factory=list)
    downstream_node_ids: list[str] = field(default_factory=list)

    # Summaries (Level 1: default visible)
    input_summary: dict[str, Any] = field(default_factory=dict)
    output_summary: dict[str, Any] = field(default_factory=dict)
    error_summary: dict[str, Any] = field(default_factory=dict)

    # Contract checks
    contract_checks: list[ContractCheck] = field(default_factory=list)

    # Artifact references (Level 3: raw, default closed)
    artifact_refs: list[dict[str, Any]] = field(default_factory=list)

    # Redaction
    redaction_profile: str = "summary_only"  # summary_only | redline | raw

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "workflow_run_id": self.workflow_run_id,
            "prompt_id": self.prompt_id,
            "turn_id": self.turn_id,
            "attempt_id": self.attempt_id,
            "node_id": self.node_id,
            "node_class": self.node_class,
            "node_label": self.node_label,
            "node_version": self.node_version,
            "execution_status": self.execution_status,
            "business_disposition": self.business_disposition,
            "semantic_health": self.semantic_health,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "upstream_node_ids": self.upstream_node_ids,
            "downstream_node_ids": self.downstream_node_ids,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "error_summary": self.error_summary,
            "contract_checks": [c.to_dict() for c in self.contract_checks],
            "artifact_refs": self.artifact_refs,
            "redaction_profile": self.redaction_profile,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeExecutionRecord:
        checks = [ContractCheck.from_dict(c) for c in data.get("contract_checks", [])]
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            trace_id=data.get("trace_id", ""),
            workflow_run_id=data.get("workflow_run_id", ""),
            prompt_id=data.get("prompt_id", ""),
            turn_id=data.get("turn_id", ""),
            attempt_id=data.get("attempt_id", ""),
            node_id=data.get("node_id", ""),
            node_class=data.get("node_class", ""),
            node_label=data.get("node_label", ""),
            node_version=data.get("node_version", ""),
            execution_status=data.get("execution_status", ExecutionStatus.NOT_REACHED.value),
            business_disposition=data.get("business_disposition", BusinessDisposition.NOT_REQUIRED.value),
            semantic_health=data.get("semantic_health", SemanticHealth.NOT_CHECKED.value),
            started_at=data.get("started_at", ""),
            finished_at=data.get("finished_at", ""),
            duration_ms=data.get("duration_ms", 0),
            upstream_node_ids=data.get("upstream_node_ids", []),
            downstream_node_ids=data.get("downstream_node_ids", []),
            input_summary=data.get("input_summary", {}),
            output_summary=data.get("output_summary", {}),
            error_summary=data.get("error_summary", {}),
            contract_checks=checks,
            artifact_refs=data.get("artifact_refs", []),
            redaction_profile=data.get("redaction_profile", "summary_only"),
        )

    def set_timing(self, started_at: str, finished_at: str) -> None:
        self.started_at = started_at
        self.finished_at = finished_at
        try:
            s = datetime.fromisoformat(started_at)
            f = datetime.fromisoformat(finished_at)
            self.duration_ms = int((f - s).total_seconds() * 1000)
        except (ValueError, TypeError):
            self.duration_ms = 0

    def add_contract_check(self, check: ContractCheck) -> None:
        self.contract_checks.append(check)
        # Update semantic_health based on worst check
        if check.severity == "violation" and not check.passed:
            self.semantic_health = SemanticHealth.VIOLATION.value
        elif check.severity == "warning" and not check.passed:
            if self.semantic_health != SemanticHealth.VIOLATION.value:
                self.semantic_health = SemanticHealth.WARNING.value
