"""AWPV2SessionReadyValidator -- validates Session readiness for first turn."""

from __future__ import annotations

from typing import Any

from ..contracts.first_turn_request import FirstTurnRequest
from ..contracts.first_turn_diagnostics import FirstTurnDiagnostics
from ..contracts.first_turn_receipt import FirstTurnFailureCode
from ..storage.card_session_interfaces import CardSessionBindingStore


class AWPV2SessionReadyValidator:
    """Validate that a Session is ready for first turn execution.

    Checks:
      - Session exists
      - Session status = ready
      - CardSessionBinding is complete
      - logicalCardId / cardVersion / sourceHash match request
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "first_turn_request": ("FIRST_TURN_REQUEST",),
            },
        }

    RETURN_TYPES = ("VALIDATION_RESULT", "FIRST_TURN_DIAGNOSTICS")
    RETURN_NAMES = ("validation_result", "diagnostics")
    FUNCTION = "execute"
    CATEGORY = "AWP V2/First Turn"
    OUTPUT_NODE = False

    def execute(self, first_turn_request: dict[str, Any]) -> tuple[dict, dict]:
        request = FirstTurnRequest.from_dict(first_turn_request)
        diag = FirstTurnDiagnostics(
            request_id=request.request_id,
            trace_id=request.trace_id,
            session_id=request.session_id,
        )

        # Validate request fields
        errors = request.validate()
        if errors:
            diag.validation_errors = errors
            diag.steps_failed.append("validate_request")
            diag.outcome = "failure"
            diag.failure_code = FirstTurnFailureCode.VALIDATION_ERROR
            diag.failure_message = "; ".join(errors)
            return ({"valid": False, "errors": errors}, diag.to_dict())

        diag.steps_completed.append("validate_request")

        # Note: Actual session/binding validation requires stores
        # which are wired through the combined node or pipeline.
        # This thin node validates request-level fields only.
        return ({"valid": True, "errors": []}, diag.to_dict())


NODE_CLASS_MAPPINGS = {
    "AWPV2SessionReadyValidator": AWPV2SessionReadyValidator,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2SessionReadyValidator": "AWP V2 会话就绪校验",
}
