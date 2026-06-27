"""MemoryCurationCandidate — a single memory operation proposed by the Curator.

schemaId: awp.rp.memory-curation-candidate.v1

Each candidate proposes one memory operation (create/update/merge/resolve/
demote/archive). Candidates are NOT writes — only MemoryCommitRuntime writes.
Candidates without accepted evidence are rejected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .memory_curation_evidence import MemoryCurationEvidence

SCHEMA_ID = "awp.rp.memory-curation-candidate.v1"
SCHEMA_VERSION = 1


# Target layers
class CurationTargetLayer:
    ACTIVE_MEMORY = "active_memory"
    RAG_MEMORY = "rag_memory"
    BOTH = "both"
    NONE = "none"


# Operation types
class CurationOperation:
    CREATE_ACTIVE = "create_active"
    UPDATE_ACTIVE = "update_active"
    MERGE_ACTIVE = "merge_active"
    MARK_RESOLVED = "mark_resolved"
    DEMOTE_ACTIVE = "demote_active"
    ARCHIVE_ACTIVE_TO_RAG = "archive_active_to_rag"
    CREATE_RAG = "create_rag"
    UPDATE_RAG = "update_rag"
    MARK_RAG_STALE = "mark_rag_stale"
    NO_OP = "no_op"


@dataclass(frozen=True)
class MemoryCurationCandidate:
    """A single proposed memory operation from the Memory Curator."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    candidate_id: str = ""
    trace_id: str = ""
    turn_id: str = ""

    # Operation
    target_layer: str = CurationTargetLayer.NONE
    operation: str = CurationOperation.NO_OP

    # Content (for create/update operations)
    summary: str = ""           # 30-80 chars for active memory
    content: str = ""           # longer content for RAG memory

    # Evidence binding (at least one required)
    foundation_facts: list[str] = field(default_factory=list)
    evidence_refs: list[MemoryCurationEvidence] = field(default_factory=list)
    source_turn_ids: list[str] = field(default_factory=list)

    # Entity / tag binding
    entity_refs: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # Ranking
    importance: float = 0.5
    confidence: float = 0.5

    # Lifecycle
    resolution_status: str = ""   # for mark_resolved / mark_rag_stale

    # Merge / dedup targets
    duplicate_of_memory_ids: list[str] = field(default_factory=list)
    merge_target_memory_ids: list[str] = field(default_factory=list)

    # Provenance
    reason: str = ""

    # Hard prohibitions
    must_not_assert_unsupported_fact: bool = True
    must_not_write_storage: bool = True

    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "target_layer": self.target_layer,
            "operation": self.operation,
            "summary": self.summary,
            "content": self.content,
            "foundation_facts": list(self.foundation_facts),
            "evidence_refs": [e.to_dict() for e in self.evidence_refs],
            "source_turn_ids": list(self.source_turn_ids),
            "entity_refs": list(self.entity_refs),
            "tags": list(self.tags),
            "importance": self.importance,
            "confidence": self.confidence,
            "resolution_status": self.resolution_status,
            "duplicate_of_memory_ids": list(self.duplicate_of_memory_ids),
            "merge_target_memory_ids": list(self.merge_target_memory_ids),
            "reason": self.reason,
            "must_not_assert_unsupported_fact": self.must_not_assert_unsupported_fact,
            "must_not_write_storage": self.must_not_write_storage,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryCurationCandidate:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            candidate_id=data.get("candidate_id", ""),
            trace_id=data.get("trace_id", ""),
            turn_id=data.get("turn_id", ""),
            target_layer=data.get("target_layer", CurationTargetLayer.NONE),
            operation=data.get("operation", CurationOperation.NO_OP),
            summary=data.get("summary", ""),
            content=data.get("content", ""),
            foundation_facts=list(data.get("foundation_facts", [])),
            evidence_refs=[
                MemoryCurationEvidence.from_dict(e) for e in data.get("evidence_refs", [])
            ],
            source_turn_ids=list(data.get("source_turn_ids", [])),
            entity_refs=list(data.get("entity_refs", [])),
            tags=list(data.get("tags", [])),
            importance=data.get("importance", 0.5),
            confidence=data.get("confidence", 0.5),
            resolution_status=data.get("resolution_status", ""),
            duplicate_of_memory_ids=list(data.get("duplicate_of_memory_ids", [])),
            merge_target_memory_ids=list(data.get("merge_target_memory_ids", [])),
            reason=data.get("reason", ""),
            must_not_assert_unsupported_fact=data.get("must_not_assert_unsupported_fact", True),
            must_not_write_storage=data.get("must_not_write_storage", True),
            created_at=data.get("created_at", ""),
        )
