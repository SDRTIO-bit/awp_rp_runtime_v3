"""AWPV2OpportunityTrigger — ComfyUI node for Opportunity trigger evaluation."""

from __future__ import annotations
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.director_plan import DirectorPlan
from ..runtime.opportunity_trigger_policy import OpportunityTriggerPolicy


class AWPV2OpportunityTrigger:
    """Evaluate whether Opportunity Agent should be triggered."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT", {}),
                "director_plan": ("DIRECTOR_PLAN", {}),
            },
            "optional": {
                "history_recall_result": ("HISTORY_RECALL_RESULT", {}),
            },
        }

    RETURN_TYPES = ("OPPORTUNITY_TRIGGER_RESULT",)
    RETURN_NAMES = ("trigger_result",)
    FUNCTION = "evaluate"
    CATEGORY = "AWP V2/Opportunity"

    def evaluate(
        self,
        round_snapshot: RoundSnapshot,
        director_plan: DirectorPlan,
        history_recall_result: Any = None,
    ) -> tuple:
        policy = OpportunityTriggerPolicy()
        result = policy.evaluate(round_snapshot, director_plan, history_recall_result)
        return (result,)
