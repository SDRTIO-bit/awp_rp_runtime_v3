"""AWPV2WorldLifeResult — ComfyUI node for outputting WorldLifeResult."""

from __future__ import annotations
from typing import Any

from ..contracts.world_life_result import WorldLifeResult


class AWPV2WorldLifeResult:
    """Output WorldLifeResult fields for downstream consumption."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "world_life_result": ("WORLD_LIFE_RESULT", {}),
            },
        }

    RETURN_TYPES = ("WORLD_LIFE_RESULT", "STRING", "STRING")
    RETURN_NAMES = ("world_life_result", "status", "summary")
    FUNCTION = "output"
    CATEGORY = "AWP V2/WorldLife"

    def output(self, world_life_result: WorldLifeResult) -> tuple:
        status = world_life_result.status.value
        summary_parts = [
            f"状态: {status}",
            f"候选数: {len(world_life_result.candidates)}",
            f"拒绝数: {len(world_life_result.rejected_candidates)}",
        ]
        if world_life_result.degraded_reasons:
            summary_parts.append(f"降级原因: {'; '.join(world_life_result.degraded_reasons)}")
        summary = " | ".join(summary_parts)
        return (world_life_result, status, summary)
