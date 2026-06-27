"""P2 Tests: SuggestionMerger."""

import pytest
from awp_rp_runtime_v2.runtime.suggestion_merger import SuggestionMerger
from awp_rp_runtime_v2.contracts.agent_suggestion import AgentSuggestion, SuggestionKind
from awp_rp_runtime_v2.contracts.agent_execution_result import AgentExecutionResult
from awp_rp_runtime_v2.contracts.delegation_plan import DelegationPlan, DelegationTask
from awp_rp_runtime_v2.contracts.turn_brief import TurnBrief
from awp_rp_runtime_v2.contracts.round_snapshot import RoundSnapshot
from awp_rp_runtime_v2.contracts.card_state import CardState
from awp_rp_runtime_v2.contracts.suggestion_merge_result import MergeDecision


def _make_snapshot() -> RoundSnapshot:
    return RoundSnapshot(
        snapshot_id="snap1", trace_id="trace1",
        card_id="c1", session_id="s1",
        card_state=CardState(card_id="c1", session_id="s1"),
    )

def _make_brief(**kwargs) -> TurnBrief:
    return TurnBrief(brief_id="b1", **kwargs)

def _make_plan(tasks=None) -> DelegationPlan:
    return DelegationPlan(plan_id="p1", tasks=tasks or [])


class TestSuggestionMerger:

    def test_empty_results(self):
        merger = SuggestionMerger()
        result = merger.merge(
            _make_plan(), _make_brief(), _make_snapshot(), []
        )
        assert result.adopted == []
        assert result.ignored == []
        assert result.conflicts == []

    def test_single_suggestion_adopted(self):
        merger = SuggestionMerger()
        sug = AgentSuggestion(
            suggestion_id="s1", kind=SuggestionKind.NARRATIVE_OPPORTUNITY,
            summary="Add detail", confidence=0.8,
            evidence=["Turn 1"], source_refs=["turn_record:t1"],
        )
        exec_result = AgentExecutionResult(
            task_id="t1", role="worldbook-researcher", success=True,
            suggestions=[sug],
        )
        result = merger.merge(
            _make_plan(), _make_brief(), _make_snapshot(), [exec_result]
        )
        assert len(result.adopted) == 1
        assert result.adopted[0].suggestion_id == "s1"

    def test_must_not_do_violation_ignored(self):
        """Test 17: mustNotDo violation → ignored."""
        merger = SuggestionMerger()
        brief = _make_brief(must_not_do=["Contradict established facts"])
        sug = AgentSuggestion(
            suggestion_id="s1", kind=SuggestionKind.NARRATIVE_OPPORTUNITY,
            summary="Contradict facts", confidence=0.9,
            recommendations=["Contradict the established timeline"],
            evidence=["e1"], source_refs=["r1"],
        )
        exec_result = AgentExecutionResult(
            task_id="t1", role="worldbook-researcher", success=True,
            suggestions=[sug],
        )
        result = merger.merge(
            _make_plan(), brief, _make_snapshot(), [exec_result]
        )
        assert len(result.ignored) >= 1
        assert any(i.reason == "Violates mustNotDo" for i in result.ignored)

    def test_high_risk_without_evidence_ignored(self):
        """Test 15: no evidence + high risk → ignored."""
        merger = SuggestionMerger()
        sug = AgentSuggestion(
            suggestion_id="s1", kind=SuggestionKind.STATE_PATCH_PROPOSAL,
            summary="Risky change", confidence=0.3,
            risk_flags=["high", "unverified"],
            # No evidence
        )
        exec_result = AgentExecutionResult(
            task_id="t1", role="state-updater", success=True,
            suggestions=[sug],
        )
        result = merger.merge(
            _make_plan(), _make_brief(), _make_snapshot(), [exec_result]
        )
        assert len(result.ignored) >= 1
        assert any("without evidence" in i.reason for i in result.ignored)

    def test_conflicting_state_changes(self):
        """Test 18: two mutually exclusive state changes → conflict."""
        merger = SuggestionMerger()
        s1 = AgentSuggestion(
            suggestion_id="s1", kind=SuggestionKind.STATE_PATCH_PROPOSAL,
            summary="Set HP to 100", confidence=0.8,
            evidence=["e1"], source_refs=["r1"],
            proposed_state_changes=[{"path": "variables.hp", "value": 100}],
        )
        s2 = AgentSuggestion(
            suggestion_id="s2", kind=SuggestionKind.STATE_PATCH_PROPOSAL,
            summary="Set HP to 50", confidence=0.7,
            evidence=["e2"], source_refs=["r2"],
            proposed_state_changes=[{"path": "variables.hp", "value": 50}],
        )
        exec_results = [
            AgentExecutionResult(task_id="t1", role="state-updater", success=True, suggestions=[s1]),
            AgentExecutionResult(task_id="t2", role="state-updater", success=True, suggestions=[s2]),
        ]
        result = merger.merge(
            _make_plan(), _make_brief(), _make_snapshot(), exec_results
        )
        assert len(result.conflicts) >= 1

    def test_failed_tasks_recorded(self):
        merger = SuggestionMerger()
        exec_result = AgentExecutionResult(
            task_id="t1", role="continuity-checker", success=False,
            error_message="timeout",
        )
        result = merger.merge(
            _make_plan(), _make_brief(), _make_snapshot(), [exec_result]
        )
        assert "t1" in result.failed_tasks

    def test_writer_guidance_generated(self):
        merger = SuggestionMerger()
        sug = AgentSuggestion(
            suggestion_id="s1", kind=SuggestionKind.NARRATIVE_OPPORTUNITY,
            summary="Add detail", confidence=0.8,
            recommendations=["Add environmental description"],
            evidence=["e1"], source_refs=["r1"],
        )
        exec_result = AgentExecutionResult(
            task_id="t1", role="worldbook-researcher", success=True,
            suggestions=[sug],
        )
        result = merger.merge(
            _make_plan(), _make_brief(), _make_snapshot(), [exec_result]
        )
        assert len(result.writer_guidance) >= 1
