"""AWPV2OpportunityAgent — ComfyUI node for running Opportunity Agent."""

from __future__ import annotations
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.delegation_plan import DelegationTask
from ..runtime.opportunity_trigger_policy import OpportunityTriggerResult
from ..runtime.opportunity_runtime import OpportunityRuntime


class AWPV2OpportunityAgent:
    """Run the Opportunity Agent to identify narrative opportunities."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT", {}),
                "trigger_result": ("OPPORTUNITY_TRIGGER_RESULT", {}),
            },
        }

    RETURN_TYPES = ("OPPORTUNITY_RESULT",)
    RETURN_NAMES = ("opportunity_result",)
    FUNCTION = "run"
    CATEGORY = "AWP V2/Opportunity"

    def run(
        self,
        round_snapshot: RoundSnapshot,
        trigger_result: OpportunityTriggerResult,
    ) -> tuple:
        runtime = OpportunityRuntime()
        task = DelegationTask(
            task_id="opportunity_task",
            role="opportunity",
            tool_allowlist=list(runtime.query_planner.__class__.__dict__.keys()),
        )
        result = runtime.run(
            snapshot=round_snapshot,
            task=task,
            trigger_result=trigger_result,
        )
        return (result,)
