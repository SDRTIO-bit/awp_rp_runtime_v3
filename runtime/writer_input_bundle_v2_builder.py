"""WriterInputBundleV2Builder — builds WriterInputBundle with FinalTurnBrief.

Creates the WriterInputBundle that is Writer's ONLY formal input.
Writer cannot access stores, tool gateway, or raw tool results.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.final_turn_brief import FinalTurnBrief
from ..contracts.suggestion_merge_result import SuggestionMergeResult
from ..contracts.writer_input_bundle import WriterInputBundle


class WriterInputBundleV2Builder:
    """Builds WriterInputBundle with FinalTurnBrief for Writer V2."""

    def build(
        self,
        snapshot: RoundSnapshot,
        final_brief: FinalTurnBrief,
        merge_result: SuggestionMergeResult | None = None,
    ) -> WriterInputBundle:
        """Build a WriterInputBundle.

        Writer can ONLY read from this bundle.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Build accepted guidance from merge result
        accepted_guidance = []
        if merge_result:
            for item in merge_result.adopted:
                if item.suggestion and item.suggestion.summary:
                    accepted_guidance.append(item.suggestion.summary)
            accepted_guidance.extend(merge_result.writer_guidance)

        # Build writer constraints from FinalTurnBrief
        writer_constraints = list(final_brief.writer_constraints)
        writer_constraints.extend([
            "Must not use tools or make tool calls",
            "Must not delegate to sub-agents",
            "Must not write to CardState, TurnRecord, or Memory",
            "Must not output JSON, debug info, or analysis",
            "Must not expose sub-agent suggestions to player",
        ])

        return WriterInputBundle(
            bundle_id=f"wib_{uuid.uuid4().hex[:12]}",
            trace_id=snapshot.trace_id,
            snapshot_id=snapshot.snapshot_id,
            final_turn_brief_id=final_brief.brief_id,
            suggestion_merge_id=merge_result.merge_id if merge_result else "",
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            base_card_state_revision=snapshot.base_card_state_revision,
            recent_accepted_turns_ref=snapshot.snapshot_id,
            active_memory_refs=[m.get("memory_id", "") for m in snapshot.active_memories[:15]],
            rag_recall_refs=[r.get("memory_id", "") for r in snapshot.rag_recall[:10]],
            final_turn_brief=final_brief.to_dict(),
            accepted_guidance=accepted_guidance,
            writer_constraints=writer_constraints,
            style_contract={
                "style": "narrative",
                "language": "zh",
                "perspective": "third_person",
            },
            format_contract={
                "min_length": 1000,
                "max_length": 5000,
            },
            budget_contract={
                "max_tokens": 4000,
            },
            state_proposal_hints=merge_result.state_proposal_hints if merge_result else [],
            memory_proposal_hints=merge_result.memory_proposal_hints if merge_result else [],
            created_at=now,
        )
