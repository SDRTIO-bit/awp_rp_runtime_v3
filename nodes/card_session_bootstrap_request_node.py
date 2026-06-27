"""AWPV2CardSessionBootstrapRequest — creates a bootstrap request contract.

Can optionally accept a CARD_DEFINITION to auto-extract logical_card_id,
card_version, and source_hash.
"""

from __future__ import annotations
from typing import Any


class AWPV2CardSessionBootstrapRequest:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "request_id": ("STRING", {"default": ""}),
                "session_id": ("STRING", {"default": ""}),
                "greeting_id": ("STRING", {"default": "g0"}),
            },
            "optional": {
                "card_definition": ("CARD_DEFINITION",),
                "logical_card_id": ("STRING", {"default": ""}),
                "card_version": ("INT", {"default": 0, "min": 0}),
                "expected_source_hash": ("STRING", {"default": ""}),
                "workflow_run_id": ("STRING", {"default": ""}),
                "trace_id": ("STRING", {"default": ""}),
                "initial_state_seed": ("STRING", {"default": "{}"}),
            },
        }

    RETURN_TYPES = ("BOOTSTRAP_REQUEST",)
    RETURN_NAMES = ("bootstrap_request",)
    FUNCTION = "execute"
    CATEGORY = "AWP/CardSession"

    def execute(
        self,
        request_id: str,
        session_id: str,
        greeting_id: str,
        card_definition: dict | None = None,
        logical_card_id: str = "",
        card_version: int = 0,
        expected_source_hash: str = "",
        workflow_run_id: str = "",
        trace_id: str = "",
        initial_state_seed: str = "{}",
    ) -> tuple[dict]:
        import json
        from datetime import datetime, timezone
        from ..contracts.card_session_bootstrap_request import CardSessionBootstrapRequest

        # Extract from card_definition if provided and not overridden
        if card_definition:
            if not logical_card_id:
                logical_card_id = card_definition.get("logical_card_id", "")
            if card_version == 0:
                card_version = card_definition.get("card_version", 0)
            if not expected_source_hash:
                expected_source_hash = card_definition.get("source_hash", "")

        seed = {}
        if initial_state_seed:
            try:
                seed = json.loads(initial_state_seed) if isinstance(initial_state_seed, str) else initial_state_seed
            except (json.JSONDecodeError, TypeError):
                seed = {}

        req = CardSessionBootstrapRequest(
            request_id=request_id,
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            session_id=session_id,
            logical_card_id=logical_card_id,
            card_version=card_version,
            greeting_id=greeting_id,
            expected_source_hash=expected_source_hash,
            initial_state_seed=seed,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return (req.to_dict(),)
