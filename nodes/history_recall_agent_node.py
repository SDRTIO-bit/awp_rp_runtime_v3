"""AWPV2HistoryRecallAgent — ComfyUI node for History/Recall Agent execution.

Runs the History/Recall Agent to produce structured historical evidence.
"""

from __future__ import annotations

from ..contracts.delegation_plan import DelegationTask
from ..runtime.history_recall_runtime import HistoryRecallRuntime
from ..runtime.history_recall_tool_profile import HISTORY_RECALL_TOOLS


class AWPV2HistoryRecallAgent:
    """Runs the History/Recall Agent."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "snapshot": ("ROUND_SNAPSHOT", {}),
                "trigger_result": ("TRIGGER_RESULT", {}),
                "task_id": ("STRING", {"default": "hist_1"}),
            },
        }

    RETURN_TYPES = ("HISTORY_RECALL_RESULT",)
    RETURN_NAMES = ("result",)
    FUNCTION = "run"
    CATEGORY = "AWP V2/History Recall"

    def run(self, snapshot, trigger_result, task_id="hist_1"):
        task = DelegationTask(
            task_id=task_id,
            role="history-recall",
            tool_allowlist=list(HISTORY_RECALL_TOOLS.keys()),
        )
        runtime = HistoryRecallRuntime()
        result = runtime.run(
            snapshot=snapshot,
            task=task,
            trigger_result=trigger_result,
        )
        return (result,)
