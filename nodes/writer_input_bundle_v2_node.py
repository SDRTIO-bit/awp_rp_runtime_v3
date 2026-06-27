"""AWPV2WriterInputBundleV2 — builds WriterInputBundle with FinalTurnBrief.

Creates the WriterInputBundle that is Writer's ONLY formal input.
"""

from __future__ import annotations


class AWPV2WriterInputBundleV2:
    """AWP V2 Writer输入包V2节点"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT",),
                "final_turn_brief": ("FINAL_TURN_BRIEF",),
            },
            "optional": {
                "suggestion_merge_result": ("SUGGESTION_MERGE_RESULT",),
            },
        }

    RETURN_TYPES = ("WRITER_INPUT_BUNDLE",)
    RETURN_NAMES = ("writer_input_bundle",)
    FUNCTION = "execute"
    CATEGORY = "AWP V2 / Writer"

    def execute(self, round_snapshot: dict, final_turn_brief: dict,
                suggestion_merge_result: dict | None = None):
        from ..runtime.writer_input_bundle_v2_builder import WriterInputBundleV2Builder
        from ..contracts.round_snapshot import RoundSnapshot
        from ..contracts.final_turn_brief import FinalTurnBrief
        from ..contracts.suggestion_merge_result import SuggestionMergeResult

        snapshot = RoundSnapshot.from_dict(round_snapshot)
        brief = FinalTurnBrief.from_dict(final_turn_brief)

        merge = None
        if suggestion_merge_result:
            merge = SuggestionMergeResult.from_dict(suggestion_merge_result)

        builder = WriterInputBundleV2Builder()
        bundle = builder.build(snapshot, brief, merge)

        return (bundle.to_dict(),)
