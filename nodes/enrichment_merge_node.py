"""AWPV2EnrichmentMerge — ComfyUI node for merging tool results.

Takes ToolResultBundle and produces EnrichmentBundle.
"""

from __future__ import annotations


class AWPV2EnrichmentMerge:
    """AWP V2 丰富合并节点"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "tool_result_bundle": ("TOOL_RESULT_BUNDLE",),
            },
        }

    RETURN_TYPES = ("ENRICHMENT_BUNDLE",)
    RETURN_NAMES = ("enrichment_bundle",)
    FUNCTION = "execute"
    CATEGORY = "AWP V2 / Tool Gateway"

    def execute(self, tool_result_bundle: dict):
        from ..runtime.enrichment_merger import EnrichmentMerger
        from ..contracts.tool_result_bundle import ToolResultBundle

        bundle = ToolResultBundle.from_dict(tool_result_bundle)
        merger = EnrichmentMerger()
        enrichment = merger.merge(bundle)

        return (enrichment.to_dict(),)
