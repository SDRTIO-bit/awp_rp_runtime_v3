"""AWPV2WriterInputBundle — builds the WriterInputBundle.

Input: round_snapshot, turn_brief, suggestion_merge_result
Output: writer_input_bundle
"""

from __future__ import annotations

from typing import Any


class AWPV2WriterInputBundle:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT",),
                "turn_brief": ("TURN_BRIEF",),
                "suggestion_merge_result": ("SUGGESTION_MERGE_RESULT",),
            },
        }

    RETURN_TYPES = ("WRITER_INPUT_BUNDLE",)
    RETURN_NAMES = ("writer_input_bundle",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(
        self,
        round_snapshot: dict[str, Any],
        turn_brief: dict[str, Any],
        suggestion_merge_result: dict[str, Any],
    ) -> tuple[dict[str, Any]]:
        from ..contracts.round_snapshot import RoundSnapshot
        from ..contracts.turn_brief import TurnBrief
        from ..contracts.suggestion_merge_result import SuggestionMergeResult
        from ..runtime.writer_input_bundle_builder import WriterInputBundleBuilder

        snapshot = RoundSnapshot.from_dict(round_snapshot)
        brief = TurnBrief.from_dict(turn_brief)
        merge = SuggestionMergeResult.from_dict(suggestion_merge_result)

        builder = WriterInputBundleBuilder()
        bundle = builder.build(snapshot, brief, merge)
        return (bundle.to_dict(),)
