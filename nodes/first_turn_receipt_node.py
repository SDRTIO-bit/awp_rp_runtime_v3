"""AWPV2FirstTurnReceipt -- produces FirstTurnReceipt from committed state."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from ..contracts.first_turn_receipt import FirstTurnReceipt


class AWPV2FirstTurnReceipt:
    """Produce FirstTurnReceipt after successful first turn execution.

    Only issued when:
      - Quality Gate accepted
      - CardState committed
      - TurnRecord committed
      - D6 Memory Curator completed (or explicit no-op)
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "first_turn_request": ("FIRST_TURN_REQUEST",),
                "quality_decision": ("QUALITY_DECISION",),
                "card_state_commit_result": ("CARD_STATE_COMMIT_RESULT",),
                "turn_record": ("TURN_RECORD",),
            },
            "optional": {
                "memory_curation_status": ("STRING", {"default": "noop"}),
                "active_memory_write_count": ("INT", {"default": 0}),
                "rag_memory_write_count": ("INT", {"default": 0}),
            },
        }

    RETURN_TYPES = ("FIRST_TURN_RECEIPT",)
    RETURN_NAMES = ("first_turn_receipt",)
    FUNCTION = "execute"
    CATEGORY = "AWP V2/First Turn"
    OUTPUT_NODE = True

    def execute(
        self,
        first_turn_request: dict[str, Any],
        quality_decision: dict[str, Any],
        card_state_commit_result: dict[str, Any],
        turn_record: dict[str, Any],
        memory_curation_status: str = "noop",
        active_memory_write_count: int = 0,
        rag_memory_write_count: int = 0,
    ) -> tuple[dict]:
        now = datetime.now(timezone.utc).isoformat()
        request_id = first_turn_request.get("request_id", "")
        seed = f"{request_id}:{now}"
        receipt_id = f"ftr_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"

        receipt = FirstTurnReceipt(
            receipt_id=receipt_id,
            request_id=request_id,
            workflow_run_id=first_turn_request.get("workflow_run_id", ""),
            trace_id=first_turn_request.get("trace_id", ""),
            turn_id=first_turn_request.get("turn_id", ""),
            attempt_id=first_turn_request.get("attempt_id", ""),
            session_id=first_turn_request.get("session_id", ""),
            logical_card_id=first_turn_request.get("expected_logical_card_id", ""),
            card_version=first_turn_request.get("expected_card_version", 0),
            source_hash=first_turn_request.get("expected_source_hash", ""),
            quality_verdict=quality_decision.get("verdict", ""),
            base_card_state_revision=card_state_commit_result.get("from_revision", 0),
            result_card_state_revision=card_state_commit_result.get("to_revision", 0),
            card_state_commit_status=card_state_commit_result.get("status", ""),
            turn_record_id=turn_record.get("turn_id", ""),
            turn_index=turn_record.get("turn_index", 0),
            turn_record_commit_status="committed",
            memory_curation_status=memory_curation_status,
            active_memory_write_count=active_memory_write_count,
            rag_memory_write_count=rag_memory_write_count,
            idempotency_status="new",
            created_at=now,
        )
        return (receipt.to_dict(),)


NODE_CLASS_MAPPINGS = {
    "AWPV2FirstTurnReceipt": AWPV2FirstTurnReceipt,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2FirstTurnReceipt": "AWP V2 首回合收据",
}
