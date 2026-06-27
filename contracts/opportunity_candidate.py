"""OpportunityCandidate — a single opportunity candidate.

schemaId: awp.rp.opportunity-candidate.v1

Opportunity != Event. An opportunity is a narrative opening based on existing facts.
It cannot assert facts, modify state, or advance the timeline.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.opportunity-candidate.v1"
SCHEMA_VERSION = 1

class OpportunityKind(str, Enum):
    THREAD_RECALL = "thread_recall"
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

class NarrativeFunction(str, Enum):
    INCREASE_TENSION = "increase_tension"
    CREATE_CHOICE_SPACE = "create_choice_space"
    DEEPEN_CHARACTERIZATION = "deepen_characterization"
    SURFACE_UNRESOLVED_THREAD = "surface_unresolved_thread"
    SOFTEN_TRANSITION = "soften_transition"
    CREATE_EMOTIONAL_SUBTEXT = "create_emotional_subtext"
    PREPARE_FUTURE_HOOK = "prepare_future_hook"
    AVOID_REPETITION = "avoid_repetition"

@dataclass
class OpportunityCandidate:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    candidate_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    kind: OpportunityKind = OpportunityKind.THREAD_RECALL
    title: str = ""
    summary: str = ""
    narrative_function: NarrativeFunction = NarrativeFunction.INCREASE_TENSION
    focus_entities: list[str] = field(default_factory=list)
    foundation_facts: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    activation_conditions: list[str] = field(default_factory=list)
    player_agency_risk: float = 0.0
    continuity_risk: float = 0.0
    novelty_score: float = 0.5
    relevance_score: float = 0.5
    confidence: float = 0.5
    suggested_writer_use: str = ""
    suggested_director_use: str = ""
    must_not_assert_as_fact: bool = True
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "candidate_id": self.candidate_id, "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id, "kind": self.kind.value,
            "title": self.title, "summary": self.summary,
            "narrative_function": self.narrative_function.value,
            "focus_entities": self.focus_entities,
            "foundation_facts": self.foundation_facts,
            "evidence_refs": self.evidence_refs,
            "activation_conditions": self.activation_conditions,
            "player_agency_risk": self.player_agency_risk,
            "continuity_risk": self.continuity_risk,
            "novelty_score": self.novelty_score,
            "relevance_score": self.relevance_score,
            "confidence": self.confidence,
            "suggested_writer_use": self.suggested_writer_use,
            "suggested_director_use": self.suggested_director_use,
            "must_not_assert_as_fact": self.must_not_assert_as_fact,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpportunityCandidate:
        kind_raw = data.get("kind", "thread_recall")
        try:
            kind = OpportunityKind(kind_raw)
        except ValueError:
            kind = OpportunityKind.THREAD_RECALL
        func_raw = data.get("narrative_function", "increase_tension")
        try:
            func = NarrativeFunction(func_raw)
        except ValueError:
            func = NarrativeFunction.INCREASE_TENSION
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            candidate_id=data.get("candidate_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            kind=kind, title=data.get("title", ""),
            summary=data.get("summary", ""),
            narrative_function=func,
            focus_entities=data.get("focus_entities", []),
            foundation_facts=data.get("foundation_facts", []),
            evidence_refs=data.get("evidence_refs", []),
            activation_conditions=data.get("activation_conditions", []),
            player_agency_risk=data.get("player_agency_risk", 0.0),
            continuity_risk=data.get("continuity_risk", 0.0),
            novelty_score=data.get("novelty_score", 0.5),
            relevance_score=data.get("relevance_score", 0.5),
            confidence=data.get("confidence", 0.5),
            suggested_writer_use=data.get("suggested_writer_use", ""),
            suggested_director_use=data.get("suggested_director_use", ""),
            must_not_assert_as_fact=data.get("must_not_assert_as_fact", True),
            created_at=data.get("created_at", ""),
        )
