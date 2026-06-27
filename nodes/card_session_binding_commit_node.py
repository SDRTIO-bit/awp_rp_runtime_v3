"""AWPV2CardSessionBindingCommit — commits the final CardSessionBinding."""

from __future__ import annotations
from typing import Any


class AWPV2CardSessionBindingCommit:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "bootstrap_request": ("BOOTSTRAP_REQUEST",),
                "card_definition": ("CARD_DEFINITION",),
                "greeting_selection": ("GREETING_SELECTION",),
                "opening_record": ("OPENING_RECORD",),
                "worldbook_binding": ("WORLDBOOK_BINDING",),
                "card_state": ("CARD_STATE",),
            },
        }

    RETURN_TYPES = ("CARD_SESSION_BINDING", "BOOTSTRAP_RECEIPT")
    RETURN_NAMES = ("session_binding", "bootstrap_receipt")
    FUNCTION = "execute"
    CATEGORY = "AWP/CardSession"

    def execute(
        self,
        bootstrap_request: dict,
        card_definition: dict,
        greeting_selection: dict,
        opening_record: dict,
        worldbook_binding: dict,
        card_state: dict,
    ) -> tuple[dict, dict]:
        import hashlib
        from datetime import datetime, timezone
        from ..contracts.card_session_binding import CardSessionBinding, CardSessionBindingStatus
        from ..contracts.card_session_bootstrap_receipt import CardSessionBootstrapReceipt
        from ..contracts.card_session_bootstrap_request import CardSessionBootstrapRequest
        from ..contracts.card_definition import CardDefinition
        from ..contracts.greeting_selection import GreetingSelection
        from ..contracts.opening_record import OpeningRecord
        from ..contracts.worldbook_binding import WorldbookBinding
        from ..contracts.card_state import CardState

        req = CardSessionBootstrapRequest.from_dict(bootstrap_request)
        defn = CardDefinition.from_dict(card_definition)
        sel = GreetingSelection.from_dict(greeting_selection)
        opr = OpeningRecord.from_dict(opening_record)
        wb = WorldbookBinding.from_dict(worldbook_binding)
        cs = CardState.from_dict(card_state)
        now = datetime.now(timezone.utc).isoformat()

        # Create binding
        binding = CardSessionBinding(
            session_id=req.session_id,
            logical_card_id=defn.logical_card_id,
            card_version=defn.card_version,
            source_hash=defn.source_hash,
            card_definition_ref=f"{defn.logical_card_id}/v{defn.card_version}",
            selected_greeting_id=sel.greeting_id,
            worldbook_binding_id=wb.worldbook_binding_id,
            opening_record_id=opr.opening_record_id,
            created_at=now,
            status=CardSessionBindingStatus.READY,
        )

        # Create receipt
        receipt_id = f"rcpt_{hashlib.sha256(f'{req.request_id}_{req.session_id}'.encode()).hexdigest()[:16]}"
        receipt = CardSessionBootstrapReceipt(
            receipt_id=receipt_id,
            request_id=req.request_id,
            workflow_run_id=req.workflow_run_id,
            trace_id=req.trace_id,
            session_id=req.session_id,
            logical_card_id=defn.logical_card_id,
            card_version=defn.card_version,
            source_hash=defn.source_hash,
            greeting_id=sel.greeting_id,
            opening_record_id=opr.opening_record_id,
            worldbook_binding_id=wb.worldbook_binding_id,
            card_state_revision=cs.revision,
            commit_status="success",
            idempotency_status="new",
            created_at=now,
        )

        return (binding.to_dict(), receipt.to_dict())
