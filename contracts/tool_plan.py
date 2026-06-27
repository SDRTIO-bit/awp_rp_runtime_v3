"""ToolPlan — Director's plan for tool calls in the current turn.

schemaId: awp.rp.tool-plan.v1

Director produces this to request tool calls through the ToolGateway.
Tools are strictly limited to registered, permission-checked, budget-controlled calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.tool-plan.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PlannedToolRequest:
    """A single planned tool request within a ToolPlan."""
    request_id: str = ""
    tool_id: str = ""
    purpose: str = ""
    priority: float = 0.5
    input: dict[str, Any] = field(default_factory=dict)
    expected_result_schema: str = ""
    timeout_ms: int = 30000
    token_budget: int = 1000
    required: bool = False
    failure_policy: str = "degrade"  # degrade | abort
    evidence_requirement: str = ""  # What evidence is needed from this tool

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "tool_id": self.tool_id,
            "purpose": self.purpose,
            "priority": self.priority,
            "input": self.input,
            "expected_result_schema": self.expected_result_schema,
            "timeout_ms": self.timeout_ms,
            "token_budget": self.token_budget,
            "required": self.required,
            "failure_policy": self.failure_policy,
            "evidence_requirement": self.evidence_requirement,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlannedToolRequest:
        return cls(
            request_id=data.get("request_id", ""),
            tool_id=data.get("tool_id", ""),
            purpose=data.get("purpose", ""),
            priority=data.get("priority", 0.5),
            input=data.get("input", {}),
            expected_result_schema=data.get("expected_result_schema", ""),
            timeout_ms=data.get("timeout_ms", 30000),
            token_budget=data.get("token_budget", 1000),
            required=data.get("required", False),
            failure_policy=data.get("failure_policy", "degrade"),
            evidence_requirement=data.get("evidence_requirement", ""),
        )


@dataclass
class ToolPlan:
    """Director's plan for tool calls in the current turn.

    All tool calls must go through the ToolGateway.
    No direct tool execution allowed.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    tool_plan_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    director_plan_id: str = ""
    card_id: str = ""
    session_id: str = ""

    # Requests
    requests: list[PlannedToolRequest] = field(default_factory=list)

    # Budget constraints
    max_request_count: int = 5
    max_parallelism: int = 1
    total_token_budget: int = 5000
    total_time_budget_ms: int = 60000

    # Fallback
    fallback_policy: str = "degrade_optional"  # degrade_optional | abort_all

    # Timestamp
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "tool_plan_id": self.tool_plan_id,
            "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id,
            "director_plan_id": self.director_plan_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "requests": [r.to_dict() for r in self.requests],
            "max_request_count": self.max_request_count,
            "max_parallelism": self.max_parallelism,
            "total_token_budget": self.total_token_budget,
            "total_time_budget_ms": self.total_time_budget_ms,
            "fallback_policy": self.fallback_policy,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolPlan:
        requests = [PlannedToolRequest.from_dict(r) for r in data.get("requests", [])]
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            tool_plan_id=data.get("tool_plan_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            director_plan_id=data.get("director_plan_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            requests=requests,
            max_request_count=data.get("max_request_count", 5),
            max_parallelism=data.get("max_parallelism", 1),
            total_token_budget=data.get("total_token_budget", 5000),
            total_time_budget_ms=data.get("total_time_budget_ms", 60000),
            fallback_policy=data.get("fallback_policy", "degrade_optional"),
            created_at=data.get("created_at", ""),
        )
