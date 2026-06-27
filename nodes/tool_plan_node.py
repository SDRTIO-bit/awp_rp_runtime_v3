"""AWPV2ToolPlan — ComfyUI node for ToolPlan validation.

Validates a ToolPlan against budget and permission constraints.
"""

from __future__ import annotations


class AWPV2ToolPlan:
    """AWP V2 工具计划节点"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "tool_plan": ("TOOL_PLAN",),
            },
        }

    RETURN_TYPES = ("TOOL_PLAN", "VALIDATION_RESULT")
    RETURN_NAMES = ("tool_plan", "validation_result")
    FUNCTION = "execute"
    CATEGORY = "AWP V2 / Tool Gateway"

    def execute(self, tool_plan: dict):
        from ..runtime.tool_budget_runtime import ToolBudgetRuntime
        from ..contracts.tool_plan import ToolPlan

        plan = ToolPlan.from_dict(tool_plan)
        budget = ToolBudgetRuntime()
        valid, violations = budget.validate_plan(plan)

        return (tool_plan, {"valid": valid, "violations": violations})
