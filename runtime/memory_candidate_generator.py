"""MemoryCandidateGenerator — generates memory curation candidates.

Two implementations:
  - FakeMemoryCandidateGenerator: deterministic, no LLM
  - Real LLM adapter: future work

The generator reads accepted facts and proposes candidates. It NEVER writes
to stores. It NEVER creates facts. It NEVER asserts unsupported claims.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from ..contracts.memory_curation_request import MemoryCurationRequest
from ..contracts.memory_curation_candidate import (
    MemoryCurationCandidate, CurationTargetLayer, CurationOperation,
)
from ..contracts.memory_curation_evidence import MemoryCurationEvidence
from ..contracts.active_memory import ActiveMemoryKind
from .memory_curation_query_planner import CurationQueryPlan


class MemoryCandidateGeneratorAdapter(Protocol):
    """Protocol for LLM-based candidate generation (future work)."""
    def generate(
        self, request: MemoryCurationRequest, plan: CurationQueryPlan,
    ) -> list[MemoryCurationCandidate]:
        ...


class FakeMemoryCandidateGenerator:
    """Deterministic candidate generator (M1 / D6 fake mode).

    Produces candidates from accepted turn data using simple rules:
    1. Create a RAG record from the accepted turn
    2. Check if any active memories should be updated/resolved
    3. Create an active memory if the turn has long-term significance

    No LLM involved. No novel prose. Source-bound only.
    """

    def generate(
        self,
        request: MemoryCurationRequest,
        plan: CurationQueryPlan,
    ) -> list[MemoryCurationCandidate]:
        """Generate deterministic candidates from accepted turn data."""
        candidates: list[MemoryCurationCandidate] = []

        # 1. Always create a RAG record for the accepted turn
        rag_candidate = self._create_rag_candidate(request)
        if rag_candidate:
            candidates.append(rag_candidate)

        # 2. Check active memories for potential updates/resolution
        update_candidates = self._check_active_memory_updates(request, plan)
        candidates.extend(update_candidates)

        # 3. Create active memory if turn has significant signals
        active_candidate = self._create_active_candidate(request, plan)
        if active_candidate:
            candidates.append(active_candidate)

        return candidates

    def _create_rag_candidate(
        self, request: MemoryCurationRequest,
    ) -> MemoryCurationCandidate | None:
        """Create a RAG candidate from the accepted turn."""
        if not request.accepted_output:
            return None

        summary = request.accepted_output[:80]
        evidence = MemoryCurationEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:8]}",
            source_turn_id=request.turn_id,
            source_card_state_revision=0,
            evidence_type="accepted_turn",
            quote=summary[:40],
            relevance=0.8,
        )

        return MemoryCurationCandidate(
            candidate_id=f"cand_rag_{uuid.uuid4().hex[:8]}",
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            target_layer=CurationTargetLayer.RAG_MEMORY,
            operation=CurationOperation.CREATE_RAG,
            summary=summary,
            content=request.accepted_output,
            foundation_facts=[f"accepted_turn:{request.turn_id}"],
            evidence_refs=[evidence],
            source_turn_ids=[request.turn_id],
            entity_refs=[],
            tags=["accepted_turn"],
            importance=0.5,
            confidence=0.7,
            reason="accepted_turn_long_term_record",
        )

    def _check_active_memory_updates(
        self,
        request: MemoryCurationRequest,
        plan: CurationQueryPlan,
    ) -> list[MemoryCurationCandidate]:
        """Check if existing active memories should be updated/resolved."""
        candidates: list[MemoryCurationCandidate] = []
        accepted_output = request.accepted_output or ""

        for mem in request.active_memory_snapshot:
            mem_id = mem.get("memory_id", "")
            mem_kind = mem.get("kind", "")
            mem_status = mem.get("status", "")
            mem_summary = mem.get("summary", "")
            entity_refs = mem.get("entity_refs", [])

            if mem_status != "active":
                continue

            # Check if the accepted output resolves this memory
            # Simple heuristic: if key entities appear in the output
            entity_match = any(e in accepted_output for e in entity_refs)

            if entity_match and mem_kind in ("promise", "misunderstanding", "secret"):
                # This turn may have advanced/resolved this memory
                evidence = MemoryCurationEvidence(
                    evidence_id=f"ev_{uuid.uuid4().hex[:8]}",
                    source_turn_id=request.turn_id,
                    evidence_type="accepted_turn",
                    quote=accepted_output[:40],
                    relevance=0.7,
                )

                # If the turn explicitly resolves the promise/secret
                resolution_keywords = ["兑现", "完成", "实现", "揭露", "真相", "公开"]
                is_resolution = any(kw in accepted_output for kw in resolution_keywords)

                if is_resolution:
                    candidates.append(MemoryCurationCandidate(
                        candidate_id=f"cand_resolve_{uuid.uuid4().hex[:8]}",
                        trace_id=request.trace_id,
                        turn_id=request.turn_id,
                        target_layer=CurationTargetLayer.ACTIVE_MEMORY,
                        operation=CurationOperation.MARK_RESOLVED,
                        foundation_facts=[f"accepted_turn:{request.turn_id}"],
                        evidence_refs=[evidence],
                        source_turn_ids=[request.turn_id],
                        entity_refs=entity_refs,
                        resolution_status="resolved",
                        duplicate_of_memory_ids=[mem_id],
                        reason=f"turn_resolves_{mem_kind}",
                    ))
                else:
                    # Update the memory with new turn reference
                    candidates.append(MemoryCurationCandidate(
                        candidate_id=f"cand_update_{uuid.uuid4().hex[:8]}",
                        trace_id=request.trace_id,
                        turn_id=request.turn_id,
                        target_layer=CurationTargetLayer.ACTIVE_MEMORY,
                        operation=CurationOperation.UPDATE_ACTIVE,
                        summary=mem_summary,
                        foundation_facts=[f"accepted_turn:{request.turn_id}"],
                        evidence_refs=[evidence],
                        source_turn_ids=[request.turn_id],
                        entity_refs=entity_refs,
                        merge_target_memory_ids=[mem_id],
                        reason=f"turn_advances_{mem_kind}",
                    ))

        return candidates

    def _create_active_candidate(
        self,
        request: MemoryCurationRequest,
        plan: CurationQueryPlan,
    ) -> MemoryCurationCandidate | None:
        """Create an active memory candidate if the turn has long-term significance."""
        accepted_output = request.accepted_output or ""
        if not accepted_output:
            return None

        # Determine the kind based on domains
        kind = ActiveMemoryKind.SCENE_PRESSURE.value
        importance = 0.5
        if "promise" in plan.domains:
            kind = ActiveMemoryKind.PROMISE.value
            importance = 0.7
        elif "secret" in plan.domains:
            kind = ActiveMemoryKind.SECRET.value
            importance = 0.8
        elif "relationship" in plan.domains:
            kind = ActiveMemoryKind.RELATIONSHIP_SHIFT.value
            importance = 0.7
        elif "goal" in plan.domains:
            kind = ActiveMemoryKind.PLAYER_GOAL.value
            importance = 0.6
        elif "longterm_impact" in plan.domains:
            kind = ActiveMemoryKind.UNRESOLVED_THREAD.value
            importance = 0.6

        # Only create if we have a meaningful domain signal
        if not plan.domains:
            return None

        summary = accepted_output[:80]
        evidence = MemoryCurationEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:8]}",
            source_turn_id=request.turn_id,
            evidence_type="accepted_turn",
            quote=summary[:40],
            relevance=0.7,
        )

        return MemoryCurationCandidate(
            candidate_id=f"cand_active_{uuid.uuid4().hex[:8]}",
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            target_layer=CurationTargetLayer.ACTIVE_MEMORY,
            operation=CurationOperation.CREATE_ACTIVE,
            summary=summary,
            foundation_facts=[f"accepted_turn:{request.turn_id}"],
            evidence_refs=[evidence],
            source_turn_ids=[request.turn_id],
            entity_refs=plan.focus_entities[:5],
            tags=[kind],
            importance=importance,
            confidence=0.6,
            reason=f"long_term_signal:{kind}",
        )
