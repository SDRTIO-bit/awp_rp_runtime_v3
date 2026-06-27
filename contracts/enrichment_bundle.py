"""EnrichmentBundle — merged and validated tool results for Director.

schemaId: awp.rp.enrichment-bundle.v1

Created after ToolGateway execution. Director uses this to produce FinalTurnBrief.
Tool results are validated, summarized, and categorized before reaching Director.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.enrichment-bundle.v1"
SCHEMA_VERSION = 1


@dataclass
class EnrichmentItem:
    """A single enriched item from a tool result."""
    source_request_id: str = ""
    tool_id: str = ""
    status: str = ""
    summary: str = ""
    structured_data: dict[str, Any] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    accepted: bool = True
    rejection_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_request_id": self.source_request_id,
            "tool_id": self.tool_id,
            "status": self.status,
            "summary": self.summary,
            "structured_data": self.structured_data,
            "evidence": self.evidence,
            "source_refs": self.source_refs,
            "accepted": self.accepted,
            "rejection_reason": self.rejection_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnrichmentItem:
        return cls(
            source_request_id=data.get("source_request_id", ""),
            tool_id=data.get("tool_id", ""),
            status=data.get("status", ""),
            summary=data.get("summary", ""),
            structured_data=data.get("structured_data", {}),
            evidence=data.get("evidence", []),
            source_refs=data.get("source_refs", []),
            accepted=data.get("accepted", True),
            rejection_reason=data.get("rejection_reason", ""),
        )


@dataclass
class EnrichmentBundle:
    """Merged and validated tool results for Director consumption."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity
    bundle_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    tool_result_bundle_id: str = ""

    # Enriched items
    accepted_items: list[EnrichmentItem] = field(default_factory=list)
    rejected_items: list[EnrichmentItem] = field(default_factory=list)
    degraded_items: list[EnrichmentItem] = field(default_factory=list)

    # Summary
    total_tools_called: int = 0
    total_successful: int = 0
    total_failed: int = 0

    # Timestamp
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "bundle_id": self.bundle_id,
            "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id,
            "tool_result_bundle_id": self.tool_result_bundle_id,
            "accepted_items": [i.to_dict() for i in self.accepted_items],
            "rejected_items": [i.to_dict() for i in self.rejected_items],
            "degraded_items": [i.to_dict() for i in self.degraded_items],
            "total_tools_called": self.total_tools_called,
            "total_successful": self.total_successful,
            "total_failed": self.total_failed,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnrichmentBundle:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            bundle_id=data.get("bundle_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            tool_result_bundle_id=data.get("tool_result_bundle_id", ""),
            accepted_items=[EnrichmentItem.from_dict(i) for i in data.get("accepted_items", [])],
            rejected_items=[EnrichmentItem.from_dict(i) for i in data.get("rejected_items", [])],
            degraded_items=[EnrichmentItem.from_dict(i) for i in data.get("degraded_items", [])],
            total_tools_called=data.get("total_tools_called", 0),
            total_successful=data.get("total_successful", 0),
            total_failed=data.get("total_failed", 0),
            created_at=data.get("created_at", ""),
        )
