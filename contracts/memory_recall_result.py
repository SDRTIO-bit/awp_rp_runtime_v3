"""MemoryRecallResult — deterministically-ordered recall hits with diagnostics.

schemaId: awp.rp.memory-recall-result.v1

Each hit carries: score, hit reason(s), sourceRefs, provenance, and a stale /
conflicted flag. Hits conflicting with CardState are downgraded or ignored by
the MemoryContextAssembler (never by free LLM judgement).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .memory_recall_request import MemoryRecallRequest

SCHEMA_ID = "awp.rp.memory-recall-result.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class RecallHit:
    """A single recall hit."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    memory_id: str = ""
    layer: str = ""  # "active" | "rag"
    score: float = 0.0
    hit_reasons: list[str] = field(default_factory=list)  # why it matched
    source_refs: list[str] = field(default_factory=list)  # source_turn_ids
    provenance: str = ""
    importance: float = 0.0
    confidence: float = 0.0
    status: str = "active"
    summary: str = ""
    content: str = ""
    entity_refs: list[str] = field(default_factory=list)

    # Conflict diagnostics (filled by assembler, not by free recall)
    conflict_status: str = ""  # "" | "stale" | "conflicted" | "ignored"
    conflict_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "memory_id": self.memory_id,
            "layer": self.layer,
            "score": self.score,
            "hit_reasons": list(self.hit_reasons),
            "source_refs": list(self.source_refs),
            "provenance": self.provenance,
            "importance": self.importance,
            "confidence": self.confidence,
            "status": self.status,
            "summary": self.summary,
            "content": self.content,
            "entity_refs": list(self.entity_refs),
            "conflict_status": self.conflict_status,
            "conflict_reason": self.conflict_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecallHit:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            memory_id=data.get("memory_id", ""),
            layer=data.get("layer", ""),
            score=data.get("score", 0.0),
            hit_reasons=list(data.get("hit_reasons", [])),
            source_refs=list(data.get("source_refs", [])),
            provenance=data.get("provenance", ""),
            importance=data.get("importance", 0.0),
            confidence=data.get("confidence", 0.0),
            status=data.get("status", "active"),
            summary=data.get("summary", ""),
            content=data.get("content", ""),
            entity_refs=list(data.get("entity_refs", [])),
            conflict_status=data.get("conflict_status", ""),
            conflict_reason=data.get("conflict_reason", ""),
        )


@dataclass(frozen=True)
class MemoryRecallResult:
    """Result of a recall request, with diagnostics."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    request: MemoryRecallRequest = field(default_factory=MemoryRecallRequest)
    hits: list[RecallHit] = field(default_factory=list)
    excluded: list[dict[str, Any]] = field(default_factory=list)
    # excluded entries: {"memory_id":..., "reason":"stale|filtered|scope_mismatch|..."}
    ordered_by: str = ""  # deterministic ordering description
    total_available: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "request": self.request.to_dict(),
            "hits": [h.to_dict() for h in self.hits],
            "excluded": list(self.excluded),
            "ordered_by": self.ordered_by,
            "total_available": self.total_available,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryRecallResult:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            request=MemoryRecallRequest.from_dict(data.get("request", {})),
            hits=[RecallHit.from_dict(h) for h in data.get("hits", [])],
            excluded=list(data.get("excluded", [])),
            ordered_by=data.get("ordered_by", ""),
            total_available=data.get("total_available", 0),
        )
