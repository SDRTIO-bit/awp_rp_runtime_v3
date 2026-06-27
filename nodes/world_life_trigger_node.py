"""AWPV2WorldLifeTrigger — ComfyUI node for World-Life trigger evaluation."""

from __future__ import annotations
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.director_plan import DirectorPlan
from ..runtime.world_life_trigger_policy import WorldLifeTriggerPolicy


class AWPV2WorldLifeTrigger:
    """Evaluate whether World-Life Agent should be triggered."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT", {}),
                "director_plan": ("DIRECTOR_PLAN", {}),
            },
            "optional": {
                "history_recall_result": ("HISTORY_RECALL_RESULT", {}),
                "opportunity_result": ("OPPORTUNITY_RESULT", {}),
            },
        }

    RETURN_TYPES = ("WORLD_LIFE_TRIGGER_RESULT",)
    RETURN_NAMES = ("trigger_result",)
    FUNCTION = "evaluate"
    CATEGORY = "AWP V2/WorldLife"

    def evaluate(
        self,
        round_snapshot: RoundSnapshot,
        director_plan: DirectorPlan,
        history_recall_result: Any = None,
        opportunity_result: Any = None,
    ) -> tuple:
        policy = WorldLifeTriggerPolicy()
        result = policy.evaluate(
            round_snapshot, director_plan,
            history_recall_result, opportunity_result,
        )
        return (result,)
