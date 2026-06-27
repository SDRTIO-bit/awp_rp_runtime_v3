"""OpportunityCandidateGenerator — generates opportunity candidates from evidence.

This is the Fake Adapter for V1. It generates deterministic candidates
from snapshot data and evidence. A future LLM Adapter can replace this.

Opportunity ≠ Event. All candidates must:
- Be grounded in existing evidence
- Not assert facts as having already happened
- Not modify state or advance timeline
- Not override player agency
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.opportunity_candidate import (
    OpportunityCandidate, OpportunityKind, NarrativeFunction,
)
from ..contracts.opportunity_evidence import OpportunityEvidence
from .opportunity_trigger_policy import OpportunityTriggerResult


class OpportunityCandidateGenerator:
    """Generates opportunity candidates from snapshot data and evidence.

    Fake Adapter mode: deterministic generation from snapshot data.
    Future: LLM Adapter can generate richer candidates.
    """

    def generate(
        self,
        snapshot: RoundSnapshot,
        trigger_result: OpportunityTriggerResult,
        evidence: list[OpportunityEvidence],
        max_candidates: int = 5,
    ) -> list[OpportunityCandidate]:
        """Generate opportunity candidates from evidence.

        Returns list of candidates, each grounded in evidence.
        """
        now = datetime.now(timezone.utc).isoformat()
        candidates: list[OpportunityCandidate] = []

        # Strategy 1: Promise/commitment pressure from active memories
        for mem in snapshot.active_memories:
            if mem.get("kind") == "promise" and len(candidates) < max_candidates:
                ev_refs = [ev.evidence_id for ev in evidence
                           if ev.source_ref == mem.get("memory_id")]
                candidates.append(OpportunityCandidate(
                    candidate_id=f"oc_{uuid.uuid4().hex[:8]}",
                    trace_id=snapshot.trace_id,
                    snapshot_id=snapshot.snapshot_id,
                    kind=OpportunityKind.PROMISE_PRESSURE,
                    title=f"未兑现承诺: {mem.get('summary', '')[:50]}",
                    summary=f"基于活跃记忆中的承诺记录，角色可能在对话中表现出迟疑或提醒",
                    narrative_function=NarrativeFunction.INCREASE_TENSION,
                    focus_entities=mem.get("entity_refs", []),
                    foundation_facts=[mem.get("summary", "")],
                    evidence_refs=ev_refs,
                    activation_conditions=["角色提及承诺相关话题", "玩家追问承诺"],
                    player_agency_risk=0.1,
                    continuity_risk=0.2,
                    novelty_score=0.6,
                    relevance_score=0.8,
                    confidence=mem.get("confidence", 0.7),
                    suggested_writer_use="角色可自然表现出对承诺的迟疑或内疚",
                    suggested_director_use="可作为对话节奏的张力增强点",
                    must_not_assert_as_fact=True,
                    created_at=now,
                ))

        # Strategy 2: Secret/misunderstanding pressure from RAG
        for rag in snapshot.rag_recall:
            kind = rag.get("kind", "")
            if kind in ("secret", "misunderstanding") and len(candidates) < max_candidates:
                ev_refs = [ev.evidence_id for ev in evidence
                           if ev.source_ref == rag.get("memory_id")]
                opp_kind = (OpportunityKind.SECRET_PRESSURE if kind == "secret"
                            else OpportunityKind.MISUNDERSTANDING_PRESSURE)
                candidates.append(OpportunityCandidate(
                    candidate_id=f"oc_{uuid.uuid4().hex[:8]}",
                    trace_id=snapshot.trace_id,
                    snapshot_id=snapshot.snapshot_id,
                    kind=opp_kind,
                    title=f"{kind}: {rag.get('summary', '')[:50]}",
                    summary=f"基于RAG记忆中的{kind}记录，可让角色反应更微妙",
                    narrative_function=NarrativeFunction.CREATE_EMOTIONAL_SUBTEXT,
                    focus_entities=rag.get("entity_refs", []),
                    foundation_facts=[rag.get("summary", "")],
                    evidence_refs=ev_refs,
                    activation_conditions=["对话涉及相关话题", "角色间互动"],
                    player_agency_risk=0.2,
                    continuity_risk=0.3,
                    novelty_score=0.7,
                    relevance_score=0.7,
                    confidence=rag.get("confidence", 0.6),
                    suggested_writer_use="角色反应可带有隐藏的情感层次",
                    suggested_director_use="可作为伏笔回收的自然入口",
                    must_not_assert_as_fact=True,
                    created_at=now,
                ))

        # Strategy 3: Unresolved threads from DirectorPlan
        for thread in snapshot.active_worldbook_entries:
            if len(candidates) >= max_candidates:
                break
            content = thread.get("content", "")
            if any(kw in content for kw in ["伏笔", "悬念", "暗示", "线索"]):
                candidates.append(OpportunityCandidate(
                    candidate_id=f"oc_{uuid.uuid4().hex[:8]}",
                    trace_id=snapshot.trace_id,
                    snapshot_id=snapshot.snapshot_id,
                    kind=OpportunityKind.FORESHADOWING_ECHO,
                    title=f"伏笔回声: {thread.get('title', '')[:50]}",
                    summary="基于世界书中的伏笔记录，可在本回合自然提及",
                    narrative_function=NarrativeFunction.PREPARE_FUTURE_HOOK,
                    focus_entities=[],
                    foundation_facts=[content[:200]],
                    evidence_refs=[f"worldbook:{thread.get('title', '')}"],
                    activation_conditions=["对话自然涉及相关话题"],
                    player_agency_risk=0.1,
                    continuity_risk=0.1,
                    novelty_score=0.5,
                    relevance_score=0.6,
                    confidence=0.5,
                    suggested_writer_use="可作为背景细节自然提及",
                    suggested_director_use="可作为未来剧情的铺垫",
                    must_not_assert_as_fact=True,
                    created_at=now,
                ))

        # Strategy 4: Relationship tension from DirectorPlan
        if "relationship_tension" in trigger_result.opportunity_domains:
            for tension in snapshot.active_memories:
                if tension.get("kind") == "relationship" and len(candidates) < max_candidates:
                    ev_refs = [ev.evidence_id for ev in evidence
                               if ev.source_ref == tension.get("memory_id")]
                    candidates.append(OpportunityCandidate(
                        candidate_id=f"oc_{uuid.uuid4().hex[:8]}",
                        trace_id=snapshot.trace_id,
                        snapshot_id=snapshot.snapshot_id,
                        kind=OpportunityKind.RELATIONSHIP_TENSION,
                        title=f"关系张力: {tension.get('summary', '')[:50]}",
                        summary="基于关系记忆，人物反应可更微妙",
                        narrative_function=NarrativeFunction.DEEPEN_CHARACTERIZATION,
                        focus_entities=tension.get("entity_refs", []),
                        foundation_facts=[tension.get("summary", "")],
                        evidence_refs=ev_refs,
                        activation_conditions=["角色间互动", "涉及关系话题"],
                        player_agency_risk=0.15,
                        continuity_risk=0.2,
                        novelty_score=0.6,
                        relevance_score=0.7,
                        confidence=tension.get("confidence", 0.7),
                        suggested_writer_use="角色反应可带有关系历史的微妙影响",
                        suggested_director_use="可作为关系发展的自然推进点",
                        must_not_assert_as_fact=True,
                        created_at=now,
                    ))

        # Strategy 5: Goal reactivation from active memories
        for mem in snapshot.active_memories:
            if mem.get("kind") == "goal" and len(candidates) < max_candidates:
                ev_refs = [ev.evidence_id for ev in evidence
                           if ev.source_ref == mem.get("memory_id")]
                candidates.append(OpportunityCandidate(
                    candidate_id=f"oc_{uuid.uuid4().hex[:8]}",
                    trace_id=snapshot.trace_id,
                    snapshot_id=snapshot.snapshot_id,
                    kind=OpportunityKind.GOAL_REACTIVATION,
                    title=f"目标重激活: {mem.get('summary', '')[:50]}",
                    summary="基于长期目标记忆，可在本回合自然提起",
                    narrative_function=NarrativeFunction.CREATE_CHOICE_SPACE,
                    focus_entities=mem.get("entity_refs", []),
                    foundation_facts=[mem.get("summary", "")],
                    evidence_refs=ev_refs,
                    activation_conditions=["对话自然涉及目标", "玩家表达方向"],
                    player_agency_risk=0.1,
                    continuity_risk=0.1,
                    novelty_score=0.5,
                    relevance_score=0.7,
                    confidence=mem.get("confidence", 0.7),
                    suggested_writer_use="可自然提起长期目标，留下选择空间",
                    suggested_director_use="可作为决策空间的自然扩展",
                    must_not_assert_as_fact=True,
                    created_at=now,
                ))

        return candidates[:max_candidates]
