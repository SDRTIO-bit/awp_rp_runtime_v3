"""AWPV2HistoryRecallTrigger — ComfyUI node for History Recall trigger policy.

Evaluates whether a history recall task should be created.
"""

from __future__ import annotations

from ..runtime.history_recall_trigger_policy import HistoryRecallTriggerPolicy


class AWPV2HistoryRecallTrigger:
    """Evaluates whether history recall should be triggered."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "snapshot": ("ROUND_SNAPSHOT", {}),
                "director_plan": ("DIRECTOR_PLAN", {}),
            },
        }

    RETURN_TYPES = ("TRIGGER_RESULT",)
    RETURN_NAMES = ("trigger_result",)
    FUNCTION = "evaluate"
    CATEGORY = "AWP V2/History Recall"

    def evaluate(self, snapshot, director_plan):
        policy = HistoryRecallTriggerPolicy()
        result = policy.evaluate(snapshot, director_plan)
        return (result,)
