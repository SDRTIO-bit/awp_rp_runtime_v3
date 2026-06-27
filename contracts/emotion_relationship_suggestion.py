"""EmotionRelationshipSuggestion — structured suggestion from Emotion/Relationship Agent.

schemaId: awp.rp.emotion-relationship-suggestion.v1

This is the output that gets converted to AgentSuggestion for SuggestionMerge.
Emotion/relationship suggestions are SOFT guidance -- they cannot assert facts
or modify relationships.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.emotion-relationship-suggestion.v1"
SCHEMA_VERSION = 1

class EmotionRelationshipSuggestionKind(str, Enum):
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
    EMOTION_RELATIONSHIP_WARNING = "emotion_relationship_warning"

@dataclass
class EmotionRelationshipSuggestion:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    suggestion_id: str = ""
    kind: EmotionRelationshipSuggestionKind = EmotionRelationshipSuggestionKind.TRUST_TENSION
    title: str = ""
    summary: str = ""
    focus_entities: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float = 0.5
    priority: float = 0.5
    writer_guidance: str = ""
    director_guidance: str = ""
    must_not_assert_as_fact: bool = True
    must_not_modify_relationship: bool = True
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "suggestion_id": self.suggestion_id, "kind": self.kind.value,
            "title": self.title, "summary": self.summary,
            "focus_entities": self.focus_entities,
            "evidence_refs": self.evidence_refs,
            "confidence": self.confidence, "priority": self.priority,
            "writer_guidance": self.writer_guidance,
            "director_guidance": self.director_guidance,
            "must_not_assert_as_fact": self.must_not_assert_as_fact,
            "must_not_modify_relationship": self.must_not_modify_relationship,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmotionRelationshipSuggestion:
        kind_raw = data.get("kind", "trust_tension")
        try:
            kind = EmotionRelationshipSuggestionKind(kind_raw)
        except ValueError:
            kind = EmotionRelationshipSuggestionKind.TRUST_TENSION
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            suggestion_id=data.get("suggestion_id", ""),
            kind=kind, title=data.get("title", ""),
            summary=data.get("summary", ""),
            focus_entities=data.get("focus_entities", []),
            evidence_refs=data.get("evidence_refs", []),
            confidence=data.get("confidence", 0.5),
            priority=data.get("priority", 0.5),
            writer_guidance=data.get("writer_guidance", ""),
            director_guidance=data.get("director_guidance", ""),
            must_not_assert_as_fact=data.get("must_not_assert_as_fact", True),
            must_not_modify_relationship=data.get("must_not_modify_relationship", True),
            created_at=data.get("created_at", ""),
        )
