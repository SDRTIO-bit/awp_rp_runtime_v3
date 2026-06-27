"""AWPV2MemoryCurationValidator — validates memory curation candidates.

ComfyUI node that validates candidates from the Memory Curator Agent.
"""

from __future__ import annotations

from typing import Any


class AWPV2MemoryCurationValidator:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "curation_result": ("MEMORY_CURATION_RESULT",),
                "curation_request": ("MEMORY_CURATION_REQUEST",),
            },
        }

    RETURN_TYPES = ("MEMORY_CURATION_RESULT",)
    RETURN_NAMES = ("validated_result",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2/Memory"

    def execute(
        self,
        curation_result: dict[str, Any],
        curation_request: dict[str, Any],
    ) -> tuple[dict[str, Any]]:
        from ..contracts.memory_curation_result import MemoryCurationResult
        from ..contracts.memory_curation_request import MemoryCurationRequest
        from ..runtime.memory_curation_validator import MemoryCurationValidator

        result = MemoryCurationResult.from_dict(curation_result)
        request = MemoryCurationRequest.from_dict(curation_request)

        # Re-validate accepted candidates
        validator = MemoryCurationValidator()
        validation = validator.validate_all(result.accepted_candidates, request)

        # Build updated result
        all_rejected = result.rejected_candidates + validation.rejected_candidates
        all_reasons = result.rejection_reasons + validation.rejection_reasons

        updated = MemoryCurationResult(
            result_id=result.result_id,
            trace_id=result.trace_id,
            turn_id=result.turn_id,
            card_id=result.card_id,
            session_id=result.session_id,
            accepted_candidates=validation.valid_candidates,
            rejected_candidates=all_rejected,
            rejection_reasons=all_reasons,
            degraded=result.degraded,
            degraded_reasons=list(result.degraded_reasons),
            total_candidates_generated=result.total_candidates_generated,
            total_candidates_accepted=len(validation.valid_candidates),
            total_candidates_rejected=len(all_rejected),
            active_memory_count_before=result.active_memory_count_before,
            active_memory_count_after=result.active_memory_count_after,
        )

        return (updated.to_dict(),)
