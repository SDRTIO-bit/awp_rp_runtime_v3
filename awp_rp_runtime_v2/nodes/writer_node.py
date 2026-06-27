"""WriterNode — runs the Writer agent.

Input: round_snapshot, turn_brief, suggestion_merge_result
Output: candidate_text
"""

from __future__ import annotations

from typing import Any


class WriterNode:
    """Run Writer agent to produce candidate RP text."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "round_snapshot": ("ROUND_SNAPSHOT",),
                "turn_brief": ("TURN_BRIEF",),
                "suggestion_merge_result": ("SUGGESTION_MERGE_RESULT",),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("candidate_text",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(
        self,
        round_snapshot: dict[str, Any],
        turn_brief: dict[str, Any],
        suggestion_merge_result: dict[str, Any],
    ) -> tuple[str]:
        """Run Writer to produce candidate text."""
        from ..contracts.round_snapshot import RoundSnapshot
        from ..contracts.turn_brief import TurnBrief
        from ..contracts.suggestion_merge_result import SuggestionMergeResult
        from ..testing.fakes.fake_llm import FakeLLMProvider
        from ..runtime.writer_runtime import WriterRuntime

        snapshot = RoundSnapshot.from_dict(round_snapshot)
        brief = TurnBrief.from_dict(turn_brief)
        merge = SuggestionMergeResult.from_dict(suggestion_merge_result)

        llm = FakeLLMProvider()
        writer = WriterRuntime(llm)
        text = writer.run(snapshot, brief, merge)

        return (text,)
