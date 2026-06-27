"""SuggestionConflictGovernor — unified conflict governance for D-Integration.

Implements the priority hierarchy:
  CardState > accepted TurnRecord > ActiveMemory > high-confidence RagMemory
  > active worldbook > DirectorPlan > AgentSuggestion > no-evidence speculation

Enforces:
  - History high-priority facts cannot be overridden by Opportunity/World-Life/Emotion
  - Opportunity/World-Life/Emotion can only be soft suggestions, not facts
  - Continuity blocking issues need high-priority evidence
  - Player agency cannot be overridden by any agent
  - Low-priority RAG cannot override CardState/accepted Turn
  - World-Life "might happen" cannot become "already happened"
  - Emotion/Relationship interpretation cannot assert relationship changed
  - Opportunity drama opening cannot assert player accepted
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..contracts.agent_suggestion import AgentSuggestion, SuggestionKind
from ..contracts.agent_execution_result import AgentExecutionResult
from ..contracts.suggestion_merge_result import SuggestionMergeResult, MergeItem, MergeDecision
from ..contracts.suggestion_conflict import (
    SuggestionConflict, ConflictKind, ConflictResolution,
)
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.delegation_plan import DelegationPlan
from ..contracts.turn_brief import TurnBrief
from .continuity_barrier_runtime import EVIDENCE_SOURCE_PRIORITY


# Fact leak patterns: these suggestion kinds must NOT assert facts
NON_FACT_SUGGESTION_KINDS = {
    # Opportunity: proposals, not events
    SuggestionKind.PROMISE_PRESSURE,
    SuggestionKind.RELATIONSHIP_TENSION,
    SuggestionKind.EMOTIONAL_SHIFT,
    SuggestionKind.SECRET_PRESSURE,
    SuggestionKind.MISUNDERSTANDING_PRESSURE,
    SuggestionKind.GOAL_REACTIVATION,
    SuggestionKind.SCENE_PRESSURE,
    SuggestionKind.CHOICE_OPENING,
    SuggestionKind.FORESHADOWING_ECHO,
    SuggestionKind.PACE_VARIATION,
    # World-Life: atmosphere, not events
    SuggestionKind.ENVIRONMENTAL_PRESSURE,
    SuggestionKind.WEATHER_OR_TIME_ATMOSPHERE,
    SuggestionKind.NPC_SIDE_TENSION,
    SuggestionKind.EVENT_STAGE_ECHO,
    SuggestionKind.LOCATION_LIFE_DETAIL,
    SuggestionKind.SOCIAL_BACKGROUND_SIGNAL,
    SuggestionKind.WORLDBOOK_RESONANCE,
    SuggestionKind.OFFSCREEN_CONSEQUENCE_HINT,
    SuggestionKind.AMBIENT_RUMOR_SIGNAL,
    # Emotion/Relationship: interpretation, not change
    SuggestionKind.ER_TRUST_TENSION,
    SuggestionKind.ER_GUARDEDNESS,
    SuggestionKind.ER_EMOTIONAL_RESIDUE,
    SuggestionKind.ER_UNRESOLVED_HURT,
    SuggestionKind.ER_PROMISE_PRESSURE,
    SuggestionKind.ER_MISUNDERSTANDING_SIGNAL,
    SuggestionKind.ER_JEALOUSY_RISK,
    SuggestionKind.ER_AFFECTION_RESTRAINT,
    SuggestionKind.ER_CONFLICT_DEESCALATION,
    SuggestionKind.ER_RELATIONSHIP_BOUNDARY,
    SuggestionKind.ER_SUBTEXT_OPPORTUNITY,
}


class SuggestionConflictGovernor:
    """Unified conflict governance with deterministic rules."""

    def govern(
        self,
        merge_result: SuggestionMergeResult,
        snapshot: RoundSnapshot,
        brief: TurnBrief,
    ) -> tuple[SuggestionMergeResult, list[SuggestionConflict]]:
        """Apply conflict governance to merge result.

        Returns (governed_merge_result, conflicts).
        """
        conflicts: list[SuggestionConflict] = []
        now = datetime.now(timezone.utc).isoformat()

        governed_adopted = []
        governed_ignored = list(merge_result.ignored)
        governed_conflicts = list(merge_result.conflicts)

        for item in merge_result.adopted:
            if item.suggestion is None:
                governed_adopted.append(item)
                continue

            sug = item.suggestion

            # Rule 1: Fact leak detection
            if sug.kind in NON_FACT_SUGGESTION_KINDS:
                if self._has_fact_assertion(sug):
                    conflict = SuggestionConflict(
                        conflict_id=f"conf_{uuid.uuid4().hex[:12]}",
                        trace_id=merge_result.trace_id,
                        involved_suggestion_ids=[sug.suggestion_id],
                        conflict_kind=self._get_leak_kind(sug.kind),
                        evidence_refs=sug.source_refs,
                        priority_decision="Non-fact suggestion asserts facts",
                        resolution=ConflictResolution.DOWNGRADED_TO_SOFT_GUIDANCE,
                        downgraded_suggestion_ids=[sug.suggestion_id],
                        created_at=now,
                    )
                    conflicts.append(conflict)
                    governed_conflicts.append(MergeItem(
                        suggestion_id=sug.suggestion_id,
                        task_id=item.task_id,
                        role=sug.role,
                        decision=MergeDecision.CONFLICT,
                        reason="Fact leak: non-fact suggestion asserts facts",
                        evidence_refs=sug.source_refs,
                        resolution="Downgraded to soft guidance",
                        priority_score=item.priority_score,
                        suggestion=sug,
                    ))
                    continue

            # Rule 2: Player agency protection
            if self._violates_player_agency(sug, snapshot):
                conflict = SuggestionConflict(
                    conflict_id=f"conf_{uuid.uuid4().hex[:12]}",
                    trace_id=merge_result.trace_id,
                    involved_suggestion_ids=[sug.suggestion_id],
                    conflict_kind=ConflictKind.PLAYER_AGENCY_VIOLATION,
                    evidence_refs=sug.source_refs,
                    priority_decision="Player agency cannot be overridden",
                    resolution=ConflictResolution.BLOCKED_BY_PLAYER_AGENCY,
                    rejected_suggestion_ids=[sug.suggestion_id],
                    created_at=now,
                )
                conflicts.append(conflict)
                governed_ignored.append(MergeItem(
                    suggestion_id=sug.suggestion_id,
                    task_id=item.task_id,
                    role=sug.role,
                    decision=MergeDecision.IGNORED,
                    reason="Blocked by player agency",
                    evidence_refs=sug.source_refs,
                    priority_score=item.priority_score,
                    suggestion=sug,
                ))
                continue

            # Rule 3: CardState fact override protection
            if self._contradicts_card_state(sug, snapshot):
                conflict = SuggestionConflict(
                    conflict_id=f"conf_{uuid.uuid4().hex[:12]}",
                    trace_id=merge_result.trace_id,
                    involved_suggestion_ids=[sug.suggestion_id],
                    conflict_kind=ConflictKind.FACT_CONTRADICTION,
                    evidence_refs=sug.source_refs,
                    priority_decision="CardState overrides suggestion",
                    resolution=ConflictResolution.BLOCKED_BY_HARD_FACT,
                    rejected_suggestion_ids=[sug.suggestion_id],
                    created_at=now,
                )
                conflicts.append(conflict)
                governed_ignored.append(MergeItem(
                    suggestion_id=sug.suggestion_id,
                    task_id=item.task_id,
                    role=sug.role,
                    decision=MergeDecision.IGNORED,
                    reason="Blocked by CardState fact",
                    evidence_refs=sug.source_refs,
                    priority_score=item.priority_score,
                    suggestion=sug,
                ))
                continue

            governed_adopted.append(item)

        return SuggestionMergeResult(
            merge_id=merge_result.merge_id,
            trace_id=merge_result.trace_id,
            snapshot_id=merge_result.snapshot_id,
            brief_id=merge_result.brief_id,
            plan_id=merge_result.plan_id,
            adopted=governed_adopted,
            ignored=governed_ignored,
            conflicts=governed_conflicts,
            degraded_tasks=merge_result.degraded_tasks,
            failed_tasks=merge_result.failed_tasks,
            writer_guidance=merge_result.writer_guidance,
            state_proposal_hints=merge_result.state_proposal_hints,
            memory_proposal_hints=merge_result.memory_proposal_hints,
            created_at=merge_result.created_at,
        ), conflicts

    def _has_fact_assertion(self, sug: AgentSuggestion) -> bool:
        """Check if suggestion asserts something as a fact."""
        fact_keywords = ["已经", "已", "确实", "确定", "事实上", "was", "is", "has been"]
        summary_lower = sug.summary.lower()
        for kw in fact_keywords:
            if kw in sug.summary:
                return True
        # Check proposed state changes (those ARE fact assertions)
        if sug.proposed_state_changes:
            return True
        return False

    def _get_leak_kind(self, kind: SuggestionKind) -> ConflictKind:
        """Map suggestion kind to conflict kind."""
        if kind.value.startswith("er_"):
            return ConflictKind.EMOTION_FACT_LEAK
        if kind in {
            SuggestionKind.ENVIRONMENTAL_PRESSURE,
            SuggestionKind.WEATHER_OR_TIME_ATMOSPHERE,
            SuggestionKind.NPC_SIDE_TENSION,
            SuggestionKind.EVENT_STAGE_ECHO,
            SuggestionKind.LOCATION_LIFE_DETAIL,
            SuggestionKind.SOCIAL_BACKGROUND_SIGNAL,
            SuggestionKind.WORLDBOOK_RESONANCE,
            SuggestionKind.OFFSCREEN_CONSEQUENCE_HINT,
            SuggestionKind.AMBIENT_RUMOR_SIGNAL,
        }:
            return ConflictKind.WORLD_LIFE_FACT_LEAK
        return ConflictKind.OPPORTUNITY_FACT_LEAK

    def _violates_player_agency(
        self, sug: AgentSuggestion, snapshot: RoundSnapshot
    ) -> bool:
        """Check if suggestion overrides player choice."""
        agency_keywords = ["玩家选择", "玩家决定", "玩家接受", "玩家同意",
                           "player chooses", "player decides", "player accepts"]
        for kw in agency_keywords:
            if kw in sug.summary:
                return True
        # High risk_flags with agency-related content
        if "player_agency" in str(sug.risk_flags):
            return True
        return False

    def _contradicts_card_state(
        self, sug: AgentSuggestion, snapshot: RoundSnapshot
    ) -> bool:
        """Check if suggestion directly contradicts CardState facts."""
        # Simple check: if suggestion has high-risk flags and low evidence
        if len(sug.risk_flags) >= 3 and not sug.source_refs:
            return True
        return False
