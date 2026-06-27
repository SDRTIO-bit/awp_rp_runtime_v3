"""AWPV2WorldLifeAgent — ComfyUI node for running World-Life Agent."""

from __future__ import annotations
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.delegation_plan import DelegationTask
from ..runtime.world_life_trigger_policy import WorldLifeTriggerResult
from ..runtime.world_life_runtime import WorldLifeRuntime


class AWPV2WorldLifeAgent:
    """Run the World-Life Agent to identify world activity beyond protagonist's view."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT", {}),
                "trigger_result": ("WORLD_LIFE_TRIGGER_RESULT", {}),
            },
        }

    RETURN_TYPES = ("WORLD_LIFE_RESULT",)
    RETURN_NAMES = ("world_life_result",)
    FUNCTION = "run"
    CATEGORY = "AWP V2/WorldLife"

    def run(
        self,
        round_snapshot: RoundSnapshot,
        trigger_result: WorldLifeTriggerResult,
    ) -> tuple:
        runtime = WorldLifeRuntime()
        task = DelegationTask(
            task_id="world_life_task",
            role="world-life",
            tool_allowlist=list(runtime.query_planner.__class__.__dict__.keys()),
        )
        result = runtime.run(
            snapshot=round_snapshot,
            task=task,
            trigger_result=trigger_result,
        )
        return (result,)
