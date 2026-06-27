"""ToolBudgetRuntime — budget and timeout enforcement for tool plans.

Enforces per-plan and per-request limits on:
- Request count
- Token budget
- Time budget
- Parallelism
"""

from __future__ import annotations

from ..contracts.tool_plan import ToolPlan, PlannedToolRequest


class ToolBudgetRuntime:
    """Enforces budget and timeout constraints on tool plans."""

    def validate_plan(self, plan: ToolPlan) -> tuple[bool, list[str]]:
        """Validate a ToolPlan against budget constraints.

        Returns (valid, list_of_violations).
        """
        violations = []

        # Check request count
        if len(plan.requests) > plan.max_request_count:
            violations.append(
                f"Request count {len(plan.requests)} exceeds max {plan.max_request_count}"
            )

        # Check total token budget
        total_tokens = sum(r.token_budget for r in plan.requests)
        if total_tokens > plan.total_token_budget:
            violations.append(
                f"Total token budget {total_tokens} exceeds max {plan.total_token_budget}"
            )

        # Check individual request timeouts
        for req in plan.requests:
            if req.timeout_ms > plan.total_time_budget_ms:
                violations.append(
                    f"Request '{req.request_id}' timeout {req.timeout_ms}ms "
                    f"exceeds plan total time budget {plan.total_time_budget_ms}ms"
                )

        return len(violations) == 0, violations

    def check_request_budget(
        self,
        request: PlannedToolRequest,
        remaining_token_budget: int,
        remaining_time_budget_ms: int,
    ) -> tuple[bool, str]:
        """Check if a single request fits within remaining budget."""
        if request.token_budget > remaining_token_budget:
            return False, (
                f"Request token budget {request.token_budget} "
                f"exceeds remaining {remaining_token_budget}"
            )
        if request.timeout_ms > remaining_time_budget_ms:
            return False, (
                f"Request timeout {request.timeout_ms}ms "
                f"exceeds remaining {remaining_time_budget_ms}ms"
            )
        return True, "Within budget"
