"""MemoryCurationTriggerDiagnostics — trigger policy result for Memory Curator.

schemaId: awp.rp.memory-curation-trigger-diagnostics.v1

Deterministic evaluation of whether the Memory Curator should run for the
current accepted turn. Only fires when QualityGate=ACCEPT, CardStateCommit
=SUCCESS, and TurnRecordCommit=SUCCESS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.memory-curation-trigger-diagnostics.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class MemoryCurationTriggerDiagnostics:
    """Result of the Memory Curation trigger policy evaluation."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    should_trigger: bool = False
    trigger_reasons: list[str] = field(default_factory=list)
    curation_domains: list[str] = field(default_factory=list)
    max_active_candidates: int = 5
    max_rag_candidates: int = 5
    idempotency_key: str = ""
    risk_level: str = "none"
    skip_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "should_trigger": self.should_trigger,
            "trigger_reasons": list(self.trigger_reasons),
            "curation_domains": list(self.curation_domains),
            "max_active_candidates": self.max_active_candidates,
            "max_rag_candidates": self.max_rag_candidates,
            "idempotency_key": self.idempotency_key,
            "risk_level": self.risk_level,
            "skip_reason": self.skip_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryCurationTriggerDiagnostics:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            should_trigger=data.get("should_trigger", False),
            trigger_reasons=list(data.get("trigger_reasons", [])),
            curation_domains=list(data.get("curation_domains", [])),
            max_active_candidates=data.get("max_active_candidates", 5),
            max_rag_candidates=data.get("max_rag_candidates", 5),
            idempotency_key=data.get("idempotency_key", ""),
            risk_level=data.get("risk_level", "none"),
            skip_reason=data.get("skip_reason", ""),
        )
