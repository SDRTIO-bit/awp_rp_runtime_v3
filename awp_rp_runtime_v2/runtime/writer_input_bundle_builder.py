"""WriterInputBundleBuilder — builds the WriterInputBundle.

The bundle is the only formal input for future Writer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.turn_brief import TurnBrief
from ..contracts.suggestion_merge_result import SuggestionMergeResult
from ..contracts.writer_input_bundle import WriterInputBundle


class WriterInputBundleBuilder:

    def build(
        self,
        snapshot: RoundSnapshot,
        brief: TurnBrief,
        merge_result: SuggestionMergeResult,
    ) -> WriterInputBundle:
        now = datetime.now(timezone.utc).isoformat()

        return WriterInputBundle(
            bundle_id=f"bundle_{uuid.uuid4().hex[:12]}",
            trace_id=snapshot.trace_id,
            snapshot_id=snapshot.snapshot_id,
            brief_id=brief.brief_id,
            merge_id=merge_result.merge_id,
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            base_card_state_revision=snapshot.base_card_state_revision,
            round_snapshot_ref=snapshot.snapshot_id,
            turn_brief_ref=brief.brief_id,
            suggestion_merge_ref=merge_result.merge_id,
            writer_constraints=brief.writer_constraints + brief.must_not_do,
            accepted_guidance=merge_result.writer_guidance,
            state_proposal_hints=merge_result.state_proposal_hints,
            memory_proposal_hints=merge_result.memory_proposal_hints,
            created_at=now,
        )
