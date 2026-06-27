"""AWPV2CardDefinitionReadyValidator — validates a CardDefinition is ready for bootstrap."""

from __future__ import annotations
from typing import Any


class AWPV2CardDefinitionReadyValidator:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "bootstrap_request": ("BOOTSTRAP_REQUEST",),
                "card_definition": ("CARD_DEFINITION",),
            },
        }

    RETURN_TYPES = ("CARD_DEFINITION", "VALIDATION_RESULT")
    RETURN_NAMES = ("card_definition", "validation_result")
    FUNCTION = "execute"
    CATEGORY = "AWP/CardSession"

    def execute(self, bootstrap_request: dict, card_definition: dict) -> tuple[dict, dict]:
        from ..contracts.card_definition import CardDefinition, CardDefinitionStatus
        from ..contracts.card_session_bootstrap_request import CardSessionBootstrapRequest

        req = CardSessionBootstrapRequest.from_dict(bootstrap_request)
        defn = CardDefinition.from_dict(card_definition)

        errors: list[str] = []

        # Check card exists
        if not defn.logical_card_id:
            errors.append("CardDefinition is empty")

        # Check card is ready
        if defn.status != CardDefinitionStatus.READY:
            errors.append(f"Card status is '{defn.status}', expected 'ready'")

        # Check version matches
        if defn.card_version != req.card_version:
            errors.append(f"Card version mismatch: requested {req.card_version}, got {defn.card_version}")

        # Check logical card ID matches
        if defn.logical_card_id != req.logical_card_id:
            errors.append(f"Logical card ID mismatch: requested {req.logical_card_id}, got {defn.logical_card_id}")

        # Check source hash matches
        if defn.source_hash != req.expected_source_hash:
            errors.append(f"Source hash mismatch: expected {req.expected_source_hash}, got {defn.source_hash}")

        result = {
            "valid": len(errors) == 0,
            "errors": errors,
            "logical_card_id": defn.logical_card_id,
            "card_version": defn.card_version,
            "source_hash": defn.source_hash,
            "status": defn.status,
        }
        return (card_definition, result)
