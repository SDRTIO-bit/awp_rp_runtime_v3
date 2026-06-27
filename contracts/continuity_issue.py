"""ContinuityIssue — a single continuity issue detected by Continuity Agent.

schemaId: awp.rp.continuity-issue.v1

Each issue identifies a conflict, ambiguity, missing premise, or
fact boundary that the Writer must not violate.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.continuity-issue.v1"
SCHEMA_VERSION = 1


class ContinuityIssueKind(str, Enum):
    IDENTITY_CONFLICT = "identity_conflict"
    LOCATION_CONFLICT = "location_conflict"
    TIMELINE_CONFLICT = "timeline_conflict"
    EVENT_STAGE_CONFLICT = "event_stage_conflict"
    STATE_CONFLICT = "state_conflict"
    RELATIONSHIP_CONFLICT = "relationship_conflict"
    KNOWLEDGE_BOUNDARY_CONFLICT = "knowledge_boundary_conflict"
    SECRET_EXPOSURE_RISK = "secret_exposure_risk"
    PROMISE_RESOLUTION_RISK = "promise_resolution_risk"
    CHARACTER_AVAILABILITY_CONFLICT = "character_availability_conflict"
    CAUSALITY_GAP = "causality_gap"
    MEMORY_CONFLICT = "memory_conflict"
    SUGGESTION_CONFLICT = "suggestion_conflict"
    WORLDBOOK_CONFLICT = "worldbook_conflict"
    PLAYER_AGENCY_RISK = "player_agency_risk"


class ContinuitySeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


@dataclass
class ContinuityIssue:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    issue_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    kind: ContinuityIssueKind = ContinuityIssueKind.STATE_CONFLICT
    severity: ContinuitySeverity = ContinuitySeverity.WARNING
    summary: str = ""
    affected_entities: list[str] = field(default_factory=list)
    affected_locations: list[str] = field(default_factory=list)
    affected_turns: list[str] = field(default_factory=list)
    foundation_facts: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    conflicting_refs: list[str] = field(default_factory=list)
    priority_decision: str = ""
    writer_constraint: str = ""
    director_recommendation: str = ""
    must_not_assert_as_fact: bool = True
    must_not_modify_state: bool = True
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "issue_id": self.issue_id, "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id,
            "kind": self.kind.value, "severity": self.severity.value,
            "summary": self.summary,
            "affected_entities": self.affected_entities,
            "affected_locations": self.affected_locations,
            "affected_turns": self.affected_turns,
            "foundation_facts": self.foundation_facts,
            "evidence_refs": self.evidence_refs,
            "conflicting_refs": self.conflicting_refs,
            "priority_decision": self.priority_decision,
            "writer_constraint": self.writer_constraint,
            "director_recommendation": self.director_recommendation,
            "must_not_assert_as_fact": self.must_not_assert_as_fact,
            "must_not_modify_state": self.must_not_modify_state,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContinuityIssue:
        kind_raw = data.get("kind", "state_conflict")
        try:
            kind = ContinuityIssueKind(kind_raw)
        except ValueError:
            kind = ContinuityIssueKind.STATE_CONFLICT
        sev_raw = data.get("severity", "warning")
        try:
            severity = ContinuitySeverity(sev_raw)
        except ValueError:
            severity = ContinuitySeverity.WARNING
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            issue_id=data.get("issue_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            kind=kind, severity=severity,
            summary=data.get("summary", ""),
            affected_entities=data.get("affected_entities", []),
            affected_locations=data.get("affected_locations", []),
            affected_turns=data.get("affected_turns", []),
            foundation_facts=data.get("foundation_facts", []),
            evidence_refs=data.get("evidence_refs", []),
            conflicting_refs=data.get("conflicting_refs", []),
            priority_decision=data.get("priority_decision", ""),
            writer_constraint=data.get("writer_constraint", ""),
            director_recommendation=data.get("director_recommendation", ""),
            must_not_assert_as_fact=data.get("must_not_assert_as_fact", True),
            must_not_modify_state=data.get("must_not_modify_state", True),
            created_at=data.get("created_at", ""),
        )
