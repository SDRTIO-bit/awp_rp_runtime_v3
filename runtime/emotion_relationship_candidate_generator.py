"""EmotionRelationshipCandidateGenerator — generates emotion/relationship candidates from evidence.

This is the Fake Adapter for V1. It generates deterministic candidates
from snapshot data and evidence. A future LLM Adapter can replace this.

Emotion/Relationship Candidate = based on existing facts, captures a specific
relational dynamic or emotional undercurrent detected in the narrative context.

It CANNOT:
- Assert facts as having happened
- Modify relationships or state
- Override player agency
- Auto-advance relationship arcs
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.emotion_relationship_candidate import (
    EmotionRelationshipCandidate, RelationshipKind,
)
from ..contracts.relationship_evidence import RelationshipEvidence
from .emotion_relationship_trigger_policy import EmotionRelationshipTriggerResult


class EmotionRelationshipCandidateGenerator:
    """Generates emotion/relationship candidates from snapshot data and evidence.

    Fake Adapter mode: deterministic generation from snapshot data.
    Future: LLM Adapter can generate richer candidates.
    """

    def generate(
        self,
        snapshot: RoundSnapshot,
        trigger_result: EmotionRelationshipTriggerResult,
        evidence: list[RelationshipEvidence],
        max_candidates: int = 5,
    ) -> list[EmotionRelationshipCandidate]:
        """Generate emotion/relationship candidates from evidence.

        Returns list of candidates, each grounded in evidence.
        All candidates have must_not_assert_as_fact=True and must_not_modify_relationship=True.
        """
        now = datetime.now(timezone.utc).isoformat()
        candidates: list[EmotionRelationshipCandidate] = []

        # Strategy 1: trust_tension from relationship_shift memories
        for mem in snapshot.active_memories:
            if mem.get("kind") == "relationship_shift" and len(candidates) < max_candidates:
                ev_refs = [ev.evidence_id for ev in evidence
                           if ev.source_ref == mem.get("memory_id")]
                candidates.append(EmotionRelationshipCandidate(
                    candidate_id=f"erc_{uuid.uuid4().hex[:8]}",
                    trace_id=snapshot.trace_id,
                    snapshot_id=snapshot.snapshot_id,
                    kind=RelationshipKind.TRUST_TENSION,
                    summary=f"信任张力: {mem.get('summary', '')[:80]}",
                    focus_entities=mem.get("entity_refs", []),
                    relationship_state_interpretation="基于关系变化记忆，角色间可能存在未解决的信任问题",
                    emotional_signals=["迟疑", "回避", "防备"],
                    foundation_facts=[mem.get("summary", "")],
                    evidence_refs=ev_refs,
                    confidence=mem.get("confidence", 0.7),
                    player_agency_risk=0.1,
                    continuity_risk=0.2,
                    sudden_shift_risk=0.1,
                    suggested_writer_use="角色反应可带有微妙的不信任或试探",
                    suggested_director_use="可作为信任重建的自然线索",
                    must_not_assert_as_fact=True,
                    must_not_modify_relationship=True,
                    created_at=now,
                ))

        # Strategy 2: emotional_residue from promise memories
        for mem in snapshot.active_memories:
            if mem.get("kind") == "promise" and len(candidates) < max_candidates:
                ev_refs = [ev.evidence_id for ev in evidence
                           if ev.source_ref == mem.get("memory_id")]
                candidates.append(EmotionRelationshipCandidate(
                    candidate_id=f"erc_{uuid.uuid4().hex[:8]}",
                    trace_id=snapshot.trace_id,
                    snapshot_id=snapshot.snapshot_id,
                    kind=RelationshipKind.EMOTIONAL_RESIDUE,
                    summary=f"情感残留: {mem.get('summary', '')[:80]}",
                    focus_entities=mem.get("entity_refs", []),
                    relationship_state_interpretation="基于未兑现承诺，角色可能带有内疚或期待的微妙情感",
                    emotional_signals=["犹豫", "欲言又止", "心虚"],
                    foundation_facts=[mem.get("summary", "")],
                    evidence_refs=ev_refs,
                    confidence=mem.get("confidence", 0.7),
                    player_agency_risk=0.1,
                    continuity_risk=0.2,
                    sudden_shift_risk=0.1,
                    suggested_writer_use="角色可自然表现出对承诺的迟疑或内疚感",
                    suggested_director_use="可作为情感张力的自然增强点",
                    must_not_assert_as_fact=True,
                    must_not_modify_relationship=True,
                    created_at=now,
                ))

        # Strategy 3: misunderstanding_signal from RAG memories
        for rag in snapshot.rag_recall:
            kind = rag.get("kind", "")
            if kind == "misunderstanding" and len(candidates) < max_candidates:
                ev_refs = [ev.evidence_id for ev in evidence
                           if ev.source_ref == rag.get("memory_id")]
                candidates.append(EmotionRelationshipCandidate(
                    candidate_id=f"erc_{uuid.uuid4().hex[:8]}",
                    trace_id=snapshot.trace_id,
                    snapshot_id=snapshot.snapshot_id,
                    kind=RelationshipKind.MISUNDERSTANDING_SIGNAL,
                    summary=f"误会信号: {rag.get('summary', '')[:80]}",
                    focus_entities=rag.get("entity_refs", []),
                    relationship_state_interpretation="基于RAG中的误会记录，角色反应可能带有隐藏的误解",
                    emotional_signals=["委屈", "纠结", "沉默"],
                    foundation_facts=[rag.get("summary", "")],
                    evidence_refs=ev_refs,
                    confidence=rag.get("confidence", 0.6),
                    player_agency_risk=0.2,
                    continuity_risk=0.3,
                    sudden_shift_risk=0.2,
                    suggested_writer_use="角色反应可带有未消解的误会色彩",
                    suggested_director_use="可作为误会揭示的自然伏笔",
                    must_not_assert_as_fact=True,
                    must_not_modify_relationship=True,
                    created_at=now,
                ))

        # Strategy 4: guardedness from secret memories
        for rag in snapshot.rag_recall:
            kind = rag.get("kind", "")
            if kind == "secret" and len(candidates) < max_candidates:
                ev_refs = [ev.evidence_id for ev in evidence
                           if ev.source_ref == rag.get("memory_id")]
                candidates.append(EmotionRelationshipCandidate(
                    candidate_id=f"erc_{uuid.uuid4().hex[:8]}",
                    trace_id=snapshot.trace_id,
                    snapshot_id=snapshot.snapshot_id,
                    kind=RelationshipKind.GUARDEDNESS,
                    summary=f"防备心理: {rag.get('summary', '')[:80]}",
                    focus_entities=rag.get("entity_refs", []),
                    relationship_state_interpretation="基于秘密记忆，角色可能表现出防备或回避",
                    emotional_signals=["防备", "回避", "心虚"],
                    foundation_facts=[rag.get("summary", "")],
                    evidence_refs=ev_refs,
                    confidence=rag.get("confidence", 0.6),
                    player_agency_risk=0.15,
                    continuity_risk=0.2,
                    sudden_shift_risk=0.15,
                    suggested_writer_use="角色的言语或行为可带有微妙的防备感",
                    suggested_director_use="可作为秘密压力的自然体现",
                    must_not_assert_as_fact=True,
                    must_not_modify_relationship=True,
                    created_at=now,
                ))

        # Strategy 5: relationship_boundary from Director tensions
        if "relationship_tension" in trigger_result.emotion_relationship_domains:
            for tension in snapshot.active_memories:
                if tension.get("kind") == "relationship" and len(candidates) < max_candidates:
                    ev_refs = [ev.evidence_id for ev in evidence
                               if ev.source_ref == tension.get("memory_id")]
                    candidates.append(EmotionRelationshipCandidate(
                        candidate_id=f"erc_{uuid.uuid4().hex[:8]}",
                        trace_id=snapshot.trace_id,
                        snapshot_id=snapshot.snapshot_id,
                        kind=RelationshipKind.RELATIONSHIP_BOUNDARY,
                        summary=f"关系边界: {tension.get('summary', '')[:80]}",
                        focus_entities=tension.get("entity_refs", []),
                        relationship_state_interpretation="基于关系张力记忆，角色间存在需要尊重的边界",
                        emotional_signals=["紧张", "不安", "犹豫"],
                        foundation_facts=[tension.get("summary", "")],
                        evidence_refs=ev_refs,
                        confidence=tension.get("confidence", 0.7),
                        player_agency_risk=0.15,
                        continuity_risk=0.2,
                        sudden_shift_risk=0.2,
                        suggested_writer_use="角色互动应自然体现对边界的微妙感知",
                        suggested_director_use="可作为关系发展的安全引导",
                        must_not_assert_as_fact=True,
                        must_not_modify_relationship=True,
                        created_at=now,
                    ))

        # Strategy 6: subtext_opportunity from recent turn emotion signals
        if "emotion_signal" in trigger_result.emotion_relationship_domains:
            for turn in snapshot.recent_turn_records[:2]:
                if len(candidates) >= max_candidates:
                    break
                turn_text = turn.writer_output or ""
                if any(kw in turn_text for kw in ["沉默", "叹气", "犹豫", "欲言又止", "紧张"]):
                    ev_refs = [f"turn:{turn.turn_id}"]
                    candidates.append(EmotionRelationshipCandidate(
                        candidate_id=f"erc_{uuid.uuid4().hex[:8]}",
                        trace_id=snapshot.trace_id,
                        snapshot_id=snapshot.snapshot_id,
                        kind=RelationshipKind.SUBTEXT_OPPORTUNITY,
                        summary=f"潜台词机会: 近期对话中检测到情感信号",
                        focus_entities=[],
                        relationship_state_interpretation="近期对话中存在未言明的情感层次",
                        emotional_signals=["沉默", "叹气", "欲言又止"],
                        foundation_facts=[turn_text[:200]],
                        evidence_refs=ev_refs,
                        confidence=0.6,
                        player_agency_risk=0.1,
                        continuity_risk=0.1,
                        sudden_shift_risk=0.1,
                        suggested_writer_use="可在回复中自然体现角色未言明的情感层次",
                        suggested_director_use="可作为情感深度的自然引导",
                        must_not_assert_as_fact=True,
                        must_not_modify_relationship=True,
                        created_at=now,
                    ))

        return candidates[:max_candidates]
