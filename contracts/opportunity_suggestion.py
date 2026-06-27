"""OpportunitySuggestion — structured suggestion from Opportunity Agent.

schemaId: awp.rp.opportunity-suggestion.v1

This is the output that gets converted to AgentSuggestion for SuggestionMerge.
Opportunity suggestions are SOFT guidance -- they cannot be asserted as facts.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.opportunity-suggestion.v1"
SCHEMA_VERSION = 1

class OpportunitySuggestionKind(str, Enum):
    PROMISE_PRESSURE = "promise_pressure"
    RELATIONSHIP_TENSION = "relationship_tension"
    EMOTIONAL_SHIFT = "emotional_shift"
    SECRET_PRESSURE = "secret_pressure"
    MISUNDERSTANDING_PRESSURE = "misunderstanding_pressure"
    GOAL_REACTIVATION = "goal_reactivation"
    SCENE_PRESSURE = "scene_pressure"
    CHOICE_OPENING = "choice_opening"
    FORESHADOWING_ECHO = "foreshadowing_echo"
    PACE_VARIATION = "pace_variation"
    OPPORTUNITY_WARNING = "opportunity_warning"

@dataclass
class OpportunitySuggestion:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    suggestion_id: str = ""
    kind: OpportunitySuggestionKind = OpportunitySuggestionKind.CHOICE_OPENING
    title: str = ""
    summary: str = ""
    narrative_function: str = ""
    focus_entities: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float = 0.5
    priority: float = 0.5
    writer_guidance: str = ""
    director_guidance: str = ""
    must_not_assert_as_fact: bool = True
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "suggestion_id": self.suggestion_id, "kind": self.kind.value,
            "title": self.title, "summary": self.summary,
            "narrative_function": self.narrative_function,
            "focus_entities": self.focus_entities,
            "evidence_refs": self.evidence_refs,
            "confidence": self.confidence, "priority": self.priority,
            "writer_guidance": self.writer_guidance,
            "director_guidance": self.director_guidance,
            "must_not_assert_as_fact": self.must_not_assert_as_fact,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpportunitySuggestion:
        kind_raw = data.get("kind", "choice_opening")
        try:
            kind = OpportunitySuggestionKind(kind_raw)
        except ValueError:
            kind = OpportunitySuggestionKind.CHOICE_OPENING
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            suggestion_id=data.get("suggestion_id", ""),
            kind=kind, title=data.get("title", ""),
            summary=data.get("summary", ""),
            narrative_function=data.get("narrative_function", ""),
            focus_entities=data.get("focus_entities", []),
            evidence_refs=data.get("evidence_refs", []),
            confidence=data.get("confidence", 0.5),
            priority=data.get("priority", 0.5),
            writer_guidance=data.get("writer_guidance", ""),
            director_guidance=data.get("director_guidance", ""),
            must_not_assert_as_fact=data.get("must_not_assert_as_fact", True),
            created_at=data.get("created_at", ""),
        )
