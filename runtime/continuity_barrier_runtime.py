"""ContinuityBarrierRuntime — barrier between Wave A and Wave B.

Ensures Continuity Agent only sees normalized, structured suggestion
summaries from Wave A — not raw model reasoning or tool output.

Also enforces that Continuity blocking issues require high-priority
evidence to become hard constraints.
"""

from __future__ import annotations

from ..contracts.agent_suggestion import AgentSuggestion, SuggestionKind
from ..contracts.agent_execution_result import AgentExecutionResult
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.delegation_plan import DelegationPlan, DelegationTask


# Evidence source priority (higher = more authoritative)
EVIDENCE_SOURCE_PRIORITY: dict[str, int] = {
    "cardstate": 100,
    "accepted_turn": 90,
    "active_memory": 80,
    "rag_memory": 70,
    "worldbook": 60,
    "tool_result": 50,
}

# Minimum evidence priority for a blocking issue to become hard constraint
MIN_BLOCKING_EVIDENCE_PRIORITY = 80  # Must have CardState or accepted_turn evidence


class ContinuityBarrierResult:
    """Result of passing through the continuity barrier."""

    def __init__(self):
        self.suggestion_summary: list[dict] = []
        self.evidence_refs: list[str] = []
        self.blocking_candidates: list[dict] = []
        self.warning_candidates: list[dict] = []


class ContinuityBarrierRuntime:
    """Normalizes Wave A suggestions for Continuity Agent consumption.

    Strips raw model reasoning, tool output, and system prompts.
    Only passes structured summaries, evidence refs, candidate types,
    risk levels, entity refs, and state/timeline constraints.
    """

    def normalize(
        self,
        wave_a_results: list[AgentExecutionResult],
        snapshot: RoundSnapshot,
    ) -> ContinuityBarrierResult:
        """Normalize Wave A results into Continuity-consumable format."""
        result = ContinuityBarrierResult()

        for exec_result in wave_a_results:
            if not exec_result.success:
                continue

            for sug in exec_result.suggestions:
                normalized = self._normalize_suggestion(sug)
                result.suggestion_summary.append(normalized)
                result.evidence_refs.extend(sug.source_refs)

                # Classify blocking vs warning
                if self._is_potential_blocking(sug):
                    result.blocking_candidates.append(normalized)
                else:
                    result.warning_candidates.append(normalized)

        # Deduplicate evidence refs
        result.evidence_refs = list(dict.fromkeys(result.evidence_refs))
        return result

    def _normalize_suggestion(self, sug: AgentSuggestion) -> dict:
        """Strip internal details, keep only what Continuity needs."""
        return {
            "suggestion_id": sug.suggestion_id,
            "role": sug.role,
            "kind": sug.kind.value,
            "priority": sug.priority,
            "confidence": sug.confidence,
            "summary": sug.summary,
            "recommendations": sug.recommendations[:3],  # Limit to 3
            "evidence_refs": sug.source_refs,
            "risk_flags": sug.risk_flags,
            "proposed_state_changes": sug.proposed_state_changes[:3],
        }

    def _is_potential_blocking(self, sug: AgentSuggestion) -> bool:
        """Check if suggestion might need blocking enforcement."""
        blocking_kinds = {
            SuggestionKind.CONTINUITY_FACT_CONSTRAINT,
            SuggestionKind.CONTINUITY_BLOCKING_RISK,
            SuggestionKind.HISTORICAL_CONFLICT,
            SuggestionKind.TIMELINE_WARNING,
        }
        return sug.kind in blocking_kinds or len(sug.risk_flags) >= 2

    def validate_blocking_evidence(
        self, suggestion: AgentSuggestion
    ) -> tuple[bool, str]:
        """Check if a blocking issue has sufficient evidence priority.

        Returns (can_block, reason).
        """
        if not suggestion.source_refs:
            return False, "No evidence refs — cannot be blocking"

        max_priority = 0
        for ref in suggestion.source_refs:
            source_type = ref.split(":")[0] if ":" in ref else "tool_result"
            priority = EVIDENCE_SOURCE_PRIORITY.get(source_type, 0)
            max_priority = max(max_priority, priority)

        if max_priority < MIN_BLOCKING_EVIDENCE_PRIORITY:
            return False, (
                f"Max evidence priority {max_priority} < {MIN_BLOCKING_EVIDENCE_PRIORITY} "
                f"— downgraded to warning"
            )
        return True, "Sufficient evidence priority"
