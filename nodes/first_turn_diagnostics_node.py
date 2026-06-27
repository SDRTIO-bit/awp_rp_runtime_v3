"""AWPV2FirstTurnDiagnostics -- outputs diagnostics for first turn execution."""

from __future__ import annotations

from typing import Any

from ..contracts.first_turn_diagnostics import FirstTurnDiagnostics


class AWPV2FirstTurnDiagnostics:
    """Output comprehensive diagnostics for first turn execution.

    Contains step-level tracking, validation results, worldbook retrieval
    explanation, dynamic agent dispositions, quality gate details,
    commit status, and memory curation outcome.
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "first_turn_request": ("FIRST_TURN_REQUEST",),
            },
            "optional": {
                "first_turn_context": ("FIRST_TURN_CONTEXT",),
                "first_turn_receipt": ("FIRST_TURN_RECEIPT",),
                "quality_decision": ("QUALITY_DECISION",),
                "validation_result": ("VALIDATION_RESULT",),
            },
        }

    RETURN_TYPES = ("DIAGNOSTICS",)
    RETURN_NAMES = ("diagnostics",)
    FUNCTION = "execute"
    CATEGORY = "AWP V2/First Turn"
    OUTPUT_NODE = True

    def execute(
        self,
        first_turn_request: dict[str, Any],
        first_turn_context: dict[str, Any] | None = None,
        first_turn_receipt: dict[str, Any] | None = None,
        quality_decision: dict[str, Any] | None = None,
        validation_result: dict[str, Any] | None = None,
    ) -> tuple[dict]:
        diag = FirstTurnDiagnostics(
            request_id=first_turn_request.get("request_id", ""),
            trace_id=first_turn_request.get("trace_id", ""),
            session_id=first_turn_request.get("session_id", ""),
        )

        # Collect validation info
        if validation_result:
            if not validation_result.get("valid", True):
                diag.validation_errors = validation_result.get("errors", [])
                diag.outcome = "failure"
            else:
                diag.steps_completed.append("validate_request")

        # Collect context info
        if first_turn_context:
            diag.steps_completed.extend([
                "load_binding", "verify_session", "load_opening",
                "load_worldbook", "retrieve_worldbook", "build_snapshot",
                "director_and_agents", "writer_and_quality",
            ])
            wb = first_turn_context.get("worldbook_retrieval", {})
            diag.worldbook_candidate_count = len(wb.get("candidate_entry_ids", []))
            diag.worldbook_activated_count = len(wb.get("activated_entry_ids", []))
            diag.worldbook_rejected_count = len(wb.get("rejected_entry_ids_with_reasons", {}))
            diag.worldbook_deferred_count = len(wb.get("deferred_entry_ids", []))
            diag.worldbook_disabled_count = len(wb.get("disabled_entry_ids", []))
            diag.worldbook_budget_dropped_count = len(wb.get("budget_dropped_entry_ids", []))

        # Collect quality info
        if quality_decision:
            diag.quality_verdict = quality_decision.get("verdict", "")
            diag.quality_blocking_reasons = quality_decision.get("blocking_reasons", [])

        # Collect receipt info
        if first_turn_receipt:
            diag.steps_completed.extend(["state_commit", "turn_commit", "memory_curation"])
            diag.card_state_commit_status = first_turn_receipt.get("card_state_commit_status", "")
            diag.turn_record_commit_status = first_turn_receipt.get("turn_record_commit_status", "")
            diag.memory_curation_status = first_turn_receipt.get("memory_curation_status", "")
            diag.outcome = "success"
        elif not diag.outcome:
            diag.outcome = "incomplete"

        return (diag.to_dict(),)


NODE_CLASS_MAPPINGS = {
    "AWPV2FirstTurnDiagnostics": AWPV2FirstTurnDiagnostics,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2FirstTurnDiagnostics": "AWP V2 首回合诊断",
}
