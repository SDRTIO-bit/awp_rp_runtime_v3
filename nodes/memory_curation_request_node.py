"""AWPV2MemoryCurationRequest — builds a MemoryCurationRequest.

ComfyUI node that builds the formal request for the Memory Curator Agent
from accepted turn data.
"""

from __future__ import annotations

from typing import Any


class AWPV2MemoryCurationRequest:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "turn_record": ("TURN_RECORD",),
                "round_snapshot": ("ROUND_SNAPSHOT",),
                "trigger_diagnostics": ("MEMORY_CURATION_TRIGGER_DIAGNOSTICS",),
            },
            "optional": {
                "trace_id": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("MEMORY_CURATION_REQUEST",)
    RETURN_NAMES = ("curation_request",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2/Memory"
    OUTPUT_SCHEMA_ID = "awp.rp.memory-curation-request.v1"

    def execute(
        self,
        turn_record: dict[str, Any],
        round_snapshot: dict[str, Any],
        trigger_diagnostics: dict[str, Any],
        trace_id: str = "",
    ) -> tuple[dict[str, Any]]:
        from ..contracts.turn_record import TurnRecord
        from ..contracts.round_snapshot import RoundSnapshot
        from ..contracts.memory_curation_trigger_diagnostics import (
            MemoryCurationTriggerDiagnostics,
        )
        from ..runtime.memory_curation_runtime import MemoryCurationRuntime

        tr = TurnRecord.from_dict(turn_record)
        snap = RoundSnapshot.from_dict(round_snapshot)
        diag = MemoryCurationTriggerDiagnostics.from_dict(trigger_diagnostics)

        # Use the runtime's _build_request method
        runtime = MemoryCurationRuntime()
        request = runtime._build_request(tr, snap, diag)

        return (request.to_dict(),)
