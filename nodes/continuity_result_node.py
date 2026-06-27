"""AWPV2ContinuityResult — ComfyUI node for outputting ContinuityResult."""

from __future__ import annotations
from typing import Any

from ..contracts.continuity_result import ContinuityResult


class AWPV2ContinuityResult:
    """Output ContinuityResult fields for downstream consumption."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "continuity_result": ("CONTINUITY_RESULT", {}),
            },
        }

    RETURN_TYPES = ("CONTINUITY_RESULT", "STRING", "STRING")
    RETURN_NAMES = ("continuity_result", "status", "summary")
    FUNCTION = "output"
    CATEGORY = "AWP V2/Continuity"

    def output(self, continuity_result: ContinuityResult) -> tuple:
        status = continuity_result.status.value
        summary_parts = [
            f"状态: {status}",
            f"blocking: {len(continuity_result.blocking_issues)}",
            f"warning: {len(continuity_result.warnings)}",
            f"info: {len(continuity_result.informational_notes)}",
        ]
        if continuity_result.writer_constraints:
            summary_parts.append(f"约束: {len(continuity_result.writer_constraints)}")
        if continuity_result.degraded_reasons:
            summary_parts.append(f"降级: {'; '.join(continuity_result.degraded_reasons)}")
        summary = " | ".join(summary_parts)
        return (continuity_result, status, summary)
