"""WorldLifeCandidate — a single world-life candidate.

schemaId: awp.rp.world-life-candidate.v1

World-Life Candidate = based on existing facts, suggests how environment,
NPC side-tensions, or event pressures could naturally appear in narration.

It CANNOT:
- Assert facts as having happened
- Modify state or advance timeline
- Override player agency
- Create new events or NPCs
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.world-life-candidate.v1"
SCHEMA_VERSION = 1


class WorldLifeKind(str, Enum):
    """Types of world-life candidates."""
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


class WorldLayer(str, Enum):
    """World layers for categorizing candidates."""
    ENVIRONMENT = "environment"
    LOCATION = "location"
    NPC = "npc"
    EVENT_STAGE = "event_stage"
    SOCIAL_WORLD = "social_world"
    WORLDBOOK = "worldbook"
    OFFSCREEN = "offscreen"


class VisibilityMode(str, Enum):
    """How the candidate can appear in narration."""
    BACKGROUND = "background"
    SUBTLE_SIGNAL = "subtle_signal"
    OPTIONAL_DIALOGUE_COLOR = "optional_dialogue_color"
    OPTIONAL_ACTION_CUE = "optional_action_cue"
    DIRECTOR_ONLY_WARNING = "director_only_warning"


@dataclass
class WorldLifeCandidate:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    candidate_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    kind: WorldLifeKind = WorldLifeKind.ENVIRONMENTAL_PRESSURE
    title: str = ""
    summary: str = ""
    world_layer: WorldLayer = WorldLayer.ENVIRONMENT
    narrative_function: str = ""
    focus_entities: list[str] = field(default_factory=list)
    focus_location: str = ""
    foundation_facts: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    activation_conditions: list[str] = field(default_factory=list)
    visibility_mode: VisibilityMode = VisibilityMode.BACKGROUND
    player_agency_risk: float = 0.0
    continuity_risk: float = 0.0
    state_change_risk: float = 0.0
    novelty_score: float = 0.5
    relevance_score: float = 0.5
    confidence: float = 0.5
    suggested_writer_use: str = ""
    suggested_director_use: str = ""
    must_not_assert_as_fact: bool = True
    must_not_commit_state: bool = True
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "candidate_id": self.candidate_id, "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id, "kind": self.kind.value,
            "title": self.title, "summary": self.summary,
            "world_layer": self.world_layer.value,
            "narrative_function": self.narrative_function,
            "focus_entities": self.focus_entities,
            "focus_location": self.focus_location,
            "foundation_facts": self.foundation_facts,
            "evidence_refs": self.evidence_refs,
            "activation_conditions": self.activation_conditions,
            "visibility_mode": self.visibility_mode.value,
            "player_agency_risk": self.player_agency_risk,
            "continuity_risk": self.continuity_risk,
            "state_change_risk": self.state_change_risk,
            "novelty_score": self.novelty_score,
            "relevance_score": self.relevance_score,
            "confidence": self.confidence,
            "suggested_writer_use": self.suggested_writer_use,
            "suggested_director_use": self.suggested_director_use,
            "must_not_assert_as_fact": self.must_not_assert_as_fact,
            "must_not_commit_state": self.must_not_commit_state,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldLifeCandidate:
        kind_raw = data.get("kind", "environmental_pressure")
        try:
            kind = WorldLifeKind(kind_raw)
        except ValueError:
            kind = WorldLifeKind.ENVIRONMENTAL_PRESSURE
        layer_raw = data.get("world_layer", "environment")
        try:
            layer = WorldLayer(layer_raw)
        except ValueError:
            layer = WorldLayer.ENVIRONMENT
        vis_raw = data.get("visibility_mode", "background")
        try:
            vis = VisibilityMode(vis_raw)
        except ValueError:
            vis = VisibilityMode.BACKGROUND
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            candidate_id=data.get("candidate_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            kind=kind, title=data.get("title", ""),
            summary=data.get("summary", ""),
            world_layer=layer,
            narrative_function=data.get("narrative_function", ""),
            focus_entities=data.get("focus_entities", []),
            focus_location=data.get("focus_location", ""),
            foundation_facts=data.get("foundation_facts", []),
            evidence_refs=data.get("evidence_refs", []),
            activation_conditions=data.get("activation_conditions", []),
            visibility_mode=vis,
            player_agency_risk=data.get("player_agency_risk", 0.0),
            continuity_risk=data.get("continuity_risk", 0.0),
            state_change_risk=data.get("state_change_risk", 0.0),
            novelty_score=data.get("novelty_score", 0.5),
            relevance_score=data.get("relevance_score", 0.5),
            confidence=data.get("confidence", 0.5),
            suggested_writer_use=data.get("suggested_writer_use", ""),
            suggested_director_use=data.get("suggested_director_use", ""),
            must_not_assert_as_fact=data.get("must_not_assert_as_fact", True),
            must_not_commit_state=data.get("must_not_commit_state", True),
            created_at=data.get("created_at", ""),
        )
