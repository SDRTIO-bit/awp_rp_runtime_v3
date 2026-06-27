"""AWPV2EmotionRelationshipDiagnostics — ComfyUI node for emotion/relationship diagnostics."""

from __future__ import annotations
from typing import Any

from ..contracts.emotion_relationship_result import EmotionRelationshipResult
from ..contracts.emotion_relationship_trigger_diagnostics import EmotionRelationshipTriggerDiagnostics


class AWPV2EmotionRelationshipDiagnostics:
    """Output diagnostics for emotion/relationship trigger and execution."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "er_result": ("ER_RESULT", {}),
            },
        }

    RETURN_TYPES = ("ER_DIAGNOSTICS",)
    RETURN_NAMES = ("diagnostics",)
    FUNCTION = "diagnose"
    CATEGORY = "AWP V2/EmotionRelationship"

    def diagnose(self, er_result: EmotionRelationshipResult) -> tuple:
        diag = EmotionRelationshipTriggerDiagnostics(
            diagnostics_id=f"erd_{er_result.result_id[:8]}",
            trace_id=er_result.trace_id,
            snapshot_id=er_result.snapshot_id,
            task_run_id=er_result.task_run_id,
            should_trigger=er_result.status != "no_trigger",
            candidates_generated=len(er_result.candidates) + len(er_result.rejected_candidates),
            candidates_accepted=len(er_result.candidates),
            candidates_rejected=len(er_result.rejected_candidates),
            degraded=er_result.status == "degraded",
            degraded_reasons=er_result.degraded_reasons,
        )
        return (diag,)
