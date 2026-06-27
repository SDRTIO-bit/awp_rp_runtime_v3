"""TurnOrchestrator — orchestrates the complete turn lifecycle.

Uses the new CardStatePatch / CardStateCommitRequest / Gate contracts.
D6: Integrates Memory Curator Agent for post-acceptance memory governance.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.turn_brief import TurnBrief
from ..contracts.delegation_plan import DelegationPlan
from ..contracts.agent_suggestion import AgentSuggestion
from ..contracts.suggestion_merge_result import SuggestionMergeResult
from ..contracts.quality_decision import QualityDecision, QualityVerdict
from ..contracts.card_state_patch import CardStatePatch
from ..contracts.card_state_commit import CardStateCommitResult
from ..contracts.turn_record import TurnRecord, TurnMode
from ..contracts.execution_trace import ExecutionTrace, TraceEvent

from .round_snapshot_builder import RoundSnapshotBuilder
from .director_runtime import DirectorRuntime
from .delegation_planner import DelegationPlanner
from .dynamic_subagent_pool import DynamicSubAgentPool
from .suggestion_merger import SuggestionMerger
from .writer_runtime import WriterRuntime
from .critic_runtime import CriticRuntime
from .state_proposal_runtime import StateProposalRuntime
from .card_state_commit_runtime import CardStateCommitRuntime
from .turn_record_commit_runtime import TurnRecordCommitRuntime
from .active_memory_commit_runtime import ActiveMemoryCommitRuntime
from .rag_memory_commit_runtime import RagMemoryCommitRuntime
from .retry_runtime import RetryRuntime


class TurnResult:

    def __init__(self):
        self.success: bool = False
        self.accepted_text: str = ""
        self.turn_record: TurnRecord | None = None
        self.quality_decision: QualityDecision | None = None
        self.state_commit_result: CardStateCommitResult | None = None
        self.snapshot: RoundSnapshot | None = None
        self.trace: ExecutionTrace | None = None
        self.error: str | None = None


class TurnOrchestrator:

    def __init__(
        self,
        snapshot_builder: RoundSnapshotBuilder,
        director: DirectorRuntime,
        delegation_planner: DelegationPlanner,
        subagent_pool: DynamicSubAgentPool,
        suggestion_merger: SuggestionMerger,
        writer: WriterRuntime,
        critic: CriticRuntime,
        state_proposal: StateProposalRuntime,
        state_commit: CardStateCommitRuntime,
        turn_commit: TurnRecordCommitRuntime,
        memory_commit: ActiveMemoryCommitRuntime,
        rag_commit: RagMemoryCommitRuntime,
        retry_runtime: RetryRuntime,
        max_retries: int = 3,
    ):
        self.snapshot_builder = snapshot_builder
        self.director = director
        self.delegation_planner = delegation_planner
        self.subagent_pool = subagent_pool
        self.suggestion_merger = suggestion_merger
        self.writer = writer
        self.critic = critic
        self.state_proposal = state_proposal
        self.state_commit = state_commit
        self.turn_commit = turn_commit
        self.memory_commit = memory_commit
        self.rag_commit = rag_commit
        self.retry_runtime = retry_runtime
        self.max_retries = max_retries

    def execute_turn(
        self,
        card_id: str,
        session_id: str,
        player_input: str,
        worldbook_entries: list[dict[str, Any]] | None = None,
        mode: TurnMode = TurnMode.NORMAL,
        parent_turn_id: str = "",
    ) -> TurnResult:
        result = TurnResult()
        trace = ExecutionTrace(
            trace_id=f"trace_{uuid.uuid4().hex[:12]}",
            card_id=card_id,
            session_id=session_id,
        )
        result.trace = trace

        try:
            # 1. Build snapshot
            self._trace(trace, "snapshot_built", "snapshot_builder")
            snapshot = self.snapshot_builder.build(
                card_id, session_id, player_input, worldbook_entries
            )
            trace.trace_id = snapshot.trace_id
            result.snapshot = snapshot

            # 2. Director
            self._trace(trace, "director_called", "director")
            turn_brief, delegation_plan = self.director.run(snapshot)

            # 3. Delegation
            self._trace(trace, "delegation_planned", "delegation_planner")
            delegation_plan, _ = self.delegation_planner.validate_and_filter(delegation_plan)

            # 4. Sub-agents
            self._trace(trace, "subagent_called", "subagent_pool")
            exec_results = self.subagent_pool.execute(delegation_plan, snapshot)

            # 5. Merge
            self._trace(trace, "suggestions_merged", "suggestion_merger")
            merge_result = self.suggestion_merger.merge(
                delegation_plan, turn_brief, snapshot, exec_results
            )

            # 6-7. Writer + Quality Gate (retry loop)
            retry_count = 0
            accepted = False
            candidate_text = ""
            quality_decision = None

            while retry_count <= self.max_retries:
                self._trace(trace, "writer_called", "writer")
                candidate_text = self.writer.run(snapshot, turn_brief, merge_result)

                self._trace(trace, "quality_checked", "critic")
                quality_decision = self.critic.check(
                    candidate_text, snapshot, retry_count, self.max_retries
                )
                quality_decision.trace_id = snapshot.trace_id
                quality_decision.source_turn_id = snapshot.snapshot_id

                if quality_decision.is_accepted():
                    accepted = True
                    break

                if not quality_decision.can_retry():
                    break
                retry_count += 1

            if not accepted or quality_decision is None:
                result.quality_decision = quality_decision
                result.error = "Quality gate rejected after all retries"
                trace.success = False
                return result

            result.quality_decision = quality_decision
            result.accepted_text = candidate_text

            # 8. State proposal
            self._trace(trace, "state_proposed", "state_proposal")
            patch = self.state_proposal.generate(candidate_text, snapshot, quality_decision)
            patch.trace_id = snapshot.trace_id

            # 9. Commit state
            state_result = None
            if patch.operations:
                self._trace(trace, "state_committed", "state_commit")
                state_result = self.state_commit.commit(
                    patch=patch,
                    quality_decision=quality_decision,
                    expected_revision=snapshot.base_card_state_revision,
                )
                result.state_commit_result = state_result
                if not state_result.success:
                    result.error = f"State commit failed: {state_result.error_message}"
                    trace.success = False
                    return result

            # 10. Commit turn record
            self._trace(trace, "turn_committed", "turn_commit")
            base_rev = snapshot.base_card_state_revision
            result_rev = state_result.to_revision if state_result else base_rev

            turn_record = self.turn_commit.commit(
                player_input=player_input,
                accepted_text=candidate_text,
                snapshot=snapshot,
                quality_decision=quality_decision,
                base_card_state_revision=base_rev,
                result_card_state_revision=result_rev,
                state_commit_patch_id=patch.patch_id,
                mode=mode,
                parent_turn_id=parent_turn_id,
            )
            result.turn_record = turn_record

            # 11-12. Memory commit (formal path: gate-gated, idempotent, deterministic).
            memory_results = self._commit_memory(
                trace, snapshot, turn_record, quality_decision, state_result
            )
            turn_record.memory_commit_refs = [
                r.receipt.memory_commit_id for r in memory_results
                if r is not None and r.receipt is not None
            ]

            result.success = True
            trace.success = True

        except Exception as e:
            result.error = str(e)
            trace.success = False
            self._trace(trace, "error", "orchestrator", error=str(e))

        return result

    def _commit_memory(
        self,
        trace: ExecutionTrace,
        snapshot: RoundSnapshot,
        turn_record: TurnRecord,
        quality_decision: QualityDecision,
        state_result: CardStateCommitResult | None,
    ) -> list:
        """Run ActiveMemory + RAG memory commits via the formal commit_request path.

        D6: Uses MemoryCurationRuntime + MemoryPlanCompiler to produce an
        intelligent MemoryCommitPlan, then commits via the existing runtimes.
        Falls back to deterministic M1 fixture if curator is not available or
        returns a degraded/no-op result.
        """
        from ..contracts.memory_commit_plan import MemoryCommitRequest
        from .memory_curation_runtime import MemoryCurationRuntime
        from .memory_plan_compiler import MemoryPlanCompiler

        # D6: Run Memory Curator
        curation_runtime = MemoryCurationRuntime()
        curation_result = curation_runtime.curate(
            quality_decision=quality_decision,
            card_state_commit_result=state_result,
            turn_record=turn_record,
            snapshot=snapshot,
            trace=trace,
        )

        # Compile curation result into MemoryCommitPlan
        compiler = MemoryPlanCompiler()
        plan = compiler.compile(
            curation_result=curation_result,
            turn_id=turn_record.turn_id,
            card_id=turn_record.card_id,
            session_id=turn_record.session_id,
            trace_id=snapshot.trace_id,
            expected_card_state_revision=(
                state_result.to_revision if state_result
                else snapshot.base_card_state_revision
            ),
            quality_decision_ref=quality_decision.trace_id,
        )

        memory_commit_id = plan.memory_commit_id or f"mc_{uuid.uuid4().hex[:12]}"
        idempotency_key = plan.idempotency_key or f"{turn_record.turn_id}:{memory_commit_id}"

        request = MemoryCommitRequest(
            plan=plan,
            card_id=turn_record.card_id,
            session_id=turn_record.session_id,
            turn_id=turn_record.turn_id,
            trace_id=snapshot.trace_id,
            memory_commit_id=memory_commit_id,
            idempotency_key=idempotency_key,
            quality_decision_ref=quality_decision.trace_id,
            expected_card_state_revision=(
                state_result.to_revision if state_result else snapshot.base_card_state_revision
            ),
            card_state_commit_success=state_result is not None and state_result.success
                or (state_result is None and True),
            turn_record_commit_success=True,
        )

        active_result = self.memory_commit.commit_request(request, quality_decision)
        rag_result = self.rag_commit.commit_request(request, quality_decision)

        self._trace(trace, "memory_committed", "memory_commit")
        return [active_result, rag_result]

    def _trace(self, trace: ExecutionTrace, event_type: str, actor: str, error: str | None = None):
        trace.add_event(TraceEvent(
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            event_type=event_type,
            actor=actor,
            success=error is None,
            error=error,
        ))
