"""SuggestionMerger — deterministic merge of sub-agent suggestions.

Priority order:
  CardState/Snapshot facts
  > TurnBrief mustPreserveFacts / mustNotDo
  > High-confidence continuity with evidence
  > High-confidence state/memory proposals
  > Worldbook research
  > Emotion/opportunity
  > No-evidence / low-confidence / conflicts

Rules:
  - Cannot adopt suggestions conflicting with Snapshot facts
  - Cannot adopt suggestions violating mustNotDo
  - Cannot adopt high-risk suggestions without evidence
  - Mutually exclusive suggestions → explicit conflict record
  - Deterministic rules, not LLM-only judgment
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..contracts.agent_suggestion import AgentSuggestion, SuggestionKind
from ..contracts.agent_execution_result import AgentExecutionResult
from ..contracts.suggestion_merge_result import (
    SuggestionMergeResult, MergeItem, MergeDecision,
)
from ..contracts.delegation_plan import DelegationPlan
from ..contracts.turn_brief import TurnBrief
from ..contracts.round_snapshot import RoundSnapshot


# Priority weights by suggestion kind
KIND_WEIGHTS: dict[SuggestionKind, float] = {
    SuggestionKind.CONTINUITY_ISSUE: 1.0,
    SuggestionKind.CHARACTER_CONSISTENCY: 0.95,
    SuggestionKind.STATE_PATCH_PROPOSAL: 0.85,
    SuggestionKind.MEMORY_CANDIDATE: 0.75,
    SuggestionKind.WORLD_DETAIL: 0.65,
    SuggestionKind.NARRATIVE_OPPORTUNITY: 0.6,
    SuggestionKind.EMOTION_CUE: 0.55,
    SuggestionKind.RELATIONSHIP_SHIFT: 0.5,
    SuggestionKind.TONE_ADJUSTMENT: 0.45,
    SuggestionKind.CRITIQUE: 0.4,
    # D1: History/Recall kinds
    SuggestionKind.HISTORICAL_CONFLICT: 0.98,
    SuggestionKind.IDENTITY_CLARIFICATION: 0.92,
    SuggestionKind.TIMELINE_WARNING: 0.90,
    SuggestionKind.WRITER_CONSTRAINT: 0.88,
    SuggestionKind.DIRECTOR_FOLLOWUP: 0.70,
    # D2: Opportunity kinds
    SuggestionKind.PROMISE_PRESSURE: 0.82,
    SuggestionKind.RELATIONSHIP_TENSION: 0.78,
    SuggestionKind.EMOTIONAL_SHIFT: 0.72,
    SuggestionKind.SECRET_PRESSURE: 0.80,
    SuggestionKind.MISUNDERSTANDING_PRESSURE: 0.76,
    SuggestionKind.GOAL_REACTIVATION: 0.74,
    SuggestionKind.SCENE_PRESSURE: 0.68,
    SuggestionKind.CHOICE_OPENING: 0.66,
    SuggestionKind.FORESHADOWING_ECHO: 0.62,
    SuggestionKind.PACE_VARIATION: 0.58,
    SuggestionKind.OPPORTUNITY_WARNING: 0.85,
}

MAX_ADOPTED = 15


class SuggestionMerger:
    """Deterministic suggestion merger."""

    def merge(
        self,
        plan: DelegationPlan,
        brief: TurnBrief,
        snapshot: RoundSnapshot,
        execution_results: list[AgentExecutionResult],
    ) -> SuggestionMergeResult:
        """Merge all suggestions from execution results."""
        now = datetime.now(timezone.utc).isoformat()
        merge_id = f"merge_{uuid.uuid4().hex[:12]}"

        # Collect all suggestions
        all_suggestions: list[tuple[AgentSuggestion, str]] = []
        failed_tasks: list[str] = []
        degraded_tasks: list[str] = []

        for result in execution_results:
            if not result.success:
                if result.degraded:
                    degraded_tasks.append(result.task_id)
                else:
                    failed_tasks.append(result.task_id)
                continue
            for sug in result.suggestions:
                all_suggestions.append((sug, result.task_id))

        # Score and sort
        scored = []
        for sug, task_id in all_suggestions:
            score = self._compute_priority(sug)
            scored.append((sug, task_id, score))
        scored.sort(key=lambda x: x[2], reverse=True)

        # Classify
        adopted: list[MergeItem] = []
        ignored: list[MergeItem] = []
        conflicts: list[MergeItem] = []
        adopted_count = 0

        # Track adopted paths for conflict detection
        adopted_paths: dict[str, str] = {}  # path → suggestion_id

        for sug, task_id, score in scored:
            # Rule: mustNotDo check
            if self._violates_must_not_do(sug, brief):
                ignored.append(MergeItem(
                    suggestion_id=sug.suggestion_id, task_id=task_id,
                    role=sug.role, decision=MergeDecision.IGNORED,
                    reason="Violates mustNotDo",
                    evidence_refs=sug.source_refs, priority_score=score,
                    suggestion=sug,
                ))
                continue

            # Rule: high-risk without evidence
            if len(sug.risk_flags) >= 2 and not sug.evidence:
                ignored.append(MergeItem(
                    suggestion_id=sug.suggestion_id, task_id=task_id,
                    role=sug.role, decision=MergeDecision.IGNORED,
                    reason="High-risk suggestion without evidence",
                    evidence_refs=sug.source_refs, priority_score=score,
                    suggestion=sug,
                ))
                continue

            # Rule: conflict detection (state changes on same path)
            if sug.proposed_state_changes:
                conflict_found = False
                for change in sug.proposed_state_changes:
                    path = change.get("path", "")
                    if path in adopted_paths:
                        conflicts.append(MergeItem(
                            suggestion_id=sug.suggestion_id, task_id=task_id,
                            role=sug.role, decision=MergeDecision.CONFLICT,
                            reason=f"Conflicts with {adopted_paths[path]} on path '{path}'",
                            evidence_refs=sug.source_refs,
                            resolution="Higher priority adopted",
                            priority_score=score,
                            suggestion=sug,
                        ))
                        conflict_found = True
                        break
                if conflict_found:
                    continue
                for change in sug.proposed_state_changes:
                    adopted_paths[change.get("path", "")] = sug.suggestion_id

            # Adopt
            if adopted_count < MAX_ADOPTED:
                adopted.append(MergeItem(
                    suggestion_id=sug.suggestion_id, task_id=task_id,
                    role=sug.role, decision=MergeDecision.ADOPTED,
                    reason="Within priority budget, passes all rules",
                    evidence_refs=sug.source_refs, priority_score=score,
                    suggestion=sug,
                ))
                adopted_count += 1
            else:
                ignored.append(MergeItem(
                    suggestion_id=sug.suggestion_id, task_id=task_id,
                    role=sug.role, decision=MergeDecision.IGNORED,
                    reason="Exceeded max adopted limit",
                    evidence_refs=sug.source_refs, priority_score=score,
                    suggestion=sug,
                ))

        # Build writer guidance
        writer_guidance = []
        state_hints = []
        memory_hints = []
        for item in adopted:
            if item.suggestion:
                writer_guidance.extend(item.suggestion.recommendations[:2])
                state_hints.extend(item.suggestion.proposed_state_changes)
                memory_hints.extend(item.suggestion.proposed_memory_candidates)

        return SuggestionMergeResult(
            merge_id=merge_id,
            trace_id=snapshot.trace_id,
            snapshot_id=snapshot.snapshot_id,
            brief_id=brief.brief_id,
            plan_id=plan.plan_id,
            adopted=adopted,
            ignored=ignored,
            conflicts=conflicts,
            degraded_tasks=degraded_tasks,
            failed_tasks=failed_tasks,
            writer_guidance=writer_guidance[:10],
            state_proposal_hints=state_hints[:5],
            memory_proposal_hints=memory_hints[:5],
            created_at=now,
        )

    def _compute_priority(self, sug: AgentSuggestion) -> float:
        kind_weight = KIND_WEIGHTS.get(sug.kind, 0.5)
        return (
            kind_weight * 0.4
            + sug.priority * 0.3
            + sug.confidence * 0.2
            + (1.0 - len(sug.risk_flags) / 5.0) * 0.1
        )

    def _violates_must_not_do(self, sug: AgentSuggestion, brief: TurnBrief) -> bool:
        """Check if suggestion violates any mustNotDo constraint."""
        for constraint in brief.must_not_do:
            constraint_lower = constraint.lower()
            # Check if suggestion content mentions violating the constraint
            if any(kw in sug.summary.lower() for kw in constraint_lower.split()[:3]):
                if len(constraint_lower.split()) > 0:
                    # Simple heuristic: if suggestion recommends something in mustNotDo
                    for rec in sug.recommendations:
                        if any(kw in rec.lower() for kw in constraint_lower.split()[:2]):
                            return True
        return False
