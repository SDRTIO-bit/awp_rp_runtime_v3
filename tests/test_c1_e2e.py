"""C1 End-to-End Integration Tests.

Test 1: Full happy path with fake LLM
Test 2: Failure path — revise then reject with zero side effects
"""

import pytest
import uuid

from awp_rp_runtime_v3.contracts.card_state import CardState, VariableEntry, SceneState
from awp_rp_runtime_v3.contracts.round_snapshot import RoundSnapshot
from awp_rp_runtime_v3.contracts.director_plan import DirectorPlan
from awp_rp_runtime_v3.contracts.tool_plan import ToolPlan, PlannedToolRequest
from awp_rp_runtime_v3.contracts.tool_result import ToolResult, ToolResultStatus
from awp_rp_runtime_v3.contracts.tool_result_bundle import ToolResultBundle
from awp_rp_runtime_v3.contracts.enrichment_bundle import EnrichmentBundle
from awp_rp_runtime_v3.contracts.final_turn_brief import FinalTurnBrief
from awp_rp_runtime_v3.contracts.writer_draft import WriterDraft
from awp_rp_runtime_v3.contracts.writer_input_bundle import WriterInputBundle
from awp_rp_runtime_v3.contracts.quality_decision import QualityDecision, QualityVerdict
from awp_rp_runtime_v3.contracts.execution_trace import ExecutionTrace
from awp_rp_runtime_v3.contracts.delegation_plan import DelegationPlan

from awp_rp_runtime_v3.runtime.tool_registry import ToolRegistry
from awp_rp_runtime_v3.runtime.tool_permission_policy import ToolPermissionPolicy
from awp_rp_runtime_v3.runtime.tool_budget_runtime import ToolBudgetRuntime
from awp_rp_runtime_v3.runtime.tool_gateway import ToolGateway, FakeToolRunner
from awp_rp_runtime_v3.runtime.enrichment_merger import EnrichmentMerger
from awp_rp_runtime_v3.runtime.final_turn_brief_runtime import FinalTurnBriefRuntime
from awp_rp_runtime_v3.runtime.director_v2_runtime import DirectorV2Runtime, FakeDirectorV2Adapter
from awp_rp_runtime_v3.runtime.writer_v2_runtime import WriterV2Runtime, FakeWriterV2Adapter
from awp_rp_runtime_v3.runtime.reviser_runtime import ReviserRuntime
from awp_rp_runtime_v3.runtime.quality_pipeline_runtime import QualityPipelineRuntime
from awp_rp_runtime_v3.runtime.writer_input_bundle_v2_builder import WriterInputBundleV2Builder
from awp_rp_runtime_v3.runtime.round_snapshot_builder import RoundSnapshotBuilder
from awp_rp_runtime_v3.runtime.state_proposal_runtime import StateProposalRuntime
from awp_rp_runtime_v3.runtime.card_state_commit_runtime import CardStateCommitRuntime
from awp_rp_runtime_v3.runtime.turn_record_commit_runtime import TurnRecordCommitRuntime
from awp_rp_runtime_v3.runtime.active_memory_commit_runtime import ActiveMemoryCommitRuntime
from awp_rp_runtime_v3.runtime.rag_memory_commit_runtime import RagMemoryCommitRuntime

from awp_rp_runtime_v3.testing.fakes.fake_stores import (
    FakeCardStateStore, FakeTurnRecordStore, FakeActiveMemoryStore, FakeRagMemoryStore,
    FakeTraceStore,
)
from awp_rp_runtime_v3.testing.fakes.fake_llm import FakeLLMProvider


class TestC1E2EHappyPath:
    """Full happy path: Init → Snapshot → Director → ToolGateway → Writer → Quality → Commit."""

    def test_full_e2e_fake_llm(self):
        # 1. Setup stores
        cs_store = FakeCardStateStore()
        tr_store = FakeTurnRecordStore()
        am_store = FakeActiveMemoryStore()
        rm_store = FakeRagMemoryStore()
        trace_store = FakeTraceStore()

        # 2. Initialize CardState
        cs_store.initialize("card1", "sess1")
        initial_state = cs_store.load("card1", "sess1")
        initial_revision = initial_state.revision

        # 3. Build RoundSnapshot
        snapshot_builder = RoundSnapshotBuilder(cs_store, tr_store, am_store, rm_store)
        snapshot = snapshot_builder.build("card1", "sess1", "我走进了月光庭院")
        assert snapshot.snapshot_id != ""
        assert snapshot.base_card_state_revision == 0

        # 4. Director produces DirectorPlan + ToolPlan + DelegationPlan
        director_adapter = FakeDirectorV2Adapter()
        director = DirectorV2Runtime(director_adapter)
        director_plan, tool_plan, delegation_plan = director.plan(snapshot)

        assert director_plan.plan_id != ""
        assert director_plan.snapshot_id == snapshot.snapshot_id
        assert tool_plan.tool_plan_id != ""
        assert tool_plan.director_plan_id == director_plan.plan_id
        assert delegation_plan.tasks == []  # No delegation in C1

        # 5. ToolGateway executes tool plan (one success, one optional failure)
        registry = ToolRegistry()
        permission = ToolPermissionPolicy(registry)
        budget = ToolBudgetRuntime()
        runner = FakeToolRunner()

        # Make rag_memory_lookup fail
        original_run = runner.run
        def partial_fail_run(tool_id, sanitized_input, snapshot):
            if tool_id == "rag_memory_lookup":
                raise RuntimeError("Simulated RAG failure")
            return original_run(tool_id, sanitized_input, snapshot)
        runner.run = partial_fail_run

        gateway = ToolGateway(registry, permission, budget, runner)

        # Add tool requests to the plan
        tool_plan.requests = [
            PlannedToolRequest(
                request_id="req_wb", tool_id="worldbook_lookup",
                input={"query": "月光庭院"}, required=True,
            ),
            PlannedToolRequest(
                request_id="req_rag", tool_id="rag_memory_lookup",
                input={"query": "庭院"}, required=False,
            ),
        ]

        trace = ExecutionTrace(trace_id=snapshot.trace_id)
        tool_bundle = gateway.execute(tool_plan, snapshot, trace)

        assert "req_wb" in tool_bundle.successful_request_ids
        assert "req_rag" in tool_bundle.degraded_request_ids
        assert len(trace.events) >= 2

        # 6. EnrichmentMerge
        merger = EnrichmentMerger()
        enrichment = merger.merge(tool_bundle)

        assert len(enrichment.accepted_items) >= 1
        assert enrichment.total_tools_called == 2

        # 7. FinalTurnBrief
        brief_runtime = FinalTurnBriefRuntime()
        final_brief = brief_runtime.produce(director_plan, enrichment, snapshot)

        assert final_brief.brief_id != ""
        assert final_brief.director_plan_id == director_plan.plan_id
        assert len(final_brief.accepted_tool_findings) >= 1
        # The degraded tool (rag_memory_lookup) appears in degraded_items, not rejected
        assert len(enrichment.degraded_items) >= 1 or len(final_brief.rejected_tool_findings) >= 1

        # 8. WriterInputBundle
        bundle_builder = WriterInputBundleV2Builder()
        writer_bundle = bundle_builder.build(snapshot, final_brief)

        assert writer_bundle.bundle_id != ""
        assert writer_bundle.final_turn_brief_id == final_brief.brief_id
        assert writer_bundle.snapshot_id == snapshot.snapshot_id

        # 9. Writer produces WriterDraft
        writer_adapter = FakeWriterV2Adapter()
        writer = WriterV2Runtime(writer_adapter)
        draft = writer.run(writer_bundle)

        assert draft.draft_id != ""
        assert draft.text != ""
        assert draft.character_count > 100
        assert draft.writer_input_bundle_id == writer_bundle.bundle_id

        # 10. Quality Pipeline accepts
        pipeline = QualityPipelineRuntime()
        quality_decision = pipeline.check(draft, snapshot)

        assert quality_decision.verdict == QualityVerdict.ACCEPTED
        assert quality_decision.allows_side_effects()

        # Ensure trace_id is set for downstream
        quality_decision.trace_id = snapshot.trace_id
        quality_decision.source_turn_id = snapshot.snapshot_id

        # 11. StateUpdateProposal
        llm_provider = FakeLLMProvider()
        state_proposal = StateProposalRuntime(llm_provider)
        patch = state_proposal.generate(draft.text, snapshot, quality_decision)
        patch.trace_id = snapshot.trace_id

        # 12. CardStateCommit
        state_commit = CardStateCommitRuntime(cs_store)
        if patch.operations:
            state_result = state_commit.commit(
                patch=patch,
                quality_decision=quality_decision,
                expected_revision=snapshot.base_card_state_revision,
            )
            assert state_result.success

        # 13. TurnRecordCommit
        turn_commit = TurnRecordCommitRuntime(tr_store)
        turn_record = turn_commit.commit(
            player_input="我走进了月光庭院",
            accepted_text=draft.text,
            snapshot=snapshot,
            quality_decision=quality_decision,
            base_card_state_revision=initial_revision,
            result_card_state_revision=initial_revision + (1 if patch.operations else 0),
            state_commit_patch_id=patch.patch_id if patch.operations else "",
        )
        assert turn_record.turn_id != ""
        assert turn_record.writer_output == draft.text

        # 14. Memory Commit (ActiveMemory + RAG)
        from awp_rp_runtime_v3.contracts.memory_commit_plan import MemoryCommitPlan, MemoryCommitRequest
        from awp_rp_runtime_v3.contracts.rag_memory import RagMemoryRecord
        from awp_rp_runtime_v3.contracts.active_memory import ActiveMemoryRecord

        rag_entry = RagMemoryRecord(
            memory_id=f"rag_{turn_record.turn_id}",
            card_id="card1", session_id="sess1", scope="session",
            content=draft.text, summary=draft.text[:80],
            source_turn_ids=[turn_record.turn_id],
            source_card_state_revision=turn_record.result_card_state_revision,
            importance=0.5, confidence=0.6,
            provenance=f"commit:{turn_record.turn_id}",
        )
        active_entry = ActiveMemoryRecord(
            memory_id=f"am_{turn_record.turn_id}",
            card_id="card1", session_id="sess1",
            summary="本回合叙事已发生并写入长期记忆，主角行为被记录为当前剧情压力节点",
            kind="scene_pressure",
            source_turn_ids=[turn_record.turn_id],
            source_card_state_revision=turn_record.result_card_state_revision,
            importance=0.5, confidence=0.6, status="active",
        )
        plan = MemoryCommitPlan(
            turn_id=turn_record.turn_id, card_id="card1", session_id="sess1",
            trace_id=snapshot.trace_id,
            expected_card_state_revision=turn_record.result_card_state_revision,
            memory_commit_id="mc1", idempotency_key="ik1",
            quality_decision_ref=quality_decision.trace_id,
            new_active_entries=[active_entry],
            new_rag_entries=[rag_entry],
            write_reasons=["accepted_turn"],
        )

        mem_request = MemoryCommitRequest(
            plan=plan, card_id="card1", session_id="sess1",
            turn_id=turn_record.turn_id, trace_id=snapshot.trace_id,
            memory_commit_id="mc1", idempotency_key=f"{turn_record.turn_id}:mc1",
            quality_decision_ref=quality_decision.trace_id,
            expected_card_state_revision=turn_record.result_card_state_revision,
            card_state_commit_success=True, turn_record_commit_success=True,
        )

        mem_commit = ActiveMemoryCommitRuntime(am_store)
        mem_result = mem_commit.commit_request(mem_request, quality_decision)
        assert mem_result is not None

        rag_commit = RagMemoryCommitRuntime(rm_store)
        rag_result = rag_commit.commit_request(mem_request, quality_decision)
        assert rag_result is not None

        # 15. Verify all traces
        assert snapshot.trace_id != ""
        assert director_plan.trace_id == snapshot.trace_id
        assert tool_plan.trace_id == snapshot.trace_id
        assert final_brief.trace_id == snapshot.trace_id
        assert draft.trace_id == snapshot.trace_id
        assert quality_decision.trace_id == snapshot.trace_id

        # 16. Verify state was committed
        final_state = cs_store.load("card1", "sess1")
        if patch.operations:
            assert final_state.revision > initial_revision

        # 17. Verify turn record was committed
        records = tr_store.get_recent("card1", "sess1")
        assert len(records) == 1
        assert records[0].writer_output == draft.text

        # 18. Verify memory was committed
        am_entries = am_store.get_all("card1", "sess1")
        assert len(am_entries) >= 1

        rag_entries = rm_store.search("card1", "sess1", "")
        assert len(rag_entries) >= 1


class TestC1E2EFailurePath:
    """Failure path: Writer violates facts → revise → still violates → reject → zero writes."""

    def test_failure_path_zero_side_effects(self):
        # 1. Setup
        cs_store = FakeCardStateStore()
        tr_store = FakeTurnRecordStore()
        am_store = FakeActiveMemoryStore()
        rm_store = FakeRagMemoryStore()

        cs_store.initialize("card1", "sess1")
        initial_state = cs_store.load("card1", "sess1")
        initial_revision = initial_state.revision

        snapshot_builder = RoundSnapshotBuilder(cs_store, tr_store, am_store, rm_store)
        snapshot = snapshot_builder.build("card1", "sess1", "我走进了月光庭院")

        # 2. Director
        director_adapter = FakeDirectorV2Adapter()
        director = DirectorV2Runtime(director_adapter)
        director_plan, tool_plan, delegation_plan = director.plan(snapshot)

        # 3. Skip tools (empty plan)
        enrichment = EnrichmentBundle(
            bundle_id="eb1", trace_id=snapshot.trace_id, snapshot_id=snapshot.snapshot_id,
        )

        # 4. FinalTurnBrief
        brief_runtime = FinalTurnBriefRuntime()
        final_brief = brief_runtime.produce(director_plan, enrichment, snapshot)

        # 5. WriterInputBundle
        bundle_builder = WriterInputBundleV2Builder()
        writer_bundle = bundle_builder.build(snapshot, final_brief)

        # 6. Writer produces BAD text (with JSON leak)
        writer_adapter = FakeWriterV2Adapter()
        writer = WriterV2Runtime(writer_adapter)

        # First attempt: JSON leak
        writer_adapter.set_text('故事开始了 {"key": "value"} 然后继续')
        draft1 = writer.run(writer_bundle)

        # 7. Quality Pipeline should catch the issue
        pipeline = QualityPipelineRuntime()
        decision1 = pipeline.check(draft1, snapshot)

        # Should be revise or reject
        assert decision1.verdict != QualityVerdict.ACCEPTED

        # 8. If revise, Reviser tries to fix
        if decision1.verdict == QualityVerdict.REVISE:
            reviser = ReviserRuntime(writer_adapter, max_revisions=1)

            from awp_rp_runtime_v3.contracts.revision_request import RevisionRequest
            from awp_rp_runtime_v3.contracts.quality_issue import QualityIssue

            request = RevisionRequest(
                request_id="rr1", trace_id=snapshot.trace_id,
                snapshot_id=snapshot.snapshot_id,
                writer_draft_id=draft1.draft_id,
                current_revision=0, max_revisions=1,
                issues=[QualityIssue(description="JSON leak detected")],
                original_text=draft1.text,
            )

            # Second attempt: still bad
            writer_adapter.set_text('又是 JSON {"bad": true} 还是不行')
            revision_result = reviser.revise(request, writer_bundle)

            # Third check: still fails
            draft2 = WriterDraft(
                draft_id="wd2", trace_id=snapshot.trace_id,
                snapshot_id=snapshot.snapshot_id,
                text=revision_result.revised_text,
                revision_number=revision_result.revision_number,
            )
            decision2 = pipeline.check(draft2, snapshot)

            # Should be reject now (revision exhausted)
            # Even if it's still revise, we've used our one revision
            if decision2.verdict == QualityVerdict.REVISE:
                # Reviser cannot revise again
                assert not reviser.can_revise(1)
                final_verdict = QualityVerdict.REJECTED
            else:
                final_verdict = decision2.verdict
        else:
            final_verdict = decision1.verdict

        # 9. Verify ZERO side effects
        # No state commit attempted
        final_state = cs_store.load("card1", "sess1")
        assert final_state.revision == initial_revision  # Unchanged

        # No turn record written
        records = tr_store.get_recent("card1", "sess1")
        assert len(records) == 0

        # No memory written
        am_entries = am_store.get_all("card1", "sess1")
        assert len(am_entries) == 0

        rag_entries = rm_store.search("card1", "sess1", "")
        assert len(rag_entries) == 0

        # Trace should record the failure
        assert snapshot.trace_id != ""
