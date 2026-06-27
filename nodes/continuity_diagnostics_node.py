"""AWPV2ContinuityDiagnostics — ComfyUI node for Continuity diagnostics."""

from __future__ import annotations
from typing import Any

from ..contracts.continuity_result import ContinuityResult
from ..contracts.continuity_trigger_diagnostics import ContinuityTriggerDiagnostics
from ..runtime.continuity_trigger_policy import ContinuityTriggerResult


class AWPV2ContinuityDiagnostics:
    """Output diagnostics for Continuity Agent execution."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "continuity_result": ("CONTINUITY_RESULT", {}),
                "trigger_result": ("CONTINUITY_TRIGGER_RESULT", {}),
            },
        }

    RETURN_TYPES = ("CONTINUITY_TRIGGER_DIAGNOSTICS", "STRING")
    RETURN_NAMES = ("diagnostics", "diagnostics_summary")
    FUNCTION = "diagnose"
    CATEGORY = "AWP V2/Continuity"
    OUTPUT_NODE = True

    def diagnose(
        self,
        continuity_result: ContinuityResult,
        trigger_result: ContinuityTriggerResult,
    ) -> tuple:
        from ..contracts.continuity_issue import ContinuitySeverity
        blocking_count = len([i for i in continuity_result.issues if i.severity == ContinuitySeverity.BLOCKING])
        warning_count = len([i for i in continuity_result.issues if i.severity == ContinuitySeverity.WARNING])
        info_count = len([i for i in continuity_result.issues if i.severity == ContinuitySeverity.INFO])

        diagnostics = ContinuityTriggerDiagnostics(
            diagnostics_id=f"cld_{continuity_result.result_id}",
            trace_id=continuity_result.trace_id,
            snapshot_id=continuity_result.snapshot_id,
            task_run_id=continuity_result.task_run_id,
            should_trigger=trigger_result.should_trigger,
            trigger_reasons=trigger_result.trigger_reasons,
            continuity_domains=trigger_result.continuity_domains,
            focus_entities=trigger_result.focus_entities,
            focus_locations=trigger_result.focus_locations,
            focus_turns=trigger_result.focus_turns,
            risk_level=trigger_result.risk_level,
            max_issue_count=trigger_result.max_issue_count,
            issues_detected=len(continuity_result.issues),
            issues_blocking=blocking_count,
            issues_warning=warning_count,
            issues_info=info_count,
            degraded=(continuity_result.status.value == "degraded"),
            degraded_reasons=continuity_result.degraded_reasons,
        )

        summary_parts = [
            f"触发: {diagnostics.should_trigger}",
            f"风险: {diagnostics.risk_level}",
            f"issue: {diagnostics.issues_detected}",
            f"blocking: {diagnostics.issues_blocking}",
            f"warning: {diagnostics.issues_warning}",
        ]
        if diagnostics.trigger_reasons:
            summary_parts.append(f"原因: {diagnostics.trigger_reasons[0][:30]}")

        return (diagnostics, " | ".join(summary_parts))
