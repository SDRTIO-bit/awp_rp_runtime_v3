"""ToolGateway — the unified, observable, permission-checked tool execution layer.

All tool calls MUST go through this gateway.
No direct tool execution allowed anywhere else.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from ..contracts.tool_plan import ToolPlan, PlannedToolRequest
from ..contracts.tool_request import ToolRequest
from ..contracts.tool_result import ToolResult, ToolResultStatus
from ..contracts.tool_result_bundle import ToolResultBundle
from ..contracts.tool_execution_receipt import ToolExecutionReceipt
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.execution_trace import ExecutionTrace, TraceEvent
from .tool_registry import ToolRegistry, ToolRegistration
from .tool_permission_policy import ToolPermissionPolicy
from .tool_budget_runtime import ToolBudgetRuntime


class ToolRunner(Protocol):
    """Protocol for tool execution implementations."""
    def run(
        self,
        tool_id: str,
        sanitized_input: dict[str, Any],
        snapshot: RoundSnapshot,
    ) -> dict[str, Any]:
        """Execute a tool and return structured results."""
        ...


class FakeToolRunner:
    """Fake tool runner for testing. Returns deterministic results."""

    def __init__(self):
        self._custom_results: dict[str, dict[str, Any]] = {}

    def set_result(self, tool_id: str, result: dict[str, Any]) -> None:
        self._custom_results[tool_id] = result

    def run(
        self,
        tool_id: str,
        sanitized_input: dict[str, Any],
        snapshot: RoundSnapshot,
    ) -> dict[str, Any]:
        if tool_id in self._custom_results:
            return self._custom_results[tool_id]

        # Default fake results per tool
        defaults = {
            "worldbook_lookup": {
                "entries": [{"title": "Default World", "content": "A generic setting"}],
                "source_refs": [f"worldbook:{snapshot.card_id}"],
            },
            "rag_memory_lookup": {
                "hits": [{"memory_id": "rag_001", "summary": "A past event", "score": 0.7}],
                "source_refs": [f"rag:{snapshot.session_id}"],
            },
            "entity_alias_lookup": {
                "aliases": ["Character A", "The Protagonist"],
                "source_refs": [f"entity:{snapshot.card_id}"],
            },
            "timeline_lookup": {
                "events": [{"turn": 1, "event": "Story began"}],
                "source_refs": [f"timeline:{snapshot.card_id}"],
            },
            "relationship_context_lookup": {
                "relationships": [{"entity_a": "player", "entity_b": "npc_1", "relation": "acquaintance"}],
                "source_refs": [f"relationship:{snapshot.card_id}"],
            },
            # D1: History/Recall tools
            "accepted_turn_lookup": {
                "turns": [{"turn_id": "tr_1", "player_input": "test", "writer_output": "A past turn"}],
                "source_refs": [f"accepted_turn:{snapshot.card_id}:{snapshot.session_id}"],
            },
            "active_memory_lookup": {
                "memories": [{"memory_id": "am_001", "summary": "An active memory", "status": "active"}],
                "source_refs": [f"active_memory:{snapshot.card_id}:{snapshot.session_id}"],
            },
        }
        return defaults.get(tool_id, {"result": "unknown_tool", "source_refs": []})


class ToolGateway:
    """The unified, observable, permission-checked tool execution layer.

    All tool calls MUST go through this gateway.
    Provides: permission checking, budget enforcement, timeout,
    result validation, trace logging, failure degradation.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        permission_policy: ToolPermissionPolicy,
        budget_runtime: ToolBudgetRuntime,
        tool_runner: ToolRunner | FakeToolRunner,
    ):
        self.registry = registry
        self.permission_policy = permission_policy
        self.budget_runtime = budget_runtime
        self.tool_runner = tool_runner

    def execute(
        self,
        plan: ToolPlan,
        snapshot: RoundSnapshot,
        trace: ExecutionTrace | None = None,
    ) -> ToolResultBundle:
        """Execute all tool requests in a plan.

        Returns ToolResultBundle with all results, categorized by status.
        """
        now = datetime.now(timezone.utc).isoformat()
        bundle_id = f"trb_{uuid.uuid4().hex[:12]}"

        # 1. Validate plan budget
        valid, violations = self.budget_runtime.validate_plan(plan)
        if not valid:
            # Return empty bundle with all requests marked as failed
            results = []
            failed_ids = []
            for req in plan.requests:
                result = ToolResult(
                    result_id=f"tr_{uuid.uuid4().hex[:12]}",
                    request_id=req.request_id,
                    trace_id=plan.trace_id,
                    tool_id=req.tool_id,
                    status=ToolResultStatus.BUDGET_EXCEEDED,
                    failure_reason=f"Plan budget violation: {'; '.join(violations)}",
                    created_at=now,
                )
                results.append(result)
                failed_ids.append(req.request_id)

            return ToolResultBundle(
                bundle_id=bundle_id,
                trace_id=plan.trace_id,
                snapshot_id=plan.snapshot_id,
                tool_plan_id=plan.tool_plan_id,
                results=results,
                failed_request_ids=failed_ids,
                budget_usage={"violations": violations},
                created_at=now,
            )

        # 2. Execute each request
        results = []
        successful_ids = []
        failed_ids = []
        degraded_ids = []
        remaining_tokens = plan.total_token_budget
        remaining_time_ms = plan.total_time_budget_ms
        receipts = []

        for req in plan.requests:
            # Check per-request budget
            within_budget, budget_msg = self.budget_runtime.check_request_budget(
                req, remaining_tokens, remaining_time_ms
            )
            if not within_budget:
                result = ToolResult(
                    result_id=f"tr_{uuid.uuid4().hex[:12]}",
                    request_id=req.request_id,
                    trace_id=plan.trace_id,
                    tool_id=req.tool_id,
                    status=ToolResultStatus.BUDGET_EXCEEDED,
                    failure_reason=budget_msg,
                    created_at=now,
                )
                results.append(result)
                failed_ids.append(req.request_id)
                continue

            # Check permission
            permission = self.permission_policy.check(req, snapshot)
            if not permission.allowed:
                result = ToolResult(
                    result_id=f"tr_{uuid.uuid4().hex[:12]}",
                    request_id=req.request_id,
                    trace_id=plan.trace_id,
                    tool_id=req.tool_id,
                    status=ToolResultStatus.PERMISSION_DENIED,
                    failure_reason=permission.reason,
                    created_at=now,
                )
                results.append(result)
                failed_ids.append(req.request_id)

                # Log receipt
                receipts.append(ToolExecutionReceipt(
                    receipt_id=f"rcpt_{uuid.uuid4().hex[:12]}",
                    request_id=req.request_id,
                    result_id=result.result_id,
                    trace_id=plan.trace_id,
                    tool_id=req.tool_id,
                    status=ToolResultStatus.PERMISSION_DENIED,
                    permission_allowed=False,
                    permission_reason=permission.reason,
                    budget_before=remaining_tokens,
                    budget_after=remaining_tokens,
                    created_at=now,
                ))
                continue

            # Execute tool
            start_time = time.time()
            try:
                raw_result = self.tool_runner.run(
                    req.tool_id, req.input, snapshot
                )
                duration_ms = int((time.time() - start_time) * 1000)

                # Build source refs from result
                source_refs = raw_result.get("source_refs", [])
                if not source_refs:
                    source_refs = [f"{req.tool_id}:{snapshot.card_id}:{snapshot.session_id}"]

                # Build summary
                summary_parts = []
                for key, value in raw_result.items():
                    if key != "source_refs" and value:
                        if isinstance(value, list):
                            summary_parts.append(f"{key}: {len(value)} items")
                        elif isinstance(value, str) and len(value) < 100:
                            summary_parts.append(f"{key}: {value}")
                summary = "; ".join(summary_parts)[:200]

                result = ToolResult(
                    result_id=f"tr_{uuid.uuid4().hex[:12]}",
                    request_id=req.request_id,
                    trace_id=plan.trace_id,
                    tool_id=req.tool_id,
                    status=ToolResultStatus.SUCCESS,
                    summary=summary,
                    structured_data=raw_result,
                    evidence=[],
                    source_refs=source_refs,
                    duration_ms=duration_ms,
                    token_usage=min(req.token_budget, 100),
                    created_at=now,
                )
                results.append(result)
                successful_ids.append(req.request_id)
                remaining_tokens -= result.token_usage
                remaining_time_ms -= duration_ms

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                status = ToolResultStatus.TIMEOUT if "timeout" in str(e).lower() else ToolResultStatus.FAILED

                result = ToolResult(
                    result_id=f"tr_{uuid.uuid4().hex[:12]}",
                    request_id=req.request_id,
                    trace_id=plan.trace_id,
                    tool_id=req.tool_id,
                    status=status,
                    failure_reason=str(e),
                    duration_ms=duration_ms,
                    created_at=now,
                )
                results.append(result)

                if req.required:
                    failed_ids.append(req.request_id)
                else:
                    degraded_ids.append(req.request_id)
                    result.status = ToolResultStatus.DEGRADED

            # Log receipt
            receipts.append(ToolExecutionReceipt(
                receipt_id=f"rcpt_{uuid.uuid4().hex[:12]}",
                request_id=req.request_id,
                result_id=results[-1].result_id if results else "",
                trace_id=plan.trace_id,
                tool_id=req.tool_id,
                status=results[-1].status if results else "unknown",
                duration_ms=duration_ms if 'duration_ms' in dir() else 0,
                token_usage=results[-1].token_usage if results else 0,
                permission_allowed=True,
                budget_before=remaining_tokens + (results[-1].token_usage if results else 0),
                budget_after=remaining_tokens,
                created_at=now,
            ))

            # Log trace event
            if trace:
                trace.add_event(TraceEvent(
                    event_id=f"evt_{uuid.uuid4().hex[:8]}",
                    event_type="tool_executed",
                    actor="tool_gateway",
                    details={
                        "tool_id": req.tool_id,
                        "request_id": req.request_id,
                        "status": results[-1].status if results else "unknown",
                    },
                    success=results[-1].is_success() if results else False,
                    duration_ms=duration_ms if 'duration_ms' in dir() else 0,
                ))

        return ToolResultBundle(
            bundle_id=bundle_id,
            trace_id=plan.trace_id,
            snapshot_id=plan.snapshot_id,
            tool_plan_id=plan.tool_plan_id,
            results=results,
            successful_request_ids=successful_ids,
            failed_request_ids=failed_ids,
            degraded_request_ids=degraded_ids,
            budget_usage={
                "total_token_budget": plan.total_token_budget,
                "tokens_used": plan.total_token_budget - remaining_tokens,
                "tokens_remaining": remaining_tokens,
                "total_time_budget_ms": plan.total_time_budget_ms,
                "time_used_ms": plan.total_time_budget_ms - remaining_time_ms,
            },
            created_at=now,
        )
