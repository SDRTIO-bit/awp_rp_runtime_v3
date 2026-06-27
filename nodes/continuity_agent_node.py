"""AWPV2ContinuityAgent — ComfyUI node for running Continuity Agent."""

from __future__ import annotations
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.delegation_plan import DelegationTask
from ..runtime.continuity_trigger_policy import ContinuityTriggerResult
from ..runtime.continuity_runtime import ContinuityRuntime
from ..runtime.continuity_tool_profile import CONTINUITY_TOOLS


class AWPV2ContinuityAgent:
    """Run the Continuity Agent to check for fact conflicts and constraints."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT", {}),
                "trigger_result": ("CONTINUITY_TRIGGER_RESULT", {}),
            },
        }

    RETURN_TYPES = ("CONTINUITY_RESULT",)
    RETURN_NAMES = ("continuity_result",)
    FUNCTION = "run"
    CATEGORY = "AWP V2/Continuity"

    def run(
        self,
        round_snapshot: RoundSnapshot,
        trigger_result: ContinuityTriggerResult,
    ) -> tuple:
        runtime = ContinuityRuntime()
        task = DelegationTask(
            task_id="continuity_task",
            role="continuity",
            tool_allowlist=list(CONTINUITY_TOOLS.keys()),
        )
        result = runtime.run(
            snapshot=round_snapshot,
            task=task,
            trigger_result=trigger_result,
        )
        return (result,)
