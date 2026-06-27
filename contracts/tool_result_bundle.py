"""ToolResultBundle — aggregated results from a ToolPlan execution.

schemaId: awp.rp.tool-result-bundle.v1

Contains all tool results from a single ToolPlan execution,
along with budget usage and categorized request IDs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .tool_result import ToolResult

SCHEMA_ID = "awp.rp.tool-result-bundle.v1"
SCHEMA_VERSION = 1


@dataclass
class ToolResultBundle:
    """Aggregated results from a ToolPlan execution."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    bundle_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    tool_plan_id: str = ""

    # Results
    results: list[ToolResult] = field(default_factory=list)

    # Categorized request IDs
    successful_request_ids: list[str] = field(default_factory=list)
    failed_request_ids: list[str] = field(default_factory=list)
    degraded_request_ids: list[str] = field(default_factory=list)

    # Budget usage
    budget_usage: dict[str, Any] = field(default_factory=dict)

    # Timestamp
    created_at: str = ""

    @property
    def success_count(self) -> int:
        return len(self.successful_request_ids)

    @property
    def failed_count(self) -> int:
        return len(self.failed_request_ids)

    @property
    def degraded_count(self) -> int:
        return len(self.degraded_request_ids)

    def get_result_by_request_id(self, request_id: str) -> ToolResult | None:
        for r in self.results:
            if r.request_id == request_id:
                return r
        return None

    def get_successful_results(self) -> list[ToolResult]:
        return [r for r in self.results if r.is_success()]

    def get_failed_results(self) -> list[ToolResult]:
        return [r for r in self.results if r.is_failed()]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "bundle_id": self.bundle_id,
            "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id,
            "tool_plan_id": self.tool_plan_id,
            "results": [r.to_dict() for r in self.results],
            "successful_request_ids": self.successful_request_ids,
            "failed_request_ids": self.failed_request_ids,
            "degraded_request_ids": self.degraded_request_ids,
            "budget_usage": self.budget_usage,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolResultBundle:
        results = [ToolResult.from_dict(r) for r in data.get("results", [])]
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            bundle_id=data.get("bundle_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            tool_plan_id=data.get("tool_plan_id", ""),
            results=results,
            successful_request_ids=data.get("successful_request_ids", []),
            failed_request_ids=data.get("failed_request_ids", []),
            degraded_request_ids=data.get("degraded_request_ids", []),
            budget_usage=data.get("budget_usage", {}),
            created_at=data.get("created_at", ""),
        )
