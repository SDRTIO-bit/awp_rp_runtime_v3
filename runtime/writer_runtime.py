"""WriterRuntime — runs the Writer agent.

Writer responsibilities:
- Read RoundSnapshot + TurnBrief + adopted suggestions
- Generate player-visible RP text
- Must NOT use tools, delegate, write state, or write memory
- Must NOT output JSON, debug info, or analysis
"""

from __future__ import annotations

from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.turn_brief import TurnBrief
from ..contracts.suggestion_merge_result import SuggestionMergeResult, MergeDecision
from ..contracts.writer_contract import WriterContract


class WriterRuntime:
    """Runtime for the Writer agent.

    Writer produces player-visible RP text.
    Writer does NOT use tools, delegate, write state, or write memory.
    """

    def __init__(self, llm_provider: Any):
        self.llm_provider = llm_provider

    def run(
        self,
        snapshot: RoundSnapshot,
        turn_brief: TurnBrief,
        merge_result: SuggestionMergeResult,
    ) -> str:
        """Run Writer to produce candidate text.

        Returns candidate RP text for quality gate review.
        """
        # Build writer contract
        contract = self._build_contract(snapshot, turn_brief, merge_result)

        # Generate candidate text
        candidate_text = self.llm_provider.generate_candidate_text(
            snapshot_summary=contract.round_snapshot_summary,
            turn_brief=contract.turn_brief,
            adopted_suggestions=contract.adopted_suggestions,
        )

        return candidate_text

    def _build_contract(
        self,
        snapshot: RoundSnapshot,
        turn_brief: TurnBrief,
        merge_result: SuggestionMergeResult,
    ) -> WriterContract:
        """Build the WriterContract from inputs."""
        # Build snapshot summary
        summary_parts = [
            f"Card: {snapshot.card_id}",
            f"Player input: {snapshot.player_input}",
            f"Scene: {snapshot.card_state.scene_state.location}",
        ]
        if snapshot.card_state.scene_state.time_of_day:
            summary_parts.append(f"Time: {snapshot.card_state.scene_state.time_of_day}")

        # Add recent turn summaries
        if snapshot.recent_turn_records:
            summary_parts.append(f"Recent {len(snapshot.recent_turn_records)} turns available")

        snapshot_summary = "\n".join(summary_parts)

        # Get adopted suggestions
        adopted = [
            {
                "title": item.suggestion.summary if item.suggestion else "",
                "content": "; ".join(item.suggestion.recommendations) if item.suggestion else "",
                "type": item.suggestion.kind.value if item.suggestion else "",
            }
            for item in merge_result.get_adopted()
        ]

        return WriterContract(
            turn_id=snapshot.trace_id,
            round_snapshot_summary=snapshot_summary,
            turn_brief=turn_brief.to_dict(),
            adopted_suggestions=adopted,
            focus_characters=turn_brief.active_characters,
        )
