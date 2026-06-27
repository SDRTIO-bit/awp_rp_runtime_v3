"""AWPV2WorldLifeDiagnostics — ComfyUI node for world-life diagnostics."""

from __future__ import annotations
from typing import Any

from ..contracts.world_life_result import WorldLifeResult
from ..contracts.world_life_trigger_diagnostics import WorldLifeTriggerDiagnostics


class AWPV2WorldLifeDiagnostics:
    """Output diagnostics for world-life trigger and execution."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "world_life_result": ("WORLD_LIFE_RESULT", {}),
            },
        }

    RETURN_TYPES = ("WORLD_LIFE_DIAGNOSTICS", "STRING")
    RETURN_NAMES = ("diagnostics", "diagnostics_text")
    FUNCTION = "diagnose"
    CATEGORY = "AWP V2/WorldLife"
    OUTPUT_NODE = True

    def diagnose(self, world_life_result: WorldLifeResult) -> tuple:
        diag = WorldLifeTriggerDiagnostics(
            diagnostics_id=f"wld_{world_life_result.result_id[:8]}",
            trace_id=world_life_result.trace_id,
            snapshot_id=world_life_result.snapshot_id,
            task_run_id=world_life_result.task_run_id,
            should_trigger=world_life_result.status != "no_trigger",
            candidates_generated=len(world_life_result.candidates) + len(world_life_result.rejected_candidates),
            candidates_accepted=len(world_life_result.candidates),
            candidates_rejected=len(world_life_result.rejected_candidates),
            degraded=world_life_result.status == "degraded",
            degraded_reasons=world_life_result.degraded_reasons,
        )
        text_parts = [
            f"触发: {diag.should_trigger}",
            f"生成: {diag.candidates_generated}",
            f"采纳: {diag.candidates_accepted}",
            f"拒绝: {diag.candidates_rejected}",
            f"降级: {diag.degraded}",
        ]
        return (diag, " | ".join(text_parts))
