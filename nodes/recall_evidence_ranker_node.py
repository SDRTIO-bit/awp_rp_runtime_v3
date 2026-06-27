"""AWPV2RecallEvidenceRanker — ComfyUI node for evidence ranking.

Ranks recall evidence by source priority, confidence, and recency.
"""

from __future__ import annotations

from ..runtime.recall_evidence_ranker import RecallEvidenceRanker


class AWPV2RecallEvidenceRanker:
    """Ranks recall evidence deterministically."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "history_recall_result": ("HISTORY_RECALL_RESULT", {}),
            },
        }

    RETURN_TYPES = ("HISTORY_RECALL_RESULT",)
    RETURN_NAMES = ("ranked_result",)
    FUNCTION = "rank"
    CATEGORY = "AWP V2/History Recall"

    def rank(self, history_recall_result):
        ranker = RecallEvidenceRanker()
        ranked = ranker.rank(history_recall_result.evidence)
        # Update the result with ranked evidence
        history_recall_result.evidence = ranked
        return (history_recall_result,)
