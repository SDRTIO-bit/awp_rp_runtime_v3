"""AWPV2CardSessionBootstrapDiagnostics — outputs bootstrap diagnostic summary."""

from __future__ import annotations
from typing import Any


class AWPV2CardSessionBootstrapDiagnostics:
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
                "session_binding": ("CARD_SESSION_BINDING",),
            },
        }

    RETURN_TYPES = ("DIAGNOSTICS",)
    RETURN_NAMES = ("diagnostics",)
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
        session_binding: dict,
    ) -> tuple[dict]:
        from ..contracts.card_session_bootstrap_request import CardSessionBootstrapRequest
        from ..contracts.card_definition import CardDefinition
        from ..contracts.greeting_selection import GreetingSelection
        from ..contracts.opening_record import OpeningRecord
        from ..contracts.worldbook_binding import WorldbookBinding
        from ..contracts.card_state import CardState
        from ..contracts.card_session_binding import CardSessionBinding
        from ..contracts.card_session_bootstrap_diagnostics import CardSessionBootstrapDiagnostics

        req = CardSessionBootstrapRequest.from_dict(bootstrap_request)
        defn = CardDefinition.from_dict(card_definition)
        sel = GreetingSelection.from_dict(greeting_selection)
        opr = OpeningRecord.from_dict(opening_record)
        wb = WorldbookBinding.from_dict(worldbook_binding)
        cs = CardState.from_dict(card_state)
        binding = CardSessionBinding.from_dict(session_binding)

        diag = CardSessionBootstrapDiagnostics(
            logical_card_id=defn.logical_card_id,
            card_version=defn.card_version,
            source_hash=defn.source_hash,
            session_id=req.session_id,
            request_id=req.request_id,
            selected_greeting_id=sel.greeting_id,
            opening_record_id=opr.opening_record_id,
            worldbook_binding_id=wb.worldbook_binding_id,
            card_state_revision_before=0,
            card_state_revision_after=cs.revision,
            bound_entry_count=len(wb.bound_entry_ids),
            disabled_entry_count=len(wb.disabled_entry_ids),
            deferred_entry_count=len(wb.deferred_entry_ids),
            commit_status=binding.status,
            idempotency_status="new",
        )
        return (diag.to_dict(),)
