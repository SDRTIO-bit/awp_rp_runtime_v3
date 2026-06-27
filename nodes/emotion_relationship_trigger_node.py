"""AWPV2EmotionRelationshipTrigger — ComfyUI node for Emotion/Relationship trigger evaluation."""

from __future__ import annotations
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.director_plan import DirectorPlan
from ..runtime.emotion_relationship_trigger_policy import EmotionRelationshipTriggerPolicy


class AWPV2EmotionRelationshipTrigger:
    """Evaluate whether Emotion/Relationship Agent should be triggered."""

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

    RETURN_TYPES = ("ER_TRIGGER_RESULT",)
    RETURN_NAMES = ("trigger_result",)
    FUNCTION = "evaluate"
    CATEGORY = "AWP V2/EmotionRelationship"

    def evaluate(
        self,
        round_snapshot: RoundSnapshot,
        director_plan: DirectorPlan,
        history_recall_result: Any = None,
    ) -> tuple:
        policy = EmotionRelationshipTriggerPolicy()
        result = policy.evaluate(round_snapshot, director_plan, history_recall_result)
        return (result,)
