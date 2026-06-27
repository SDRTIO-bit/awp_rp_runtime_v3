"""FinalTurnBriefRuntime — produces FinalTurnBrief from DirectorPlan + EnrichmentBundle.

Director uses this after tool execution to produce the final brief for Writer.
Director does NOT produce player-visible text.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..contracts.director_plan import DirectorPlan
from ..contracts.enrichment_bundle import EnrichmentBundle
from ..contracts.final_turn_brief import FinalTurnBrief
from ..contracts.round_snapshot import RoundSnapshot


class FinalTurnBriefRuntime:
    """Produces FinalTurnBrief from DirectorPlan + EnrichmentBundle."""

    def produce(
        self,
        director_plan: DirectorPlan,
        enrichment: EnrichmentBundle,
        snapshot: RoundSnapshot,
    ) -> FinalTurnBrief:
        """Produce a FinalTurnBrief.

        Director adopts, partially adopts, or rejects tool findings.
        Adopted and rejected findings are recorded with reasons.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Build accepted evidence from accepted enrichment items
        accepted_evidence = []
        accepted_findings = []
        for item in enrichment.accepted_items:
            accepted_evidence.append({
                "tool_id": item.tool_id,
                "summary": item.summary,
                "source_refs": item.source_refs,
                "evidence": item.evidence,
            })
            if item.summary:
                accepted_findings.append(f"[{item.tool_id}] {item.summary}")

        # Build rejected findings
        rejected_findings = []
        for item in enrichment.rejected_items:
            rejected_findings.append({
                "tool_id": item.tool_id,
                "reason": item.rejection_reason,
            })

        return FinalTurnBrief(
            brief_id=f"ftb_{uuid.uuid4().hex[:12]}",
            trace_id=director_plan.trace_id,
            snapshot_id=director_plan.snapshot_id,
            director_plan_id=director_plan.plan_id,
            tool_result_bundle_id=enrichment.tool_result_bundle_id,
            card_id=director_plan.card_id,
            session_id=director_plan.session_id,
            base_card_state_revision=director_plan.base_card_state_revision,
            turn_goal=director_plan.turn_goal,
            scene_focus=director_plan.scene_focus,
            active_character_refs=director_plan.active_character_refs,
            must_preserve_facts=director_plan.must_preserve_facts,
            must_not_do=director_plan.must_not_do,
            accepted_evidence=accepted_evidence,
            accepted_tool_findings=accepted_findings,
            rejected_tool_findings=rejected_findings,
            narrative_opportunities=director_plan.narrative_opportunities,
            writer_constraints=director_plan.writer_constraints,
            state_sensitivity_flags=director_plan.risk_flags,
            memory_sensitivity_flags=[],
            created_at=now,
        )
