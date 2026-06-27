"""MemoryPlanCompiler — compiles accepted candidates into MemoryCommitPlan.

Converts MemoryCurationCandidate objects into the MemoryCommitPlan format
that the existing ActiveMemoryCommitRuntime and RagMemoryCommitRuntime can
execute. The compiler is deterministic — no LLM involved.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..contracts.memory_commit_plan import MemoryCommitPlan
from ..contracts.memory_curation_candidate import (
    MemoryCurationCandidate, CurationTargetLayer, CurationOperation,
)
from ..contracts.memory_curation_result import MemoryCurationResult
from ..contracts.active_memory import ActiveMemoryRecord, ActiveMemoryKind
from ..contracts.rag_memory import RagMemoryRecord


class MemoryPlanCompiler:
    """Compiles MemoryCurationResult into MemoryCommitPlan.

    Deterministic. No LLM. Pure data transformation.
    """

    def compile(
        self,
        curation_result: MemoryCurationResult,
        turn_id: str,
        card_id: str,
        session_id: str,
        trace_id: str,
        expected_card_state_revision: int,
        quality_decision_ref: str,
    ) -> MemoryCommitPlan:
        """Compile curation result into a commit plan."""
        new_active: list[ActiveMemoryRecord] = []
        updated_active: list[ActiveMemoryRecord] = []
        resolved_active_ids: list[str] = []
        new_rag: list[RagMemoryRecord] = []
        write_reasons: list[str] = []

        for candidate in curation_result.accepted_candidates:
            if candidate.operation == CurationOperation.NO_OP:
                continue

            if candidate.target_layer == CurationTargetLayer.ACTIVE_MEMORY:
                self._compile_active_candidate(
                    candidate, turn_id, card_id, session_id,
                    expected_card_state_revision,
                    new_active, updated_active, resolved_active_ids, write_reasons,
                )
            elif candidate.target_layer == CurationTargetLayer.RAG_MEMORY:
                self._compile_rag_candidate(
                    candidate, turn_id, card_id, session_id,
                    expected_card_state_revision,
                    new_rag, write_reasons,
                )

        memory_commit_id = f"mc_{uuid.uuid4().hex[:12]}"
        idempotency_key = f"{turn_id}:{memory_commit_id}"

        return MemoryCommitPlan(
            turn_id=turn_id,
            card_id=card_id,
            session_id=session_id,
            trace_id=trace_id,
            expected_card_state_revision=expected_card_state_revision,
            memory_commit_id=memory_commit_id,
            idempotency_key=idempotency_key,
            quality_decision_ref=quality_decision_ref,
            new_active_entries=new_active,
            updated_active_entries=updated_active,
            resolved_active_ids=resolved_active_ids,
            new_rag_entries=new_rag,
            write_reasons=write_reasons,
        )

    def _compile_active_candidate(
        self,
        candidate: MemoryCurationCandidate,
        turn_id: str,
        card_id: str,
        session_id: str,
        revision: int,
        new_active: list,
        updated_active: list,
        resolved_ids: list,
        write_reasons: list,
    ) -> None:
        """Compile an active memory candidate."""
        if candidate.operation == CurationOperation.CREATE_ACTIVE:
            record = ActiveMemoryRecord(
                memory_id=f"am_{turn_id}_{candidate.candidate_id[:8]}",
                card_id=card_id,
                session_id=session_id,
                summary=candidate.summary,
                kind=candidate.tags[0] if candidate.tags else ActiveMemoryKind.SCENE_PRESSURE.value,
                entity_refs=list(candidate.entity_refs),
                source_turn_ids=[turn_id] + [t for t in candidate.source_turn_ids if t != turn_id],
                source_card_state_revision=revision,
                importance=candidate.importance,
                confidence=candidate.confidence,
                status="active",
            )
            new_active.append(record)
            write_reasons.append(candidate.reason or "curation_create_active")

        elif candidate.operation == CurationOperation.UPDATE_ACTIVE:
            # For updates, we create a record with the merge target ID
            if candidate.merge_target_memory_ids:
                target_id = candidate.merge_target_memory_ids[0]
                record = ActiveMemoryRecord(
                    memory_id=target_id,
                    card_id=card_id,
                    session_id=session_id,
                    summary=candidate.summary,
                    kind=candidate.tags[0] if candidate.tags else ActiveMemoryKind.SCENE_PRESSURE.value,
                    entity_refs=list(candidate.entity_refs),
                    source_turn_ids=[turn_id] + [t for t in candidate.source_turn_ids if t != turn_id],
                    source_card_state_revision=revision,
                    importance=candidate.importance,
                    confidence=candidate.confidence,
                    status="active",
                )
                updated_active.append(record)
                write_reasons.append(candidate.reason or "curation_update_active")

        elif candidate.operation == CurationOperation.MARK_RESOLVED:
            for mem_id in candidate.duplicate_of_memory_ids:
                if mem_id not in resolved_ids:
                    resolved_ids.append(mem_id)
            write_reasons.append(candidate.reason or "curation_resolve_active")

        elif candidate.operation == CurationOperation.MERGE_ACTIVE:
            # Merge = update the primary target with combined info
            if candidate.merge_target_memory_ids:
                target_id = candidate.merge_target_memory_ids[0]
                record = ActiveMemoryRecord(
                    memory_id=target_id,
                    card_id=card_id,
                    session_id=session_id,
                    summary=candidate.summary,
                    kind=candidate.tags[0] if candidate.tags else ActiveMemoryKind.SCENE_PRESSURE.value,
                    entity_refs=list(candidate.entity_refs),
                    source_turn_ids=[turn_id] + [t for t in candidate.source_turn_ids if t != turn_id],
                    source_card_state_revision=revision,
                    importance=candidate.importance,
                    confidence=candidate.confidence,
                    status="active",
                )
                updated_active.append(record)
                # Mark duplicates as resolved
                for mem_id in candidate.duplicate_of_memory_ids:
                    if mem_id != target_id and mem_id not in resolved_ids:
                        resolved_ids.append(mem_id)
                write_reasons.append(candidate.reason or "curation_merge_active")

        elif candidate.operation == CurationOperation.ARCHIVE_ACTIVE_TO_RAG:
            # Archive = resolve active + create RAG
            for mem_id in candidate.duplicate_of_memory_ids:
                if mem_id not in resolved_ids:
                    resolved_ids.append(mem_id)

            rag_record = RagMemoryRecord(
                memory_id=f"rag_archive_{turn_id}_{candidate.candidate_id[:8]}",
                card_id=card_id,
                session_id=session_id,
                scope="session",
                content=candidate.content or candidate.summary,
                summary=candidate.summary[:80],
                entity_refs=list(candidate.entity_refs),
                source_turn_ids=list(candidate.source_turn_ids),
                source_card_state_revision=revision,
                importance=candidate.importance,
                confidence=candidate.confidence,
                provenance=f"curation_archive:{turn_id}",
                evidence=[ev.source_turn_id for ev in candidate.evidence_refs],
            )
            new_rag.append(rag_record)
            write_reasons.append(candidate.reason or "curation_archive_to_rag")

    def _compile_rag_candidate(
        self,
        candidate: MemoryCurationCandidate,
        turn_id: str,
        card_id: str,
        session_id: str,
        revision: int,
        new_rag: list,
        write_reasons: list,
    ) -> None:
        """Compile a RAG memory candidate."""
        if candidate.operation == CurationOperation.CREATE_RAG:
            record = RagMemoryRecord(
                memory_id=f"rag_{turn_id}_{candidate.candidate_id[:8]}",
                card_id=card_id,
                session_id=session_id,
                scope="session",
                content=candidate.content or candidate.summary,
                summary=candidate.summary[:80],
                entity_refs=list(candidate.entity_refs),
                event_tags=[t for t in candidate.tags if t not in ("accepted_turn",)],
                source_turn_ids=[turn_id] + [t for t in candidate.source_turn_ids if t != turn_id],
                source_card_state_revision=revision,
                importance=candidate.importance,
                confidence=candidate.confidence,
                provenance=f"curation:{turn_id}",
                evidence=[ev.source_turn_id for ev in candidate.evidence_refs],
            )
            new_rag.append(record)
            write_reasons.append(candidate.reason or "curation_create_rag")
