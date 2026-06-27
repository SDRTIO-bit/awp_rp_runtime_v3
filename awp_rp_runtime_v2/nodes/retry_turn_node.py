"""AWPV2RetryTurn — handle turn retry.

Retry does NOT overwrite accepted TurnRecords.
Creates new attempt with new patchId and traceId.
"""

from __future__ import annotations

from typing import Any


class AWPV2RetryTurn:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "quality_decision": ("QUALITY_DECISION",),
            },
        }

    RETURN_TYPES = ("STRING", "BOOLEAN", "INT")
    RETURN_NAMES = ("retry_context", "can_retry", "new_retry_count")
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(self, quality_decision: dict[str, Any]) -> tuple[str, bool, int]:
        from ..contracts.quality_decision import QualityDecision

        decision = QualityDecision.from_dict(quality_decision)

        if decision.is_rejected():
            return (
                "Cannot retry: verdict is 'reject' (final). "
                f"Reasons: {decision.blocking_reasons}",
                False,
                decision.retry_count,
            )

        if not decision.can_retry():
            return (
                f"Cannot retry: count={decision.retry_count}, max={decision.max_retries}",
                False,
                decision.retry_count,
            )

        new_count = decision.retry_count + 1
        context = (
            f"Retry #{new_count}/{decision.max_retries}. "
            f"Previous blocking reasons: {decision.blocking_reasons}. "
            "Please address these issues."
        )
        return (context, True, new_count)
