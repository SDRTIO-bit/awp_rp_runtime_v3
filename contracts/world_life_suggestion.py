"""WorldLifeSuggestion — structured suggestion from World-Life Agent.

schemaId: awp.rp.world-life-suggestion.v1

This is the output that gets converted to AgentSuggestion for SuggestionMerge.
World-life suggestions are SOFT guidance -- they cannot be asserted as facts.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.world-life-suggestion.v1"
SCHEMA_VERSION = 1


class WorldLifeSuggestionKind(str, Enum):
    ENVIRONMENTAL_PRESSURE = "environmental_pressure"
    WEATHER_OR_TIME_ATMOSPHERE = "weather_or_time_atmosphere"
    NPC_SIDE_TENSION = "npc_side_tension"
    EVENT_STAGE_ECHO = "event_stage_echo"
    LOCATION_LIFE_DETAIL = "location_life_detail"
    SOCIAL_BACKGROUND_SIGNAL = "social_background_signal"
    WORLDBOOK_RESONANCE = "worldbook_resonance"
    OFFSCREEN_CONSEQUENCE_HINT = "offscreen_consequence_hint"
    AMBIENT_RUMOR_SIGNAL = "ambient_rumor_signal"
    SCENE_TRANSITION_PRESSURE = "scene_transition_pressure"
    WORLD_LIFE_WARNING = "world_life_warning"


@dataclass
class WorldLifeSuggestion:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    suggestion_id: str = ""
    kind: WorldLifeSuggestionKind = WorldLifeSuggestionKind.ENVIRONMENTAL_PRESSURE
    title: str = ""
    summary: str = ""
    narrative_function: str = ""
    world_layer: str = ""
    focus_entities: list[str] = field(default_factory=list)
    focus_location: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float = 0.5
    priority: float = 0.5
    writer_guidance: str = ""
    director_guidance: str = ""
    must_not_assert_as_fact: bool = True
    must_not_commit_state: bool = True
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "suggestion_id": self.suggestion_id, "kind": self.kind.value,
            "title": self.title, "summary": self.summary,
            "narrative_function": self.narrative_function,
            "world_layer": self.world_layer,
            "focus_entities": self.focus_entities,
            "focus_location": self.focus_location,
            "evidence_refs": self.evidence_refs,
            "confidence": self.confidence, "priority": self.priority,
            "writer_guidance": self.writer_guidance,
            "director_guidance": self.director_guidance,
            "must_not_assert_as_fact": self.must_not_assert_as_fact,
            "must_not_commit_state": self.must_not_commit_state,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldLifeSuggestion:
        kind_raw = data.get("kind", "environmental_pressure")
        try:
            kind = WorldLifeSuggestionKind(kind_raw)
        except ValueError:
            kind = WorldLifeSuggestionKind.ENVIRONMENTAL_PRESSURE
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            suggestion_id=data.get("suggestion_id", ""),
            kind=kind, title=data.get("title", ""),
            summary=data.get("summary", ""),
            narrative_function=data.get("narrative_function", ""),
            world_layer=data.get("world_layer", ""),
            focus_entities=data.get("focus_entities", []),
            focus_location=data.get("focus_location", ""),
            evidence_refs=data.get("evidence_refs", []),
            confidence=data.get("confidence", 0.5),
            priority=data.get("priority", 0.5),
            writer_guidance=data.get("writer_guidance", ""),
            director_guidance=data.get("director_guidance", ""),
            must_not_assert_as_fact=data.get("must_not_assert_as_fact", True),
            must_not_commit_state=data.get("must_not_commit_state", True),
            created_at=data.get("created_at", ""),
        )
