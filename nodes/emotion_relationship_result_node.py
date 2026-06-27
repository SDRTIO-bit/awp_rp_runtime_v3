"""AWPV2EmotionRelationshipResult — ComfyUI node for outputting EmotionRelationshipResult."""

from __future__ import annotations
from typing import Any

from ..contracts.emotion_relationship_result import EmotionRelationshipResult


class AWPV2EmotionRelationshipResult:
    """Output EmotionRelationshipResult fields for downstream consumption."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "er_result": ("ER_RESULT", {}),
            },
        }

    RETURN_TYPES = ("ER_RESULT", "STRING")
    RETURN_NAMES = ("er_result", "summary")
    FUNCTION = "output"
    CATEGORY = "AWP V2/EmotionRelationship"

    def output(self, er_result: EmotionRelationshipResult) -> tuple:
        status = er_result.status.value
        summary_parts = [
            f"状态: {status}",
            f"候选数: {len(er_result.candidates)}",
            f"拒绝数: {len(er_result.rejected_candidates)}",
        ]
        if er_result.degraded_reasons:
            summary_parts.append(f"降级原因: {'; '.join(er_result.degraded_reasons)}")
        summary = " | ".join(summary_parts)
        return (er_result, summary)
