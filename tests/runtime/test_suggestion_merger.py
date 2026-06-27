"""Tests for SuggestionMerger — updated for P2 contracts."""

import pytest
from awp_rp_runtime_v2.runtime.suggestion_merger import SuggestionMerger
from awp_rp_runtime_v2.contracts.agent_suggestion import AgentSuggestion, SuggestionKind
from awp_rp_runtime_v2.contracts.agent_execution_result import AgentExecutionResult
from awp_rp_runtime_v2.contracts.delegation_plan import DelegationPlan
from awp_rp_runtime_v2.contracts.turn_brief import TurnBrief
from awp_rp_runtime_v2.contracts.round_snapshot import RoundSnapshot
from awp_rp_runtime_v2.contracts.card_state import CardState
from awp_rp_runtime_v2.contracts.suggestion_merge_result import MergeDecision


def _ctx():
    plan = DelegationPlan(plan_id="p1")
    brief = TurnBrief(brief_id="b1")
    snap = RoundSnapshot(snapshot_id="s1", trace_id="t1",
                         card_id="c1", session_id="s1",
                         card_state=CardState(card_id="c1", session_id="s1"))
    return plan, brief, snap


class TestSuggestionMerger:

    def test_empty_suggestions(self):
        merger = SuggestionMerger()
        plan, brief, snap = _ctx()
        result = merger.merge(plan, brief, snap, [])
        assert result.adopted == []

    def test_single_suggestion_adopted(self):
        merger = SuggestionMerger()
        plan, brief, snap = _ctx()
        sug = AgentSuggestion(
            suggestion_id="s1", kind=SuggestionKind.NARRATIVE_OPPORTUNITY,
            summary="Add detail", confidence=0.8,
            evidence=["e1"], source_refs=["r1"],
        )
        exec_r = AgentExecutionResult(task_id="t1", role="worldbook-researcher",
                                      success=True, suggestions=[sug])
        result = merger.merge(plan, brief, snap, [exec_r])
        assert len(result.adopted) == 1

    def test_conflict_detection(self):
        merger = SuggestionMerger()
        plan, brief, snap = _ctx()
        s1 = AgentSuggestion(
            suggestion_id="s1", kind=SuggestionKind.STATE_PATCH_PROPOSAL,
            summary="Set HP 100", confidence=0.8, evidence=["e1"], source_refs=["r1"],
            proposed_state_changes=[{"path": "variables.hp", "value": 100}],
        )
        s2 = AgentSuggestion(
            suggestion_id="s2", kind=SuggestionKind.STATE_PATCH_PROPOSAL,
            summary="Set HP 50", confidence=0.7, evidence=["e2"], source_refs=["r2"],
            proposed_state_changes=[{"path": "variables.hp", "value": 50}],
        )
        exec_rs = [
            AgentExecutionResult(task_id="t1", role="state-updater", success=True, suggestions=[s1]),
            AgentExecutionResult(task_id="t2", role="state-updater", success=True, suggestions=[s2]),
        ]
        result = merger.merge(plan, brief, snap, exec_rs)
        assert len(result.conflicts) >= 1

    def test_categorization(self):
        merger = SuggestionMerger()
        plan, brief, snap = _ctx()
        sug = AgentSuggestion(
            suggestion_id="s1", kind=SuggestionKind.NARRATIVE_OPPORTUNITY,
            summary="detail", confidence=0.8, evidence=["e1"], source_refs=["r1"],
        )
        exec_r = AgentExecutionResult(task_id="t1", role="worldbook-researcher",
                                      success=True, suggestions=[sug])
        result = merger.merge(plan, brief, snap, [exec_r])
        assert result.adopted_count + result.ignored_count + result.conflict_count == len(result.items)
