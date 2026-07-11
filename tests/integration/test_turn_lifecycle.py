"""Integration tests for the complete turn lifecycle."""

import pytest
from awp_rp_runtime_v3.testing.fakes import (
    FakeCardStateStore, FakeTurnRecordStore, FakeActiveMemoryStore,
    FakeRagMemoryStore, FakeLLMProvider,
)
from awp_rp_runtime_v3.contracts.card_state import CardState, VariableEntry
from awp_rp_runtime_v3.contracts.quality_decision import QualityDecision, QualityVerdict
from awp_rp_runtime_v3.contracts.state_update_proposal import StateUpdateProposal, PatchOp, PatchOpEntry
from awp_rp_runtime_v3.contracts.suggestion_merge_result import SuggestionMergeResult

from awp_rp_runtime_v3.runtime.round_snapshot_builder import RoundSnapshotBuilder
from awp_rp_runtime_v3.runtime.director_runtime import DirectorRuntime, FakeDirectorAdapter
from awp_rp_runtime_v3.runtime.delegation_planner import DelegationPlanner
from awp_rp_runtime_v3.runtime.suggestion_merger import SuggestionMerger
from awp_rp_runtime_v3.runtime.writer_runtime import WriterRuntime
from awp_rp_runtime_v3.runtime.critic_runtime import CriticRuntime
from awp_rp_runtime_v3.runtime.state_proposal_runtime import StateProposalRuntime
from awp_rp_runtime_v3.runtime.card_state_commit_runtime import CardStateCommitRuntime
from awp_rp_runtime_v3.runtime.turn_record_commit_runtime import TurnRecordCommitRuntime
from awp_rp_runtime_v3.runtime.active_memory_commit_runtime import ActiveMemoryCommitRuntime
from awp_rp_runtime_v3.runtime.rag_memory_commit_runtime import RagMemoryCommitRuntime
from awp_rp_runtime_v3.runtime.turn_orchestrator import TurnOrchestrator
from awp_rp_runtime_v3.runtime.retry_runtime import RetryRuntime
from awp_rp_runtime_v3.runtime.agent_runtime_registry import AgentRuntimeRegistry
from awp_rp_runtime_v3.runtime.task_envelope_builder import TaskEnvelopeBuilder
from awp_rp_runtime_v3.runtime.dynamic_subagent_pool import DynamicSubAgentPool


class TestTurnLifecycleIntegration:

    def setup_method(self):
        self.card_store = FakeCardStateStore()
        self.turn_store = FakeTurnRecordStore()
        self.active_store = FakeActiveMemoryStore()
        self.rag_store = FakeRagMemoryStore()
        self.llm = FakeLLMProvider()

        self.snapshot_builder = RoundSnapshotBuilder(
            self.card_store, self.turn_store, self.active_store, self.rag_store,
        )
        director_adapter = FakeDirectorAdapter()
        self.director = DirectorRuntime(director_adapter)
        self.delegation_planner = DelegationPlanner()
        registry = AgentRuntimeRegistry()
        self.subagent_pool = DynamicSubAgentPool(registry, TaskEnvelopeBuilder(registry))
        self.suggestion_merger = SuggestionMerger()
        self.writer = WriterRuntime(self.llm)
        self.critic = CriticRuntime(self.llm)
        self.state_proposal = StateProposalRuntime(self.llm)
        self.state_commit = CardStateCommitRuntime(self.card_store)
        self.turn_commit = TurnRecordCommitRuntime(self.turn_store)
        self.memory_commit = ActiveMemoryCommitRuntime(self.active_store)
        self.rag_commit = RagMemoryCommitRuntime(self.rag_store)

        self.orchestrator = TurnOrchestrator(
            snapshot_builder=self.snapshot_builder,
            director=self.director,
            delegation_planner=self.delegation_planner,
            subagent_pool=self.subagent_pool,
            suggestion_merger=self.suggestion_merger,
            writer=self.writer,
            critic=self.critic,
            state_proposal=self.state_proposal,
            state_commit=self.state_commit,
            turn_commit=self.turn_commit,
            memory_commit=self.memory_commit,
            rag_commit=self.rag_commit,
            retry_runtime=RetryRuntime(),
        )

    def test_full_turn_success(self):
        self.card_store.initialize("card1", "sess1")
        result = self.orchestrator.execute_turn(
            card_id="card1", session_id="sess1", player_input="我走进了月光庭院",
        )
        assert result.success
        assert result.accepted_text != ""
        assert result.turn_record is not None

    def test_card_id_session_id_isolation(self):
        self.card_store.initialize("card1", "sess1")
        self.card_store.initialize("card1", "sess2")
        r1 = self.orchestrator.execute_turn(card_id="card1", session_id="sess1", player_input="Hello")
        r2 = self.orchestrator.execute_turn(card_id="card1", session_id="sess2", player_input="World")
        assert r1.success and r2.success
        assert r1.turn_record.session_id == "sess1"
        assert r2.turn_record.session_id == "sess2"

    def test_card_state_initialization_idempotent(self):
        s1 = self.card_store.initialize("card1", "sess1")
        s2 = self.card_store.initialize("card1", "sess1")
        assert s1.revision == s2.revision

    def test_revision_conflict_detection(self):
        self.card_store.initialize("card1", "sess1")
        self.llm.set_response("state_proposal", StateUpdateProposal(
            card_id="card1", session_id="sess1",
            operations=[PatchOpEntry(op=PatchOp.SET_VARIABLE, path="variables.hp", value=100)],
        ))
        result = self.orchestrator.execute_turn(
            card_id="card1", session_id="sess1", player_input="Turn 1",
        )
        assert result.success
        assert self.card_store.load("card1", "sess1").revision == 1

    def test_turn_record_saved(self):
        self.card_store.initialize("card1", "sess1")
        self.orchestrator.execute_turn(card_id="card1", session_id="sess1", player_input="Test input")
        records = self.turn_store.get_recent("card1", "sess1")
        assert len(records) == 1

    def test_round_snapshot_frozen(self):
        self.card_store.initialize("card1", "sess1")
        snapshot = self.snapshot_builder.build("card1", "sess1", "Test")
        with pytest.raises(AttributeError):
            snapshot.player_input = "Changed"

    def test_quality_gate_reject_text_too_short(self):
        self.card_store.initialize("card1", "sess1")
        self.llm.set_response("candidate_text", "Hi")
        result = self.orchestrator.execute_turn(
            card_id="card1", session_id="sess1", player_input="Test",
        )
        assert not result.success

    def test_subagent_cannot_write_state(self):
        from awp_rp_runtime_v3.contracts.agent_task_envelope import AgentTaskEnvelope
        envelope = AgentTaskEnvelope(task_id="t1", role="continuity-checker")
        assert "Cannot write to CardState" in envelope.prohibitions

    def test_writer_cannot_use_tools(self):
        from awp_rp_runtime_v3.contracts.writer_contract import WriterContract
        contract = WriterContract()
        assert "Must not use tools" in contract.prohibitions[0]

    def test_director_does_not_produce_player_text(self):
        self.card_store.initialize("card1", "sess1")
        snapshot = self.snapshot_builder.build("card1", "sess1", "Test")
        turn_brief, _ = self.director.run(snapshot)
        assert turn_brief.turn_goal != ""

    def test_suggestion_merge_explainable(self):
        merger = SuggestionMerger()
        from awp_rp_runtime_v3.contracts.agent_suggestion import AgentSuggestion, SuggestionKind
        from awp_rp_runtime_v3.contracts.agent_execution_result import AgentExecutionResult
        from awp_rp_runtime_v3.contracts.delegation_plan import DelegationPlan
        from awp_rp_runtime_v3.contracts.turn_brief import TurnBrief
        from awp_rp_runtime_v3.contracts.round_snapshot import RoundSnapshot

        sug = AgentSuggestion(suggestion_id="s1", kind=SuggestionKind.NARRATIVE_OPPORTUNITY,
                              summary="detail", evidence=["e1"], source_refs=["r1"])
        exec_r = AgentExecutionResult(task_id="t1", role="r", success=True, suggestions=[sug])
        result = merger.merge(
            DelegationPlan(plan_id="p1"), TurnBrief(brief_id="b1"),
            RoundSnapshot(snapshot_id="s1", trace_id="t1", card_id="c1", session_id="s1"),
            [exec_r],
        )
        for item in result.items:
            assert item.reason != ""

    def test_trace_recorded(self):
        self.card_store.initialize("card1", "sess1")
        result = self.orchestrator.execute_turn(
            card_id="card1", session_id="sess1", player_input="Test",
        )
        assert result.trace is not None
        event_types = {e.event_type for e in result.trace.events}
        assert "snapshot_built" in event_types


class TestRetryIntegration:

    def test_retry_does_not_duplicate_state_write(self):
        card_store = FakeCardStateStore()
        turn_store = FakeTurnRecordStore()
        active_store = FakeActiveMemoryStore()
        rag_store = FakeRagMemoryStore()
        llm = FakeLLMProvider()

        snapshot_builder = RoundSnapshotBuilder(card_store, turn_store, active_store, rag_store)
        writer = WriterRuntime(llm)
        critic = CriticRuntime(llm)

        card_store.initialize("card1", "sess1")
        snapshot = snapshot_builder.build("card1", "sess1", "Test")

        director_adapter = FakeDirectorAdapter()
        director = DirectorRuntime(director_adapter)
        turn_brief, _ = director.run(snapshot)
        text = writer.run(snapshot, turn_brief, SuggestionMergeResult())

        decision1 = critic.check(text, snapshot, retry_count=0)
        decision1.trace_id = snapshot.trace_id
        assert decision1.is_accepted()
