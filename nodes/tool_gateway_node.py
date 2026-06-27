"""AWPV2ToolGateway — ComfyUI node for tool execution.

All tool calls go through this gateway.
Permission-checked, budget-controlled, trace-logged.
"""

from __future__ import annotations


class AWPV2ToolGateway:
    """AWP V2 工具网关节点"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "tool_plan": ("TOOL_PLAN",),
                "round_snapshot": ("ROUND_SNAPSHOT",),
            },
        }

    RETURN_TYPES = ("TOOL_RESULT_BUNDLE", "EXECUTION_TRACE")
    RETURN_NAMES = ("tool_result_bundle", "execution_trace")
    FUNCTION = "execute"
    CATEGORY = "AWP V2 / Tool Gateway"

    def execute(self, tool_plan: dict, round_snapshot: dict):
        from ..runtime.tool_registry import ToolRegistry
        from ..runtime.tool_permission_policy import ToolPermissionPolicy
        from ..runtime.tool_budget_runtime import ToolBudgetRuntime
        from ..runtime.tool_gateway import ToolGateway, FakeToolRunner
        from ..contracts.tool_plan import ToolPlan
        from ..contracts.round_snapshot import RoundSnapshot
        from ..contracts.execution_trace import ExecutionTrace

        plan = ToolPlan.from_dict(tool_plan)
        snapshot = RoundSnapshot.from_dict(round_snapshot)

        registry = ToolRegistry()
        permission = ToolPermissionPolicy(registry)
        budget = ToolBudgetRuntime()
        runner = FakeToolRunner()

        gateway = ToolGateway(registry, permission, budget, runner)
        trace = ExecutionTrace(trace_id=plan.trace_id)
        bundle = gateway.execute(plan, snapshot, trace)

        return (bundle.to_dict(), trace.to_dict())
