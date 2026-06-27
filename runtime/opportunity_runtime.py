"""OpportunityRuntime — orchestrates the Opportunity Agent.

Flow:
  RoundSnapshot + DelegationTask + TriggerResult
  → build OpportunityRequest
  → plan queries via OpportunityQueryPlanner
  → collect evidence from snapshot
  → generate candidates via OpportunityCandidateGenerator
  → validate via OpportunityValidator
  → rank via OpportunityRanker
  → produce OpportunityResult

The runtime does NOT:
- Write to CardState, TurnRecord, ActiveMemory, RAG
- Access SQLite/Store directly
- Delegate to sub-agents
- Generate player-visible final text
- Access environment variables, files, or network
"""

from __future__ import annotations

import uuid
import time
from datetime import datetime, timezone
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.delegation_plan import DelegationTask
from ..contracts.opportunity_request import OpportunityRequest
from ..contracts.opportunity_evidence import OpportunityEvidence
from ..contracts.opportunity_candidate import OpportunityCandidate
from ..contracts.opportunity_result import OpportunityResult, OpportunityStatus, RejectedCandidate
from ..contracts.opportunity_trigger_diagnostics import OpportunityTriggerDiagnostics
from ..contracts.opportunity_risk import OpportunityRisk, OpportunityRiskLevel
from .opportunity_trigger_policy import OpportunityTriggerResult
from .opportunity_query_planner import OpportunityQueryPlanner
from .opportunity_candidate_generator import OpportunityCandidateGenerator
from .opportunity_validator import OpportunityValidator
from .opportunity_ranker import OpportunityRanker


class OpportunityRuntime:
    """Orchestrates the Opportunity Agent execution.

    This runtime processes the trigger result and snapshot data to produce
    a structured OpportunityResult with candidates and recommendations.
    """

    def __init__(self):
        self.query_planner = OpportunityQueryPlanner()
        self.candidate_generator = OpportunityCandidateGenerator()
        self.validator = OpportunityValidator()
        self.ranker = OpportunityRanker()

    def run(
        self,
        snapshot: RoundSnapshot,
        task: DelegationTask,
        trigger_result: OpportunityTriggerResult,
        envelope: Any = None,
    ) -> OpportunityResult:
        """Run the Opportunity Agent.

        Args:
            snapshot: The current round snapshot
            task: The delegation task
            trigger_result: The trigger policy result
            envelope: Optional AgentTaskEnvelope (unused in fake mode)

        Returns:
            OpportunityResult with candidates and recommendations
        """
        now = datetime.now(timezone.utc).isoformat()
        start_time = time.time()
        result_id = f"opr_{uuid.uuid4().hex[:12]}"

        # If no trigger, return immediately
        if not trigger_result.should_trigger:
            return OpportunityResult(
                result_id=result_id,
                trace_id=snapshot.trace_id,
                snapshot_id=snapshot.snapshot_id,
                task_run_id=task.task_id,
                status=OpportunityStatus.NO_TRIGGER,
                created_at=now,
            )

        # Build request
        request = self._build_request(snapshot, task, trigger_result)

        # Collect evidence from snapshot data
        evidence = self._collect_evidence_from_snapshot(snapshot, trigger_result)

        # Generate candidates
        raw_candidates = self.candidate_generator.generate(
            snapshot=snapshot,
            trigger_result=trigger_result,
            evidence=evidence,
            max_candidates=request.max_candidates,
        )

        # Validate candidates
        valid_candidates, rejected_with_reasons = self.validator.validate_batch(
            raw_candidates, snapshot
        )

        # Build rejected candidate records
        rejected_candidates = []
        for candidate, errors in rejected_with_reasons:
            for error in errors:
                violated_policy = "unknown"
                if "证据" in error:
                    violated_policy = "missing_evidence"
                elif "事件断言" in error:
                    violated_policy = "event_assertion"
                elif "状态修改" in error:
                    violated_policy = "state_modification"
                elif "玩家代理权" in error:
                    violated_policy = "player_agency"
                elif "mustNotAssertAsFact" in error:
                    violated_policy = "assertion_violation"
                elif "MemoryCommit" in error:
                    violated_policy = "memory_commit"

                rejected_candidates.append(RejectedCandidate(
                    candidate_id=candidate.candidate_id,
                    reason=error,
                    violated_policy=violated_policy,
                    evidence_refs=candidate.evidence_refs,
                ))

        # Rank valid candidates
        accepted_candidates, outranked = self.ranker.rank(
            valid_candidates, max_accepted=trigger_result.max_opportunity_count
        )

        # Add outranked candidates to rejected
        for c in outranked:
            rejected_candidates.append(RejectedCandidate(
                candidate_id=c.candidate_id,
                reason="被更高优先级候选淘汰",
                violated_policy="outranked",
                evidence_refs=c.evidence_refs,
            ))

        # Determine status
        status = OpportunityStatus.SUCCESS
        degraded_reasons = []
        if not accepted_candidates and raw_candidates:
            status = OpportunityStatus.DEGRADED
            degraded_reasons.append("所有候选均被验证拒绝或淘汰")
        elif not accepted_candidates:
            status = OpportunityStatus.DEGRADED
            degraded_reasons.append("无有效候选")

        # Build recommended IDs
        recommended_ids = [c.candidate_id for c in accepted_candidates]

        duration_ms = int((time.time() - start_time) * 1000)

        # Build diagnostics
        diagnostics = OpportunityTriggerDiagnostics(
            diagnostics_id=f"od_{uuid.uuid4().hex[:8]}",
            trace_id=snapshot.trace_id,
            snapshot_id=snapshot.snapshot_id,
            task_run_id=task.task_id,
            should_trigger=trigger_result.should_trigger,
            trigger_reasons=trigger_result.trigger_reasons,
            opportunity_domains=trigger_result.opportunity_domains,
            focus_entities=trigger_result.focus_entities,
            risk_level=trigger_result.risk_level,
            max_opportunity_count=trigger_result.max_opportunity_count,
            tool_calls_made=0,  # No actual tool calls in snapshot mode
            candidates_generated=len(raw_candidates),
            candidates_accepted=len(accepted_candidates),
            candidates_rejected=len(rejected_candidates),
            total_duration_ms=duration_ms,
            degraded=(status == OpportunityStatus.DEGRADED),
            degraded_reasons=degraded_reasons,
            created_at=now,
        )

        # Build result
        result = OpportunityResult(
            result_id=result_id,
            trace_id=snapshot.trace_id,
            snapshot_id=snapshot.snapshot_id,
            task_run_id=task.task_id,
            status=status,
            candidates=accepted_candidates,
            rejected_candidates=rejected_candidates,
            degraded_reasons=degraded_reasons,
            recommended_opportunity_ids=recommended_ids,
            created_at=now,
        )

        return result

    def _build_request(
        self,
        snapshot: RoundSnapshot,
        task: DelegationTask,
        trigger_result: OpportunityTriggerResult,
    ) -> OpportunityRequest:
        """Build OpportunityRequest from trigger result."""
        return OpportunityRequest(
            request_id=f"opr_{uuid.uuid4().hex[:8]}",
            trace_id=snapshot.trace_id,
            snapshot_id=snapshot.snapshot_id,
            task_run_id=task.task_id,
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            focus_entities=trigger_result.focus_entities,
            focus_threads=[],
            focus_relationship_tensions=[],
            focus_scene_pressures=[],
            player_intent=snapshot.player_input[:100],
            max_candidates=5,
            required_evidence=True,
            must_not_create_facts=True,
            budget=task.max_tokens or 1000,
        )

    def _collect_evidence_from_snapshot(
        self,
        snapshot: RoundSnapshot,
        trigger_result: OpportunityTriggerResult,
    ) -> list[OpportunityEvidence]:
        """Collect evidence from snapshot data."""
        evidence: list[OpportunityEvidence] = []
        now = datetime.now(timezone.utc).isoformat()
        entities = set(trigger_result.focus_entities)

        # Evidence from accepted turns
        for i, turn in enumerate(snapshot.recent_turn_records):
            turn_text = turn.writer_output or ""
            ev = OpportunityEvidence(
                evidence_id=f"ev_turn_{turn.turn_id}",
                source_type="accepted_turn",
                source_ref=turn.turn_id,
                excerpt=turn_text[:200],
                entity_refs=list(entities)[:5],
                confidence=0.9,
                relevance_score=0.8,
                created_at=now,
            )
            evidence.append(ev)

        # Evidence from active memories
        for i, mem in enumerate(snapshot.active_memories):
            ev = OpportunityEvidence(
                evidence_id=f"ev_am_{mem.get('memory_id', i)}",
                source_type="active_memory",
                source_ref=mem.get("memory_id", ""),
                excerpt=mem.get("summary", ""),
                entity_refs=mem.get("entity_refs", []),
                confidence=mem.get("confidence", 0.7),
                relevance_score=mem.get("importance", 0.5),
                created_at=now,
            )
            evidence.append(ev)

        # Evidence from RAG recall
        for i, rag in enumerate(snapshot.rag_recall):
            ev = OpportunityEvidence(
                evidence_id=f"ev_rag_{rag.get('memory_id', i)}",
                source_type="rag_memory",
                source_ref=rag.get("memory_id", ""),
                excerpt=rag.get("summary", ""),
                entity_refs=rag.get("entity_refs", []),
                confidence=rag.get("confidence", 0.6),
                relevance_score=rag.get("importance", 0.4),
                created_at=now,
            )
            evidence.append(ev)

        # Evidence from worldbook
        for i, wb in enumerate(snapshot.active_worldbook_entries):
            ev = OpportunityEvidence(
                evidence_id=f"ev_wb_{i}",
                source_type="worldbook",
                source_ref=wb.get("title", f"wb_{i}"),
                excerpt=wb.get("content", "")[:200],
                confidence=0.5,
                relevance_score=0.3,
                created_at=now,
            )
            evidence.append(ev)

        return evidence
