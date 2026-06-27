"""AWPV2HistoryRecallDiagnostics — ComfyUI node for history recall diagnostics.

Displays trigger reasons, tool usage, evidence stats, and timing.
"""

from __future__ import annotations


class AWPV2HistoryRecallDiagnostics:
    """Outputs diagnostics from history recall execution."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "history_recall_result": ("HISTORY_RECALL_RESULT", {}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("diagnostics_json",)
    FUNCTION = "diagnose"
    CATEGORY = "AWP V2/History Recall"

    def diagnose(self, history_recall_result):
        import json
        diag = {
            "result_id": history_recall_result.result_id,
            "status": history_recall_result.status.value,
            "focus_entities": history_recall_result.focus_entities,
            "evidence_count": len(history_recall_result.evidence),
            "confirmed_facts_count": len(history_recall_result.confirmed_facts),
            "conflicts_count": len(history_recall_result.conflicts),
            "continuity_risks_count": len(history_recall_result.continuity_risks),
            "degraded_reasons": history_recall_result.degraded_reasons,
        }
        return (json.dumps(diag, ensure_ascii=False, indent=2),)
