"""AWPV2OpportunityResult — ComfyUI node for outputting OpportunityResult."""

from __future__ import annotations
from typing import Any

from ..contracts.opportunity_result import OpportunityResult


class AWPV2OpportunityResult:
    """Output OpportunityResult fields for downstream consumption."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "opportunity_result": ("OPPORTUNITY_RESULT", {}),
            },
        }

    RETURN_TYPES = ("OPPORTUNITY_RESULT", "STRING", "STRING")
    RETURN_NAMES = ("opportunity_result", "status", "summary")
    FUNCTION = "output"
    CATEGORY = "AWP V2/Opportunity"

    def output(self, opportunity_result: OpportunityResult) -> tuple:
        status = opportunity_result.status.value
        summary_parts = [
            f"状态: {status}",
            f"候选数: {len(opportunity_result.candidates)}",
            f"拒绝数: {len(opportunity_result.rejected_candidates)}",
        ]
        if opportunity_result.degraded_reasons:
            summary_parts.append(f"降级原因: {'; '.join(opportunity_result.degraded_reasons)}")
        summary = " | ".join(summary_parts)
        return (opportunity_result, status, summary)
