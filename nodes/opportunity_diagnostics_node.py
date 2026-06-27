"""AWPV2OpportunityDiagnostics — ComfyUI node for opportunity diagnostics."""

from __future__ import annotations
from typing import Any

from ..contracts.opportunity_result import OpportunityResult
from ..contracts.opportunity_trigger_diagnostics import OpportunityTriggerDiagnostics


class AWPV2OpportunityDiagnostics:
    """Output diagnostics for opportunity trigger and execution."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "opportunity_result": ("OPPORTUNITY_RESULT", {}),
            },
        }

    RETURN_TYPES = ("OPPORTUNITY_DIAGNOSTICS", "STRING")
    RETURN_NAMES = ("diagnostics", "diagnostics_text")
    FUNCTION = "diagnose"
    CATEGORY = "AWP V2/Opportunity"
    OUTPUT_NODE = True

    def diagnose(self, opportunity_result: OpportunityResult) -> tuple:
        diag = OpportunityTriggerDiagnostics(
            diagnostics_id=f"od_{opportunity_result.result_id[:8]}",
            trace_id=opportunity_result.trace_id,
            snapshot_id=opportunity_result.snapshot_id,
            task_run_id=opportunity_result.task_run_id,
            should_trigger=opportunity_result.status != "no_trigger",
            candidates_generated=len(opportunity_result.candidates) + len(opportunity_result.rejected_candidates),
            candidates_accepted=len(opportunity_result.candidates),
            candidates_rejected=len(opportunity_result.rejected_candidates),
            degraded=opportunity_result.status == "degraded",
            degraded_reasons=opportunity_result.degraded_reasons,
        )
        text_parts = [
            f"触发: {diag.should_trigger}",
            f"生成: {diag.candidates_generated}",
            f"采纳: {diag.candidates_accepted}",
            f"拒绝: {diag.candidates_rejected}",
            f"降级: {diag.degraded}",
        ]
        return (diag, " | ".join(text_parts))
