"""MemoryCurationRuntime — orchestrates the Memory Curator Agent.

This is the main runtime for D6. It:
1. Evaluates the trigger policy
2. Builds a curation request
3. Plans the query
4. Runs the adapter (fake or LLM)
5. Returns a MemoryCurationResult

The Memory Curator is a POST-ACCEPTANCE agent. It does NOT run in the
DynamicSubAgentPool. It runs AFTER:
  Writer → QualityGate ACCEPT → CardStateCommit SUCCESS → TurnRecordCommit SUCCESS

It does NOT produce player-visible text. It does NOT write to stores.
It only produces a MemoryCurationResult which is compiled into a MemoryCommitPlan.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..contracts.quality_decision import QualityDecision
from ..contracts.card_state_commit import CardStateCommitResult
from ..contracts.turn_record import TurnRecord
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.execution_trace import ExecutionTrace, TraceEvent
from ..contracts.memory_curation_trigger_diagnostics import (
    MemoryCurationTriggerDiagnostics,
)
from ..contracts.memory_curation_request import MemoryCurationRequest
from ..contracts.memory_curation_result import MemoryCurationResult

from .memory_curation_trigger_policy import MemoryCurationTriggerPolicy
from .memory_curation_query_planner import MemoryCurationQueryPlanner
from .memory_curator_adapter import FakeMemoryCuratorAdapter


class MemoryCurationRuntime:
    """Orchestrates the Memory Curator Agent.

    Post-acceptance only. No writes. No delegation. No final text.
    """

    def __init__(
        self,
        trigger_policy: MemoryCurationTriggerPolicy | None = None,
        query_planner: MemoryCurationQueryPlanner | None = None,
        adapter: FakeMemoryCuratorAdapter | None = None,
    ):
        self.trigger_policy = trigger_policy or MemoryCurationTriggerPolicy()
        self.query_planner = query_planner or MemoryCurationQueryPlanner()
        self.adapter = adapter or FakeMemoryCuratorAdapter()

    def curate(
        self,
        quality_decision: QualityDecision,
        card_state_commit_result: CardStateCommitResult | None,
        turn_record: TurnRecord,
        snapshot: RoundSnapshot,
        trace: ExecutionTrace | None = None,
        existing_curated_turn_ids: set[str] | None = None,
    ) -> MemoryCurationResult:
        """Run memory curation for an accepted turn.

        Returns a MemoryCurationResult with accepted/rejected candidates.
        If the trigger policy says no-op, returns an empty result.
        """
        # 1. Evaluate trigger policy
        trigger_result = self.trigger_policy.evaluate(
            quality_decision=quality_decision,
            card_state_commit_result=card_state_commit_result,
            turn_record_committed=True,
            turn_record=turn_record,
            snapshot=snapshot,
            existing_curated_turn_ids=existing_curated_turn_ids,
        )

        if trace:
            trace.add_event(TraceEvent(
                event_id=f"evt_{uuid.uuid4().hex[:8]}",
                event_type="memory_curation_triggered",
                actor="memory_curator",
                details={
                    "should_trigger": trigger_result.should_trigger,
                    "risk_level": trigger_result.risk_level,
                    "skip_reason": trigger_result.skip_reason,
                },
                success=True,
            ))

        # 2. No-op path: return empty result
        if not trigger_result.should_trigger:
            return MemoryCurationResult(
                result_id=f"mcr_{turn_record.turn_id}",
                trace_id=snapshot.trace_id,
                turn_id=turn_record.turn_id,
                card_id=turn_record.card_id,
                session_id=turn_record.session_id,
                degraded=False,
            )

        # 3. Build curation request
        request = self._build_request(
            turn_record, snapshot, trigger_result,
        )

        # 4. Plan the query
        query_plan = self.query_planner.plan(
            trigger_result, turn_record, snapshot,
        )

        # 5. Run the adapter
        try:
            result = self.adapter.curate(request, query_plan)
        except Exception as e:
            # Curator failure is degraded, not fatal
            return MemoryCurationResult(
                result_id=f"mcr_{turn_record.turn_id}",
                trace_id=snapshot.trace_id,
                turn_id=turn_record.turn_id,
                card_id=turn_record.card_id,
                session_id=turn_record.session_id,
                degraded=True,
                degraded_reasons=[f"adapter_error: {str(e)}"],
            )

        if trace:
            trace.add_event(TraceEvent(
                event_id=f"evt_{uuid.uuid4().hex[:8]}",
                event_type="memory_curator_called",
                actor="memory_curator",
                details={
                    "total_generated": result.total_candidates_generated,
                    "total_accepted": result.total_candidates_accepted,
                    "total_rejected": result.total_candidates_rejected,
                    "degraded": result.degraded,
                },
                success=not result.degraded,
            ))

        return result

    def _build_request(
        self,
        turn_record: TurnRecord,
        snapshot: RoundSnapshot,
        trigger: MemoryCurationTriggerDiagnostics,
    ) -> MemoryCurationRequest:
        """Build a MemoryCurationRequest from accepted turn data."""
        # Serialize active memories
        active_snapshot = []
        for mem in snapshot.active_memories:
            if isinstance(mem, dict):
                active_snapshot.append(mem)
            elif hasattr(mem, "to_dict"):
                active_snapshot.append(mem.to_dict())

        # Serialize RAG recall
        rag_snapshot = []
        for rag in snapshot.rag_recall:
            if isinstance(rag, dict):
                rag_snapshot.append(rag)
            elif hasattr(rag, "to_dict"):
                rag_snapshot.append(rag.to_dict())

        # Serialize recent turns
        recent_turns = []
        for tr in snapshot.recent_turn_records:
            if hasattr(tr, "to_dict"):
                recent_turns.append(tr.to_dict())
            elif isinstance(tr, dict):
                recent_turns.append(tr)

        # Serialize card state
        card_state_dict = {}
        if snapshot.card_state and hasattr(snapshot.card_state, "to_dict"):
            card_state_dict = snapshot.card_state.to_dict()

        return MemoryCurationRequest(
            request_id=f"mcr_{uuid.uuid4().hex[:12]}",
            trace_id=snapshot.trace_id,
            task_run_id=f"task_{uuid.uuid4().hex[:12]}",
            card_id=turn_record.card_id,
            session_id=turn_record.session_id,
            turn_id=turn_record.turn_id,
            accepted_turn_record_ref=turn_record.turn_id,
            accepted_output=turn_record.writer_output or "",
            player_input=turn_record.player_input or "",
            quality_decision_ref=turn_record.quality_decision_ref,
            card_state_commit_ref=turn_record.state_commit_ref,
            turn_record_commit_ref=turn_record.turn_id,
            card_state_delta_summary="",
            active_memory_snapshot=active_snapshot,
            rag_memory_snapshot=rag_snapshot,
            recent_turn_records=recent_turns,
            card_state_snapshot=card_state_dict,
            max_active_candidates=trigger.max_active_candidates,
            max_rag_candidates=trigger.max_rag_candidates,
            idempotency_key=trigger.idempotency_key,
        )
