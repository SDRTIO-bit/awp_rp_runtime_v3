"""AWPV2CardSessionBootstrapRequest — creates a bootstrap request contract."""

from __future__ import annotations
from typing import Any


class AWPV2CardSessionBootstrapRequest:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "request_id": ("STRING", {"default": ""}),
                "session_id": ("STRING", {"default": ""}),
                "logical_card_id": ("STRING", {"default": ""}),
                "card_version": ("INT", {"default": 0, "min": 1}),
                "greeting_id": ("STRING", {"default": "g0"}),
                "expected_source_hash": ("STRING", {"default": ""}),
            },
            "optional": {
                "workflow_run_id": ("STRING", {"default": ""}),
                "trace_id": ("STRING", {"default": ""}),
                "initial_state_seed": ("JSON", {"default": "{}"}),
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
        logical_card_id: str,
        card_version: int,
        greeting_id: str,
        expected_source_hash: str,
        workflow_run_id: str = "",
        trace_id: str = "",
        initial_state_seed: str = "{}",
    ) -> tuple[dict]:
        import json
        from datetime import datetime, timezone
        from ..contracts.card_session_bootstrap_request import CardSessionBootstrapRequest

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
