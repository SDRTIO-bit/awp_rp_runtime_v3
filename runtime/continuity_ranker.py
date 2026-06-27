"""ContinuityRanker — deterministic ranking of continuity issues.

Priority order:
  Blocking issues with CardState/accepted_turn evidence
  > Blocking issues with ActiveMemory evidence
  > Warnings with high-priority evidence
  > Warnings with lower-priority evidence
  > Informational notes

Must exclude:
  - Issues without evidence (for blocking)
  - Issues that create new facts
  - Issues that advance timeline
  - Issues that modify relationships
  - Issues that override player agency

Default: max 3 blocking + 3 warning per turn.
"""
from __future__ import annotations

from ..contracts.continuity_issue import ContinuityIssue, ContinuityIssueKind, ContinuitySeverity


# Severity weights
_SEVERITY_WEIGHTS: dict[ContinuitySeverity, float] = {
    ContinuitySeverity.BLOCKING: 1.0,
    ContinuitySeverity.WARNING: 0.6,
    ContinuitySeverity.INFO: 0.3,
}

# Kind weights (higher = more important)
_KIND_WEIGHTS: dict[ContinuityIssueKind, float] = {
    ContinuityIssueKind.IDENTITY_CONFLICT: 0.95,
    ContinuityIssueKind.LOCATION_CONFLICT: 0.90,
    ContinuityIssueKind.TIMELINE_CONFLICT: 0.88,
    ContinuityIssueKind.EVENT_STAGE_CONFLICT: 0.85,
    ContinuityIssueKind.STATE_CONFLICT: 0.92,
    ContinuityIssueKind.RELATIONSHIP_CONFLICT: 0.82,
    ContinuityIssueKind.KNOWLEDGE_BOUNDARY_CONFLICT: 0.93,
    ContinuityIssueKind.SECRET_EXPOSURE_RISK: 0.94,
    ContinuityIssueKind.PROMISE_RESOLUTION_RISK: 0.80,
    ContinuityIssueKind.CHARACTER_AVAILABILITY_CONFLICT: 0.86,
    ContinuityIssueKind.CAUSALITY_GAP: 0.75,
    ContinuityIssueKind.MEMORY_CONFLICT: 0.78,
    ContinuityIssueKind.SUGGESTION_CONFLICT: 0.70,
    ContinuityIssueKind.WORLDBOOK_CONFLICT: 0.65,
    ContinuityIssueKind.PLAYER_AGENCY_RISK: 0.96,
}

MAX_BLOCKING = 3
MAX_WARNING = 3


class ContinuityRanker:
    """Deterministic continuity issue ranker."""

    def rank(
        self,
        issues: list[ContinuityIssue],
        max_blocking: int = MAX_BLOCKING,
        max_warning: int = MAX_WARNING,
    ) -> tuple[list[ContinuityIssue], list[ContinuityIssue]]:
        """Rank issues and return (accepted, rejected_by_rank).

        Accepted: top issues by score, respecting severity limits.
        Rejected: remaining issues (outranked, not policy violations).
        """
        if not issues:
            return [], []

        # Score each issue
        scored = []
        for issue in issues:
            score = self._compute_score(issue)
            scored.append((issue, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Split by severity and apply limits
        accepted: list[ContinuityIssue] = []
        rejected: list[ContinuityIssue] = []
        blocking_count = 0
        warning_count = 0

        for issue, score in scored:
            if issue.severity == ContinuitySeverity.BLOCKING:
                if blocking_count < max_blocking:
                    accepted.append(issue)
                    blocking_count += 1
                else:
                    rejected.append(issue)
            elif issue.severity == ContinuitySeverity.WARNING:
                if warning_count < max_warning:
                    accepted.append(issue)
                    warning_count += 1
                else:
                    rejected.append(issue)
            else:
                # Info issues don't count against limits
                accepted.append(issue)

        return accepted, rejected

    def _compute_score(self, issue: ContinuityIssue) -> float:
        """Compute priority score for an issue."""
        severity_weight = _SEVERITY_WEIGHTS.get(issue.severity, 0.3)
        kind_weight = _KIND_WEIGHTS.get(issue.kind, 0.5)

        # Evidence bonus: more evidence refs = higher score
        evidence_bonus = min(len(issue.evidence_refs) * 0.05, 0.2)

        return (
            severity_weight * 0.50
            + kind_weight * 0.30
            + evidence_bonus * 0.20
        )
