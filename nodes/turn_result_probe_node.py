"""AWPV2TurnResultProbe — terminal output node for ComfyUI /history.

Reads a completed TurnReceipt or TurnRecord and produces a history-safe
UI payload. Never writes full text, prompts, card content, or secrets.

OUTPUT_NODE = True, returns {"ui": {"awp_turn_result_json": [...]}}.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..contracts.turn_result_projection import TurnResultProjection


class AWPV2TurnResultProbe:
    """Terminal output node that projects turn results into /history.

    Reads the receipt (FirstTurnReceipt or continuation receipt), the
    diagnostics, and optionally the turn_record to build a safe projection.
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "receipt": ("JSON",),
            },
            "optional": {
                "diagnostics": ("JSON",),
                "turn_record": ("JSON",),
                "prompt_id": ("STRING", {"default": ""}),
                "turn_kind": ("STRING", {"default": "first"}),
            },
        }

    RETURN_TYPES = ()
    RETURN_NAMES = ()
    FUNCTION = "execute"
    CATEGORY = "AWP V2/Turn Result"
    OUTPUT_NODE = True

    def execute(
        self,
        receipt: dict[str, Any],
        diagnostics: dict[str, Any] | None = None,
        turn_record: dict[str, Any] | None = None,
        prompt_id: str = "",
        turn_kind: str = "first",
    ) -> dict[str, Any]:
        diag = diagnostics or {}
        tr = turn_record or {}

        # Extract accepted text for hash only (never include in projection)
        accepted_text = receipt.get("accepted_text", "")
        if not accepted_text and tr:
            accepted_text = tr.get("writer_output", "")
        text_hash = hashlib.sha256(accepted_text.encode("utf-8")).hexdigest() if accepted_text else ""

        # Build history-safe projection
        projection = TurnResultProjection(
            workflow_run_id=receipt.get("workflow_run_id", ""),
            trace_id=receipt.get("trace_id", ""),
            prompt_id=prompt_id,
            turn_id=receipt.get("turn_id", ""),
            attempt_id=receipt.get("attempt_id", ""),
            session_id=receipt.get("session_id", ""),
            turn_index=receipt.get("turn_index", tr.get("turn_index", 0)),
            turn_kind=turn_kind,
            quality_status=receipt.get("quality_verdict", ""),
            receipt_status=receipt.get("turn_record_commit_status", ""),
            turn_record_id=receipt.get("turn_record_id", tr.get("turn_id", "")),
            accepted_text_hash=text_hash,
            accepted_text_length=len(accepted_text),
            card_state_revision_before=receipt.get("base_card_state_revision", 0),
            card_state_revision_after=receipt.get("result_card_state_revision", 0),
            worldbook_activated_entry_ids=receipt.get("worldbook_activated_entry_ids", []),
            worldbook_deferred_entry_ids=receipt.get("worldbook_deferred_entry_ids", []),
            memory_disposition=receipt.get("memory_curation_status", "noop"),
            provider_usage_summary={
                "director_model": diag.get("director_model", ""),
                "writer_model": diag.get("writer_model", ""),
                "provider_calls": diag.get("provider_call_count", 0),
            },
            diagnostic_status=diag.get("outcome", "success"),
            failure_code=diag.get("failure_code", ""),
            failure_message=diag.get("failure_message", ""),
            idempotency_status=receipt.get("idempotency_status", ""),
            created_at=receipt.get("created_at", diag.get("created_at", "")),
        )

        # Serialize to JSON string for ui payload
        projection_json = json.dumps(projection.to_dict(), ensure_ascii=False, indent=2)

        return {"ui": {"awp_turn_result_json": [projection_json]}}


NODE_CLASS_MAPPINGS = {
    "AWPV2TurnResultProbe": AWPV2TurnResultProbe,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2TurnResultProbe": "AWP V2 Turn Result Probe",
}
