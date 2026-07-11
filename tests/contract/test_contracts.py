"""Tests for all contract serialization roundtrips."""

import pytest
from awp_rp_runtime_v3.contracts import (
    TurnBrief, DelegationPlan, DelegationTask,
    AgentTaskEnvelope, AgentSuggestion, SuggestionKind,
    SuggestionMergeResult, MergeItem, MergeDecision,
    QualityDecision, QualityVerdict,
    StateUpdateProposal, PatchOp, PatchOpEntry,
    MemoryCommitPlan, ActiveMemoryEntry,
    ExecutionTrace, TraceEvent,
)


class TestContractRoundtrips:

    def test_turn_brief(self):
        brief = TurnBrief(brief_id="b1", turn_goal="goal",
                          must_preserve_facts=["fact1"])
        restored = TurnBrief.from_dict(brief.to_dict())
        assert restored.brief_id == "b1"

    def test_delegation_plan(self):
        plan = DelegationPlan(plan_id="p1", tasks=[
            DelegationTask(task_id="t1", role="continuity-checker", purpose="check")
        ])
        restored = DelegationPlan.from_dict(plan.to_dict())
        assert restored.tasks[0].role == "continuity-checker"

    def test_agent_task_envelope(self):
        envelope = AgentTaskEnvelope(task_id="t1", role="continuity-checker")
        restored = AgentTaskEnvelope.from_dict(envelope.to_dict())
        assert "Cannot delegate to sub-agents" in restored.prohibitions

    def test_agent_suggestion(self):
        sug = AgentSuggestion(suggestion_id="s1", kind=SuggestionKind.CONTINUITY_ISSUE)
        restored = AgentSuggestion.from_dict(sug.to_dict())
        assert restored.kind == SuggestionKind.CONTINUITY_ISSUE

    def test_suggestion_merge_result(self):
        result = SuggestionMergeResult(merge_id="m1", adopted=[
            MergeItem(suggestion_id="s1", decision=MergeDecision.ADOPTED)
        ])
        restored = SuggestionMergeResult.from_dict(result.to_dict())
        assert len(restored.adopted) == 1

    def test_quality_decision(self):
        decision = QualityDecision(verdict=QualityVerdict.ACCEPTED, trace_id="tr1")
        restored = QualityDecision.from_dict(decision.to_dict())
        assert restored.is_accepted()

    def test_state_update_proposal(self):
        proposal = StateUpdateProposal(
            operations=[PatchOpEntry(op=PatchOp.SET_VARIABLE, path="variables.hp", value=60)]
        )
        restored = StateUpdateProposal.from_dict(proposal.to_dict())
        assert len(restored.operations) == 1

    def test_memory_commit_plan(self):
        plan = MemoryCommitPlan(new_active_entries=[
            ActiveMemoryEntry(memory_id="m1", kind="promise", summary="test")
        ])
        restored = MemoryCommitPlan.from_dict(plan.to_dict())
        assert len(restored.new_active_entries) == 1

    def test_execution_trace(self):
        trace = ExecutionTrace(trace_id="tr1", events=[TraceEvent(event_type="test")])
        restored = ExecutionTrace.from_dict(trace.to_dict())
        assert len(restored.events) == 1
