"""RecallEvidenceRanker — deterministic ranking of recall evidence.

Priority order (hard, deterministic):
  CardState > accepted_turn > ActiveMemory > RagMemory > worldbook > tool_result

Within same source type: higher confidence + higher recency first.
Conflicted/stale evidence is flagged, not removed.
"""

from __future__ import annotations

from ..contracts.recall_evidence import RecallEvidence, SOURCE_PRIORITY


class RecallEvidenceRanker:
    """Deterministic evidence ranking."""

    def rank(self, evidence: list[RecallEvidence]) -> list[RecallEvidence]:
        """Rank evidence by source priority, confidence, and recency.

        Returns sorted list (highest priority first).
        Conflicted/stale items are kept but flagged.
        """
        return sorted(
            evidence,
            key=lambda e: (
                e.source_priority,      # Source type priority (highest first)
                e.confidence,           # Higher confidence first
                e.recency,              # More recent first
                e.relevance_score,      # Higher relevance first
            ),
            reverse=True,
        )

    def filter_confirmed(
        self, evidence: list[RecallEvidence], min_confidence: float = 0.5
    ) -> list[RecallEvidence]:
        """Filter to only evidence suitable for confirmed facts.

        Requirements:
        - source_ref must be non-empty
        - confidence >= min_confidence
        - conflict_status must be empty (not conflicted/stale)
        """
        return [
            e for e in evidence
            if e.source_ref
            and e.confidence >= min_confidence
            and not e.conflict_status
        ]

    def filter_conflicted(
        self, evidence: list[RecallEvidence]
    ) -> list[RecallEvidence]:
        """Filter to only conflicted/stale evidence."""
        return [e for e in evidence if e.conflict_status in ("conflicted", "stale")]
