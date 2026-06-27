"""AWPV2DirectorPlan — ComfyUI node for Director planning.

Reads RoundSnapshot and produces DirectorPlan + ToolPlan + DelegationPlan.
"""

from __future__ import annotations

from typing import Any


class AWPV2DirectorPlan:
    """AWP V2 Director规划节点"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT",),
            },
            "optional": {
                "custom_director_plan": ("DIRECTOR_PLAN",),
            },
        }

    RETURN_TYPES = ("DIRECTOR_PLAN", "TOOL_PLAN", "DELEGATION_PLAN")
    RETURN_NAMES = ("director_plan", "tool_plan", "delegation_plan")
    FUNCTION = "execute"
    CATEGORY = "AWP V2 / Director"

    def execute(self, round_snapshot: dict, custom_director_plan: dict | None = None):
        from ..runtime.director_v2_runtime import DirectorV2Runtime, FakeDirectorV2Adapter
        from ..contracts.round_snapshot import RoundSnapshot

        snapshot = RoundSnapshot.from_dict(round_snapshot)

        adapter = FakeDirectorV2Adapter()
        if custom_director_plan:
            from ..contracts.director_plan import DirectorPlan
            adapter.set_plan(DirectorPlan.from_dict(custom_director_plan))

        runtime = DirectorV2Runtime(adapter)
        plan, tool_plan, delegation_plan = runtime.plan(snapshot)

        return (plan.to_dict(), tool_plan.to_dict(), delegation_plan.to_dict())
