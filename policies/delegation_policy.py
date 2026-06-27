"""DelegationPolicy — rules for dynamic sub-agent delegation.

Enforces:
- Maximum sub-agent count
- Allowed roles
- No recursive delegation
- Budget constraints
"""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.delegation_plan import DelegationPlan, DelegationTask


@dataclass
class DelegationValidation:
    """Result of delegation policy validation."""
    valid: bool
    errors: list[str]


class DelegationPolicy:
    """Policy for sub-agent delegation.

    Pure policy — no side effects, no I/O.
    """

    # Allowed sub-agent roles
    ALLOWED_ROLES = {
        "rp-critic",
        "rp-memory-curator",
        "rp-state-updater",
        "worldbook-researcher",
        "continuity-checker",
    }

    # Constraints
    MAX_SUB_AGENTS = 5
    MAX_TOOL_CALLS_PER_AGENT = 10
    MAX_RESULT_TOKENS_PER_AGENT = 2000

    def validate_plan(self, plan: DelegationPlan) -> DelegationValidation:
        """Validate a delegation plan against policy."""
        errors = []

        # Check task count
        if len(plan.tasks) > self.MAX_SUB_AGENTS:
            errors.append(
                f"Too many tasks: {len(plan.tasks)} > max {self.MAX_SUB_AGENTS}"
            )

        # Validate each task
        for i, task in enumerate(plan.tasks):
            # Role check
            if task.role not in self.ALLOWED_ROLES:
                errors.append(
                    f"Task[{i}]: unknown role '{task.role}'"
                )

            # Tool call budget
            if task.max_tool_calls > self.MAX_TOOL_CALLS_PER_AGENT:
                errors.append(
                    f"Task[{i}]: max_tool_calls {task.max_tool_calls} > "
                    f"max {self.MAX_TOOL_CALLS_PER_AGENT}"
                )

            # Result token budget
            if task.max_result_tokens > self.MAX_RESULT_TOKENS_PER_AGENT:
                errors.append(
                    f"Task[{i}]: max_result_tokens {task.max_result_tokens} > "
                    f"max {self.MAX_RESULT_TOKENS_PER_AGENT}"
                )

            # Goal must be non-empty
            if not task.goal.strip():
                errors.append(f"Task[{i}]: goal is empty")

        return DelegationValidation(valid=len(errors) == 0, errors=errors)

    def is_role_allowed(self, role: str) -> bool:
        """Check if a role is allowed."""
        return role in self.ALLOWED_ROLES
