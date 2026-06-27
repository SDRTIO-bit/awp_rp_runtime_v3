"""AWPV2DynamicSubAgentPool — executes dynamic sub-agents.

Input: delegation_plan, round_snapshot, turn_brief
Output: agent_execution_results, diagnostics
"""

from __future__ import annotations

from typing import Any


class AWPV2DynamicSubAgentPool:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "delegation_plan": ("DELEGATION_PLAN",),
                "round_snapshot": ("ROUND_SNAPSHOT",),
                "turn_brief": ("TURN_BRIEF",),
            },
        }

    RETURN_TYPES = ("AGENT_EXECUTION_RESULTS", "DIAGNOSTICS")
    RETURN_NAMES = ("execution_results", "diagnostics")
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(
        self,
        delegation_plan: dict[str, Any],
        round_snapshot: dict[str, Any],
        turn_brief: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        from ..contracts.delegation_plan import DelegationPlan
        from ..contracts.round_snapshot import RoundSnapshot
        from ..runtime.agent_runtime_registry import AgentRuntimeRegistry
        from ..runtime.task_envelope_builder import TaskEnvelopeBuilder
        from ..runtime.dynamic_subagent_pool import DynamicSubAgentPool

        plan = DelegationPlan.from_dict(delegation_plan)
        snapshot = RoundSnapshot.from_dict(round_snapshot)

        registry = AgentRuntimeRegistry()
        builder = TaskEnvelopeBuilder(registry)
        pool = DynamicSubAgentPool(registry, builder)

        results = pool.execute(plan, snapshot)

        diagnostics = {
            "tasks_executed": len(results),
            "tasks_succeeded": sum(1 for r in results if r.success),
            "tasks_failed": sum(1 for r in results if not r.success),
        }

        return ([r.to_dict() for r in results], diagnostics)
