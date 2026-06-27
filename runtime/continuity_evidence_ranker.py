"""ContinuityEvidenceRanker — deterministic evidence priority ranking.

Priority order (fixed):
  CardState (100) > accepted_turn (90) > ActiveMemory (80)
  > high-confidence RagMemory (70) > worldbook (60) > AgentSuggestion (40)
  > no-evidence speculation (0)

Within same source type: confidence ↓ → recency ↓ → relevance_score ↓

Low-priority evidence conflicting with high-priority facts must be
marked stale / conflicted.
"""
from __future__ import annotations

from ..contracts.continuity_evidence import (
    ContinuityEvidence, EvidenceSourceType, ConflictStatus, EVIDENCE_PRIORITY,
)


class ContinuityEvidenceRanker:
    """Deterministic evidence priority ranker for continuity analysis."""

    def rank(
        self,
        evidence: list[ContinuityEvidence],
    ) -> list[ContinuityEvidence]:
        """Rank evidence by priority, then confidence, recency, relevance.

        Returns sorted list (highest priority first).
        """
        if not evidence:
            return []

        # Sort by: source priority desc → confidence desc → recency desc → relevance desc
        ranked = sorted(
            evidence,
            key=lambda e: (
                e.priority,
                e.confidence,
                e.recency,
                e.relevance_score,
            ),
            reverse=True,
        )

        return ranked

    def detect_conflicts(
        self,
        evidence: list[ContinuityEvidence],
    ) -> list[tuple[ContinuityEvidence, ContinuityEvidence, str]]:
        """Detect conflicts between evidence sources.

        Returns list of (higher_priority, lower_priority, conflict_description).
        """
        conflicts: list[tuple[ContinuityEvidence, ContinuityEvidence, str]] = []

        # Group evidence by entity/location overlap
        for i, ev_high in enumerate(evidence):
            for ev_low in evidence[i + 1:]:
                # Only flag if different source types
                if ev_high.source_type == ev_low.source_type:
                    continue

                # Check if they cover the same entities or locations
                shared_entities = set(ev_high.entity_refs) & set(ev_low.entity_refs)
                shared_locations = set(ev_high.location_refs) & set(ev_low.location_refs)

                if shared_entities or shared_locations:
                    # Check if excerpts suggest conflicting information
                    if self._may_conflict(ev_high.excerpt, ev_low.excerpt):
                        # Mark lower priority evidence as conflicted
                        ev_low.conflict_status = ConflictStatus.CONFLICTED
                        conflicts.append((
                            ev_high,
                            ev_low,
                            f"{ev_high.source_type.value} 与 {ev_low.source_type.value} "
                            f"对同一事实存在潜在冲突",
                        ))

        return conflicts

    def mark_stale(
        self,
        evidence: list[ContinuityEvidence],
    ) -> list[ContinuityEvidence]:
        """Mark low-priority evidence that conflicts with high-priority facts.

        CardState > accepted_turn > ActiveMemory > RagMemory > worldbook > suggestion
        """
        ranked = self.rank(evidence)
        marked = list(ranked)

        for i, ev_high in enumerate(ranked):
            if ev_high.priority < 60:  # Below ActiveMemory priority
                continue
            for ev_low in ranked[i + 1:]:
                if ev_low.priority >= ev_high.priority:
                    continue
                # If lower priority evidence conflicts with higher
                if ev_low.conflict_status == ConflictStatus.CONFLICTED:
                    ev_low.conflict_status = ConflictStatus.STALE

        return marked

    def _may_conflict(self, excerpt_a: str, excerpt_b: str) -> bool:
        """Simple heuristic to detect potential conflicts between excerpts.

        Checks for negation patterns or contradictory statements.
        """
        # Simple keyword-based conflict detection
        negation_patterns = ["不", "没", "未", "非", "无", "否认"]
        positive_patterns = ["已", "有", "是", "在", "确", "肯定"]

        a_has_neg = any(p in excerpt_a for p in negation_patterns)
        b_has_neg = any(p in excerpt_b for p in negation_patterns)

        # If one has negation and the other doesn't, potential conflict
        if a_has_neg != b_has_neg:
            return True

        return False
