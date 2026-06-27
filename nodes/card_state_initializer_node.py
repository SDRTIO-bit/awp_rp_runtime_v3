"""AWPV2CardStateInitializer — initializes CardState from safe initialStateSeed."""

from __future__ import annotations
from typing import Any


class AWPV2CardStateInitializer:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "bootstrap_request": ("BOOTSTRAP_REQUEST",),
                "card_definition": ("CARD_DEFINITION",),
            },
        }

    RETURN_TYPES = ("CARD_STATE",)
    RETURN_NAMES = ("card_state",)
    FUNCTION = "execute"
    CATEGORY = "AWP/CardSession"

    def execute(self, bootstrap_request: dict, card_definition: dict) -> tuple[dict]:
        from datetime import datetime, timezone
        from ..contracts.card_state import CardState, VariableEntry
        from ..contracts.card_definition import CardDefinition
        from ..contracts.card_session_bootstrap_request import CardSessionBootstrapRequest

        req = CardSessionBootstrapRequest.from_dict(bootstrap_request)
        defn = CardDefinition.from_dict(card_definition)
        now = datetime.now(timezone.utc).isoformat()

        # Build variables from safe initialStateSeed ONLY
        # NEVER from description/personality/scenario
        # NEVER from scripts/EJS/JS/Regex
        variables = {}
        if req.initial_state_seed:
            for k, v in req.initial_state_seed.items():
                if isinstance(v, bool):
                    var_type = "bool"
                elif isinstance(v, int):
                    var_type = "int"
                elif isinstance(v, float):
                    var_type = "float"
                else:
                    var_type = "string"
                    v = str(v)
                variables[k] = VariableEntry(name=k, value=v, var_type=var_type)

        state = CardState(
            card_id=defn.logical_card_id,
            session_id=req.session_id,
            revision=1,
            variables=variables,
            created_at=now,
            updated_at=now,
        )
        return (state.to_dict(),)
