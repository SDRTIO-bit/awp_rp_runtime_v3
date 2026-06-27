"""MemoryCurationResult — final output of the Memory Curator Agent.

schemaId: awp.rp.memory-curation-result.v1

Contains accepted candidates (to be compiled into MemoryCommitPlan) and
rejected candidates (with reasons). The Curator NEVER writes to stores
directly — only the MemoryCommitRuntime may write.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .memory_curation_candidate import MemoryCurationCandidate

SCHEMA_ID = "awp.rp.memory-curation-result.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MemoryCurationResult:
    """Final output of the Memory Curator Agent."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    result_id: str = ""
    trace_id: str = ""
    turn_id: str = ""
    card_id: str = ""
    session_id: str = ""

    # Candidates
    accepted_candidates: list[MemoryCurationCandidate] = field(default_factory=list)
    rejected_candidates: list[MemoryCurationCandidate] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)

    # Degradation
    degraded: bool = False
    degraded_reasons: list[str] = field(default_factory=list)

    # Diagnostics
    total_candidates_generated: int = 0
    total_candidates_accepted: int = 0
    total_candidates_rejected: int = 0
    active_memory_count_before: int = 0
    active_memory_count_after: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "result_id": self.result_id,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "accepted_candidates": [c.to_dict() for c in self.accepted_candidates],
            "rejected_candidates": [c.to_dict() for c in self.rejected_candidates],
            "rejection_reasons": list(self.rejection_reasons),
            "degraded": self.degraded,
            "degraded_reasons": list(self.degraded_reasons),
            "total_candidates_generated": self.total_candidates_generated,
            "total_candidates_accepted": self.total_candidates_accepted,
            "total_candidates_rejected": self.total_candidates_rejected,
            "active_memory_count_before": self.active_memory_count_before,
            "active_memory_count_after": self.active_memory_count_after,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryCurationResult:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            result_id=data.get("result_id", ""),
            trace_id=data.get("trace_id", ""),
            turn_id=data.get("turn_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            accepted_candidates=[
                MemoryCurationCandidate.from_dict(c)
                for c in data.get("accepted_candidates", [])
            ],
            rejected_candidates=[
                MemoryCurationCandidate.from_dict(c)
                for c in data.get("rejected_candidates", [])
            ],
            rejection_reasons=list(data.get("rejection_reasons", [])),
            degraded=data.get("degraded", False),
            degraded_reasons=list(data.get("degraded_reasons", [])),
            total_candidates_generated=data.get("total_candidates_generated", 0),
            total_candidates_accepted=data.get("total_candidates_accepted", 0),
            total_candidates_rejected=data.get("total_candidates_rejected", 0),
            active_memory_count_before=data.get("active_memory_count_before", 0),
            active_memory_count_after=data.get("active_memory_count_after", 0),
        )
