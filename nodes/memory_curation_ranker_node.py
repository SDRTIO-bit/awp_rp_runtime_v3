"""AWPV2MemoryCurationRanker — ranks memory curation candidates.

ComfyUI node that ranks candidates from the Memory Curator Agent.
"""

from __future__ import annotations

from typing import Any


class AWPV2MemoryCurationRanker:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "curation_result": ("MEMORY_CURATION_RESULT",),
            },
            "optional": {
                "current_active_count": ("INT", {"default": 0, "min": 0, "max": 15}),
                "max_active_candidates": ("INT", {"default": 5, "min": 1, "max": 15}),
                "max_rag_candidates": ("INT", {"default": 5, "min": 1, "max": 20}),
            },
        }

    RETURN_TYPES = ("MEMORY_CURATION_RESULT",)
    RETURN_NAMES = ("ranked_result",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2/Memory"

    def execute(
        self,
        curation_result: dict[str, Any],
        current_active_count: int = 0,
        max_active_candidates: int = 5,
        max_rag_candidates: int = 5,
    ) -> tuple[dict[str, Any]]:
        from ..contracts.memory_curation_result import MemoryCurationResult
        from ..runtime.memory_curation_ranker import MemoryCurationRanker

        result = MemoryCurationResult.from_dict(curation_result)

        ranker = MemoryCurationRanker()
        ranking = ranker.rank(
            result.accepted_candidates,
            current_active_count=current_active_count,
            max_active_candidates=max_active_candidates,
            max_rag_candidates=max_rag_candidates,
        )

        all_rejected = result.rejected_candidates + ranking.rejected
        all_reasons = result.rejection_reasons + ranking.rejection_reasons

        updated = MemoryCurationResult(
            result_id=result.result_id,
            trace_id=result.trace_id,
            turn_id=result.turn_id,
            card_id=result.card_id,
            session_id=result.session_id,
            accepted_candidates=ranking.accepted,
            rejected_candidates=all_rejected,
            rejection_reasons=all_reasons,
            degraded=result.degraded,
            degraded_reasons=list(result.degraded_reasons),
            total_candidates_generated=result.total_candidates_generated,
            total_candidates_accepted=len(ranking.accepted),
            total_candidates_rejected=len(all_rejected),
            active_memory_count_before=result.active_memory_count_before,
            active_memory_count_after=result.active_memory_count_after,
        )

        return (updated.to_dict(),)
