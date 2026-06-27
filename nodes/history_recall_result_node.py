"""AWPV2HistoryRecallResult — ComfyUI node for HistoryRecallResult output.

Displays the structured history recall result.
"""

from __future__ import annotations


class AWPV2HistoryRecallResult:
    """Outputs HistoryRecallResult for downstream consumption."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "history_recall_result": ("HISTORY_RECALL_RESULT", {}),
            },
        }

    RETURN_TYPES = ("HISTORY_RECALL_RESULT",)
    RETURN_NAMES = ("result",)
    FUNCTION = "output"
    CATEGORY = "AWP V2/History Recall"

    def output(self, history_recall_result):
        return (history_recall_result,)
