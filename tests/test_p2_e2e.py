"""P2 End-to-End Integration Test.

Full chain:
  Init CardState → RoundSnapshot → FakeDirector → TurnBrief + DelegationPlan
  → Pool runs continuity-checker + memory-curator → AgentSuggestion[]
  → SuggestionMerge → WriterInputBundle
  → Verify NO CardState/TurnRecord/Memory writes
  → Verify all traces queryable
"""

import pytest
from awp_rp_runtime_v3.contracts.card_state import CardState
from awp_rp_runtime_v3.contracts.round_snapshot import RoundSnapshot
from awp_rp_runtime_v3.contracts.agent_suggestion import AgentSuggestion, SuggestionKind
from awp_rp_runtime_v3.contracts.agent_execution_result import AgentExecutionResult
from awp_rp_runtime_v3.contracts.delegation_plan import DelegationPlan, DelegationTask

from awp_rp_runtime_v3.runtime.round_snapshot_builder import RoundSnapshotBuilder
from awp_rp_runtime_v3.runtime.director_runtime import DirectorRuntime, FakeDirectorAdapter
from awp_rp_runtime_v3.runtime.agent_runtime_registry import AgentRuntimeRegistry, AgentRunner
from awp_rp_runtime_v3.runtime.task_envelope_builder import TaskEnvelopeBuilder
from awp_rp_runtime_v3.runtime.dynamic_subagent_pool import DynamicSubAgentPool
from awp_rp_runtime_v3.runtime.suggestion_merger import SuggestionMerger
from awp_rp_runtime_v3.runtime.writer_input_bundle_builder import WriterInputBundleBuilder
from awp_rp_runtime_v3.testing.fakes.fake_stores import (
    FakeCardStateStore, FakeTurnRecordStore, FakeActiveMemoryStore, FakeRagMemoryStore,
)


class TestP2EndToEnd:
    """Full P2 chain with no state/memory writes."""

    def test_full_chain_no_writes(self):
        # Setup stores (to verify no writes)
        cs_store = FakeCardStateStore()
        tr_store = FakeTurnRecordStore()
        am_store = FakeActiveMemoryStore()
        rm_store = FakeRagMemoryStore()

        # 1. Initialize CardState
        cs_store.initialize("card1", "sess1")
        initial_state = cs_store.load("card1", "sess1")
        initial_revision = initial_state.revision

        # 2. Build RoundSnapshot
        snapshot_builder = RoundSnapshotBuilder(cs_store, tr_store, am_store, rm_store)
        snapshot = snapshot_builder.build("card1", "sess1", "我走进了月光庭院")
        assert snapshot.base_card_state_revision == 0

        # 3. Director generates TurnBrief + DelegationPlan with 2 tasks
        director_adapter = FakeDirectorAdapter()
        director_adapter.set_plan(DelegationPlan(
            tasks=[
                DelegationTask(
                    task_id="task_continuity", role="continuity-checker",
                    purpose="Check timeline consistency",
                    input_field_allowlist=["card_state", "player_input"],
                    expected_suggestion_kinds=["continuity_issue"],
                ),
                DelegationTask(
                    task_id="task_memory", role="memory-curator",
                    purpose="Identify memory candidates",
                    input_field_allowlist=["card_state", "player_input"],
                    expected_suggestion_kinds=["memory_candidate"],
                ),
            ],
            total_token_budget=10000,
        ))
        director = DirectorRuntime(director_adapter)
        brief, plan = director.run(snapshot)

        assert brief.brief_id != ""
        assert plan.plan_id != ""
        assert len(plan.tasks) == 2

        # 4. Register fake runners
        registry = AgentRuntimeRegistry()

        class ContinuityRunner:
            def run(self, envelope):
                return [AgentSuggestion(
                    suggestion_id="sug_c1",
                    kind=SuggestionKind.CONTINUITY_ISSUE,
                    summary="No continuity issues found",
                    confidence=0.9,
                    evidence=["Checked all turns"],
                    source_refs=["snapshot:snap1"],
                    recommendations=["Continue as planned"],
                )]

        class MemoryCuratorRunner:
            def run(self, envelope):
                return [AgentSuggestion(
                    suggestion_id="sug_m1",
                    kind=SuggestionKind.MEMORY_CANDIDATE,
                    summary="Player entered moonlight courtyard",
                    confidence=0.8,
                    evidence=["Player input"],
                    source_refs=["player_input"],
                    proposed_memory_candidates=[{
                        "content": "Player visited the moonlight courtyard",
                        "importance": 0.7,
                    }],
                )]

        registry.register_runner("continuity-checker", ContinuityRunner())
        registry.register_runner("memory-curator", MemoryCuratorRunner())

        # 5. Execute pool
        envelope_builder = TaskEnvelopeBuilder(registry)
        pool = DynamicSubAgentPool(registry, envelope_builder)
        exec_results = pool.execute(plan, snapshot)

        assert len(exec_results) == 2
        assert all(r.success for r in exec_results)
        assert len(exec_results[0].suggestions) == 1
        assert len(exec_results[1].suggestions) == 1

        # 6. Merge suggestions
        merger = SuggestionMerger()
        merge_result = merger.merge(plan, brief, snapshot, exec_results)

        assert len(merge_result.adopted) == 2
        assert merge_result.failed_tasks == []

        # 7. Build WriterInputBundle
        bundle_builder = WriterInputBundleBuilder()
        bundle = bundle_builder.build(snapshot, brief, merge_result)

        assert bundle.bundle_id != ""
        assert bundle.round_snapshot_ref == snapshot.snapshot_id
        assert bundle.turn_brief_ref == brief.brief_id
        assert bundle.suggestion_merge_ref == merge_result.merge_id
        assert len(bundle.accepted_guidance) >= 1

        # 8. Verify NO state/memory writes occurred
        final_state = cs_store.load("card1", "sess1")
        assert final_state.revision == initial_revision  # Unchanged
        assert tr_store.get_recent("card1", "sess1") == []
        assert am_store.get_all("card1", "sess1") == []

        # 9. Verify traces are queryable
        assert snapshot.trace_id != ""
        assert brief.trace_id == snapshot.trace_id
        assert plan.trace_id == snapshot.trace_id
        assert merge_result.trace_id == snapshot.trace_id
        assert bundle.trace_id == snapshot.trace_id

    def test_empty_delegation_plan(self):
        """Test 5: empty plan completes normally."""
        from awp_rp_runtime_v3.contracts.turn_brief import TurnBrief

        registry = AgentRuntimeRegistry()
        builder = TaskEnvelopeBuilder(registry)
        pool = DynamicSubAgentPool(registry, builder)

        snapshot = RoundSnapshot(
            snapshot_id="s1", trace_id="t1",
            card_id="c1", session_id="s1",
            card_state=CardState(card_id="c1", session_id="s1"),
        )
        plan = DelegationPlan(tasks=[])

        results = pool.execute(plan, snapshot)
        assert results == []

        merger = SuggestionMerger()
        brief = TurnBrief(brief_id="b1")
        merge = merger.merge(plan, brief, snapshot, results)
        assert merge.adopted == []

    def test_subagent_cannot_delegate(self):
        """Test 12: sub-agent cannot delegate."""
        from awp_rp_runtime_v3.contracts.agent_task_envelope import AgentTaskEnvelope
        envelope = AgentTaskEnvelope()
        assert "Cannot delegate to sub-agents" in envelope.prohibitions
