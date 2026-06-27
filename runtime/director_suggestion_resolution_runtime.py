"""DirectorSuggestionResolutionRuntime — adopt/partial/reject resolution.

Director's structured decision on which suggestions to adopt, partially
adopt, or reject. Does NOT produce player-visible text. Does NOT write
CardState, TurnRecord, or Memory. Only produces structured resolution.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..contracts.agent_suggestion import AgentSuggestion
from ..contracts.suggestion_merge_result import SuggestionMergeResult, MergeItem, MergeDecision
from ..contracts.suggestion_conflict import SuggestionConflict, ConflictResolution
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.director_plan import DirectorPlan
from ..contracts.execution_trace import ExecutionTrace, TraceEvent


class DirectorResolution:
    """Structured output of Director's suggestion resolution."""

    def __init__(self):
        self.accepted_suggestion_ids: list[str] = []
        self.partially_accepted_suggestion_ids: list[str] = []
        self.rejected_suggestion_ids: list[str] = []
        self.rejection_reasons: dict[str, str] = {}
        self.hard_constraints: list[str] = []
        self.soft_guidance: list[str] = []
        self.writer_priorities: list[str] = []
        self.player_agency_guards: list[str] = []
        self.evidence_refs: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted_suggestion_ids": self.accepted_suggestion_ids,
            "partially_accepted_suggestion_ids": self.partially_accepted_suggestion_ids,
            "rejected_suggestion_ids": self.rejected_suggestion_ids,
            "rejection_reasons": self.rejection_reasons,
            "hard_constraints": self.hard_constraints,
            "soft_guidance": self.soft_guidance,
            "writer_priorities": self.writer_priorities,
            "player_agency_guards": self.player_agency_guards,
            "evidence_refs": self.evidence_refs,
        }


class DirectorSuggestionResolutionRuntime:
    """Deterministic Director suggestion resolution.

    Takes governed merge result and conflicts, produces structured
    adopt/partial/reject decisions. Does NOT produce player text.
    """

    def resolve(
        self,
        merge_result: SuggestionMergeResult,
        conflicts: list[SuggestionConflict],
        director_plan: DirectorPlan,
        snapshot: RoundSnapshot,
        trace: ExecutionTrace | None = None,
    ) -> DirectorResolution:
        """Resolve suggestions into adopt/partial/reject."""
        resolution = DirectorResolution()
        now = datetime.now(timezone.utc).isoformat()

        # Build conflict lookup: suggestion_id -> conflict
        conflict_map: dict[str, SuggestionConflict] = {}
        for conflict in conflicts:
            for sid in conflict.involved_suggestion_ids:
                conflict_map[sid] = conflict

        # Process adopted items
        for item in merge_result.adopted:
            if item.suggestion_id in conflict_map:
                conflict = conflict_map[item.suggestion_id]
                if conflict.resolution in {
                    ConflictResolution.BLOCKED_BY_PLAYER_AGENCY,
                    ConflictResolution.BLOCKED_BY_HARD_FACT,
                }:
                    resolution.rejected_suggestion_ids.append(item.suggestion_id)
                    resolution.rejection_reasons[item.suggestion_id] = (
                        f"Conflict: {conflict.resolution.value}"
                    )
                    continue
                elif conflict.resolution == ConflictResolution.DOWNGRADED_TO_SOFT_GUIDANCE:
                    resolution.partially_accepted_suggestion_ids.append(item.suggestion_id)
                    if item.suggestion:
                        resolution.soft_guidance.extend(
                            item.suggestion.recommendations[:1]
                        )
                    continue

            resolution.accepted_suggestion_ids.append(item.suggestion_id)
            if item.suggestion:
                resolution.writer_priorities.extend(
                    item.suggestion.recommendations[:2]
                )
                resolution.evidence_refs.extend(item.suggestion.source_refs[:3])

        # Process ignored items
        for item in merge_result.ignored:
            resolution.rejected_suggestion_ids.append(item.suggestion_id)
            resolution.rejection_reasons[item.suggestion_id] = item.reason

        # Process conflict items
        for item in merge_result.conflicts:
            if item.suggestion_id not in resolution.rejected_suggestion_ids:
                resolution.rejected_suggestion_ids.append(item.suggestion_id)
                resolution.rejection_reasons[item.suggestion_id] = item.reason

        # Extract hard constraints from director plan
        resolution.hard_constraints = list(director_plan.must_preserve_facts)
        resolution.player_agency_guards = [
            f for f in director_plan.must_not_do if "player" in f.lower() or "玩家" in f
        ]

        # Deduplicate evidence refs
        resolution.evidence_refs = list(dict.fromkeys(resolution.evidence_refs))

        # Trace
        if trace:
            trace.add_event(TraceEvent(
                event_id=f"evt_{uuid.uuid4().hex[:8]}",
                event_type="director_resolution",
                actor="director_resolution",
                details={
                    "accepted": len(resolution.accepted_suggestion_ids),
                    "partially_accepted": len(resolution.partially_accepted_suggestion_ids),
                    "rejected": len(resolution.rejected_suggestion_ids),
                    "conflicts": len(conflicts),
                },
            ))

        return resolution
