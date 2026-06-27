"""EmotionRelationshipCandidate — a single emotion/relationship candidate.

schemaId: awp.rp.emotion-relationship-candidate.v1

An emotion/relationship candidate captures a specific relational dynamic or
emotional undercurrent detected in the narrative context. It is SOFT guidance
-- it cannot assert facts or modify relationships.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.emotion-relationship-candidate.v1"
SCHEMA_VERSION = 1

class RelationshipKind(str, Enum):
    TRUST_TENSION = "trust_tension"
    GUARDEDNESS = "guardedness"
    EMOTIONAL_RESIDUE = "emotional_residue"
    UNRESOLVED_HURT = "unresolved_hurt"
    PROMISE_PRESSURE = "promise_pressure"
    MISUNDERSTANDING_SIGNAL = "misunderstanding_signal"
    JEALOUSY_RISK = "jealousy_risk"
    AFFECTION_RESTRAINT = "affection_restraint"
    CONFLICT_DEESCALATION = "conflict_deescalation"
    RELATIONSHIP_BOUNDARY = "relationship_boundary"
    SUBTEXT_OPPORTUNITY = "subtext_opportunity"

@dataclass
class EmotionRelationshipCandidate:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    candidate_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    kind: RelationshipKind = RelationshipKind.TRUST_TENSION
    summary: str = ""
    focus_entities: list[str] = field(default_factory=list)
    relationship_state_interpretation: str = ""
    emotional_signals: list[str] = field(default_factory=list)
    foundation_facts: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float = 0.5
    player_agency_risk: float = 0.0
    continuity_risk: float = 0.0
    sudden_shift_risk: float = 0.0
    suggested_writer_use: str = ""
    suggested_director_use: str = ""
    must_not_assert_as_fact: bool = True
    must_not_modify_relationship: bool = True
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "candidate_id": self.candidate_id, "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id, "kind": self.kind.value,
            "summary": self.summary,
            "focus_entities": self.focus_entities,
            "relationship_state_interpretation": self.relationship_state_interpretation,
            "emotional_signals": self.emotional_signals,
            "foundation_facts": self.foundation_facts,
            "evidence_refs": self.evidence_refs,
            "confidence": self.confidence,
            "player_agency_risk": self.player_agency_risk,
            "continuity_risk": self.continuity_risk,
            "sudden_shift_risk": self.sudden_shift_risk,
            "suggested_writer_use": self.suggested_writer_use,
            "suggested_director_use": self.suggested_director_use,
            "must_not_assert_as_fact": self.must_not_assert_as_fact,
            "must_not_modify_relationship": self.must_not_modify_relationship,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmotionRelationshipCandidate:
        kind_raw = data.get("kind", "trust_tension")
        try:
            kind = RelationshipKind(kind_raw)
        except ValueError:
            kind = RelationshipKind.TRUST_TENSION
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            candidate_id=data.get("candidate_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            kind=kind,
            summary=data.get("summary", ""),
            focus_entities=data.get("focus_entities", []),
            relationship_state_interpretation=data.get("relationship_state_interpretation", ""),
            emotional_signals=data.get("emotional_signals", []),
            foundation_facts=data.get("foundation_facts", []),
            evidence_refs=data.get("evidence_refs", []),
            confidence=data.get("confidence", 0.5),
            player_agency_risk=data.get("player_agency_risk", 0.0),
            continuity_risk=data.get("continuity_risk", 0.0),
            sudden_shift_risk=data.get("sudden_shift_risk", 0.0),
            suggested_writer_use=data.get("suggested_writer_use", ""),
            suggested_director_use=data.get("suggested_director_use", ""),
            must_not_assert_as_fact=data.get("must_not_assert_as_fact", True),
            must_not_modify_relationship=data.get("must_not_modify_relationship", True),
            created_at=data.get("created_at", ""),
        )
