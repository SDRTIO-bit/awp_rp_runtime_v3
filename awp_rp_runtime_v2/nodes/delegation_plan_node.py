"""AWPV2DelegationPlan — validates DelegationPlan against policy.

Input: delegation_plan
Output: validated_delegation_plan
"""

from __future__ import annotations

from typing import Any


class AWPV2DelegationPlan:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "delegation_plan": ("DELEGATION_PLAN",),
                "round_snapshot": ("ROUND_SNAPSHOT",),
                "turn_brief": ("TURN_BRIEF",),
            },
        }

    RETURN_TYPES = ("DELEGATION_PLAN", "DIAGNOSTICS")
    RETURN_NAMES = ("validated_plan", "diagnostics")
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(
        self,
        delegation_plan: dict[str, Any],
        round_snapshot: dict[str, Any],
        turn_brief: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        from ..contracts.delegation_plan import DelegationPlan
        from ..runtime.agent_runtime_registry import AgentRuntimeRegistry

        plan = DelegationPlan.from_dict(delegation_plan)
        registry = AgentRuntimeRegistry()

        errors = []
        # Validate roles
        for task in plan.tasks:
            if not registry.is_registered(task.role):
                errors.append(f"Unknown role: {task.role}")
        # Validate task count
        if len(plan.tasks) > plan.max_task_count:
            errors.append(f"Too many tasks: {len(plan.tasks)} > {plan.max_task_count}")

        diagnostics = {"valid": len(errors) == 0, "errors": errors, "task_count": len(plan.tasks)}
        return (plan.to_dict(), diagnostics)
