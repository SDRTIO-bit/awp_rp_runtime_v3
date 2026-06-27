"""AWPV2WorldbookBindingBuilder — builds a WorldbookBinding from CardDefinition."""

from __future__ import annotations
import hashlib
from typing import Any


class AWPV2WorldbookBindingBuilder:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "bootstrap_request": ("BOOTSTRAP_REQUEST",),
                "card_definition": ("CARD_DEFINITION",),
            },
        }

    RETURN_TYPES = ("WORLDBOOK_BINDING",)
    RETURN_NAMES = ("worldbook_binding",)
    FUNCTION = "execute"
    CATEGORY = "AWP/CardSession"

    def execute(self, bootstrap_request: dict, card_definition: dict) -> tuple[dict]:
        from datetime import datetime, timezone
        from ..contracts.card_definition import CardDefinition
        from ..contracts.card_session_bootstrap_request import CardSessionBootstrapRequest
        from ..contracts.worldbook_binding import WorldbookBinding, WorldbookBindingEntry

        req = CardSessionBootstrapRequest.from_dict(bootstrap_request)
        defn = CardDefinition.from_dict(card_definition)
        now = datetime.now(timezone.utc).isoformat()

        binding_id = f"wb_{hashlib.sha256(f'{req.session_id}_{defn.logical_card_id}'.encode()).hexdigest()[:16]}"

        bound_ids: list[str] = []
        disabled_ids: list[str] = []
        deferred_ids: list[str] = []
        unsupported_ids: list[str] = []
        chunk_ids: list[str] = []
        entries: list[dict[str, Any]] = []

        for e_data in defn.worldbook_catalog:
            entry_id = e_data.get("entry_id", "")
            enabled = e_data.get("enabled", True)
            constant = e_data.get("constant", False)
            selective = e_data.get("selective", False)
            has_chunks = e_data.get("has_chunks", False)

            if not enabled:
                disabled_ids.append(entry_id)
                status = "disabled"
            elif selective:
                deferred_ids.append(entry_id)
                status = "deferred"
            elif constant:
                bound_ids.append(entry_id)
                status = "candidate"
            else:
                bound_ids.append(entry_id)
                status = "candidate"

            if has_chunks:
                for c_data in defn.worldbook_chunks:
                    if c_data.get("parent_entry_id") == entry_id:
                        cid = c_data.get("chunk_id", "")
                        if cid:
                            chunk_ids.append(cid)

            entries.append(WorldbookBindingEntry(
                entry_id=entry_id,
                source_uid=e_data.get("source_uid", -1),
                enabled=enabled,
                constant=constant,
                selective=selective,
                has_chunks=has_chunks,
                chunk_ids=[c.get("chunk_id", "") for c in defn.worldbook_chunks if c.get("parent_entry_id") == entry_id],
                activation_status=status,
            ).to_dict())

        binding = WorldbookBinding(
            worldbook_binding_id=binding_id,
            session_id=req.session_id,
            logical_card_id=defn.logical_card_id,
            card_version=defn.card_version,
            source_hash=defn.source_hash,
            catalog_ref=f"{defn.logical_card_id}/v{defn.card_version}/worldbook",
            bound_entry_ids=bound_ids,
            bound_chunk_ids=chunk_ids,
            disabled_entry_ids=disabled_ids,
            deferred_entry_ids=deferred_ids,
            unsupported_activation_entry_ids=unsupported_ids,
            entries=entries,
            created_at=now,
        )
        return (binding.to_dict(),)
