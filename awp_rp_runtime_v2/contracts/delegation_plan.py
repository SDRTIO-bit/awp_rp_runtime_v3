"""DelegationPlan — Director's plan for dynamic sub-agents.

schemaId: awp.rp.delegation-plan.v1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.delegation-plan.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DelegationTask:
    task_id: str = ""
    role: str = ""  # must be a registered role
    priority: float = 0.5
    purpose: str = ""  # What this task should accomplish
    input_field_allowlist: list[str] = field(default_factory=list)
    tool_allowlist: list[str] = field(default_factory=list)
    max_tokens: int = 700
    timeout_ms: int = 30000
    required: bool = False
    failure_policy: str = "skip"  # skip | abort | degrade
    expected_suggestion_kinds: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id, "role": self.role,
            "priority": self.priority, "purpose": self.purpose,
            "input_field_allowlist": self.input_field_allowlist,
            "tool_allowlist": self.tool_allowlist,
            "max_tokens": self.max_tokens, "timeout_ms": self.timeout_ms,
            "required": self.required, "failure_policy": self.failure_policy,
            "expected_suggestion_kinds": self.expected_suggestion_kinds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DelegationTask:
        return cls(
            task_id=data.get("task_id", ""), role=data.get("role", ""),
            priority=data.get("priority", 0.5), purpose=data.get("purpose", ""),
            input_field_allowlist=data.get("input_field_allowlist", []),
            tool_allowlist=data.get("tool_allowlist", []),
            max_tokens=data.get("max_tokens", 700),
            timeout_ms=data.get("timeout_ms", 30000),
            required=data.get("required", False),
            failure_policy=data.get("failure_policy", "skip"),
            expected_suggestion_kinds=data.get("expected_suggestion_kinds", []),
        )


@dataclass
class DelegationPlan:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    plan_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    brief_id: str = ""
    card_id: str = ""
    session_id: str = ""

    tasks: list[DelegationTask] = field(default_factory=list)
    max_task_count: int = 5
    max_parallelism: int = 3
    total_token_budget: int = 10000
    total_time_budget_ms: int = 120000
    fallback_policy: str = "skip_all"  # skip_all | abort

    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "plan_id": self.plan_id, "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id, "brief_id": self.brief_id,
            "card_id": self.card_id, "session_id": self.session_id,
            "tasks": [t.to_dict() for t in self.tasks],
            "max_task_count": self.max_task_count,
            "max_parallelism": self.max_parallelism,
            "total_token_budget": self.total_token_budget,
            "total_time_budget_ms": self.total_time_budget_ms,
            "fallback_policy": self.fallback_policy,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DelegationPlan:
        tasks = [DelegationTask.from_dict(t) for t in data.get("tasks", [])]
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            plan_id=data.get("plan_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            brief_id=data.get("brief_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            tasks=tasks,
            max_task_count=data.get("max_task_count", 5),
            max_parallelism=data.get("max_parallelism", 3),
            total_token_budget=data.get("total_token_budget", 10000),
            total_time_budget_ms=data.get("total_time_budget_ms", 120000),
            fallback_policy=data.get("fallback_policy", "skip_all"),
            created_at=data.get("created_at", ""),
        )
