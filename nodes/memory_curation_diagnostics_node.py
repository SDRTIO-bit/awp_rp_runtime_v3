"""AWPV2MemoryCurationDiagnostics — diagnostics for Memory Curator.

ComfyUI node that outputs diagnostics from the memory curation process.
"""

from __future__ import annotations

from typing import Any


class AWPV2MemoryCurationDiagnostics:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "curation_result": ("MEMORY_CURATION_RESULT",),
                "trigger_diagnostics": ("MEMORY_CURATION_TRIGGER_DIAGNOSTICS",),
            },
        }

    RETURN_TYPES = ("DICT",)
    RETURN_NAMES = ("diagnostics",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2/Memory"

    def execute(
        self,
        curation_result: dict[str, Any],
        trigger_diagnostics: dict[str, Any],
    ) -> tuple[dict[str, Any]]:
        diagnostics = {
            "trigger": {
                "should_trigger": trigger_diagnostics.get("should_trigger", False),
                "risk_level": trigger_diagnostics.get("risk_level", "none"),
                "skip_reason": trigger_diagnostics.get("skip_reason", ""),
                "domains": trigger_diagnostics.get("curation_domains", []),
                "reasons": trigger_diagnostics.get("trigger_reasons", []),
            },
            "result": {
                "degraded": curation_result.get("degraded", False),
                "degraded_reasons": curation_result.get("degraded_reasons", []),
                "total_generated": curation_result.get("total_candidates_generated", 0),
                "total_accepted": curation_result.get("total_candidates_accepted", 0),
                "total_rejected": curation_result.get("total_candidates_rejected", 0),
                "active_before": curation_result.get("active_memory_count_before", 0),
                "active_after": curation_result.get("active_memory_count_after", 0),
                "rejection_reasons": curation_result.get("rejection_reasons", []),
            },
        }
        return (diagnostics,)
