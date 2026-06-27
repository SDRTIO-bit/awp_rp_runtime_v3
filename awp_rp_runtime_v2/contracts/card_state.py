"""CardState — the single source of truth for world and character variables.

schemaId: awp.rp.card-state.v1

CardState is the ONLY deterministic reality store.
All writes go through CardStateCommitRuntime with:
  - expectedRevision check
  - patchId idempotency
  - full-operation validation (any illegal op → zero writes)
  - revision increments by exactly 1 on success
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.card-state.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class VariableEntry:
    """A single variable in CardState."""
    name: str
    value: Any
    var_type: str = "string"  # string | int | float | bool | json
    description: str = ""
    last_updated_turn: str | None = None


@dataclass(frozen=True)
class EventFlag:
    """An event flag tracking whether an event has fired."""
    event_id: str
    fired: bool = False
    fired_at_turn: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SceneState:
    """Current scene information."""
    location: str = ""
    time_of_day: str = ""
    weather: str = ""
    active_npcs: list[str] = field(default_factory=list)
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CardState:
    """The deterministic reality of a card session.

    This is the ONLY source of truth for world variables, event flags,
    and scene state. No agent may write directly; all writes go through
    CardStateCommitRuntime.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    card_id: str = ""
    session_id: str = ""
    revision: int = 0
    variables: dict[str, VariableEntry] = field(default_factory=dict)
    event_flags: dict[str, EventFlag] = field(default_factory=dict)
    active_stage_ids: list[str] = field(default_factory=list)
    scene_state: SceneState = field(default_factory=SceneState)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    last_accepted_turn_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for storage."""
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "revision": self.revision,
            "variables": {
                k: {
                    "name": v.name, "value": v.value, "var_type": v.var_type,
                    "description": v.description, "last_updated_turn": v.last_updated_turn,
                }
                for k, v in self.variables.items()
            },
            "event_flags": {
                k: {
                    "event_id": v.event_id, "fired": v.fired,
                    "fired_at_turn": v.fired_at_turn, "metadata": v.metadata,
                }
                for k, v in self.event_flags.items()
            },
            "active_stage_ids": list(self.active_stage_ids),
            "scene_state": {
                "location": self.scene_state.location,
                "time_of_day": self.scene_state.time_of_day,
                "weather": self.scene_state.weather,
                "active_npcs": list(self.scene_state.active_npcs),
                "description": self.scene_state.description,
                "metadata": dict(self.scene_state.metadata),
            },
            "diagnostics": dict(self.diagnostics),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_accepted_turn_id": self.last_accepted_turn_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardState:
        """Deserialize from dict."""
        variables = {}
        for k, v in data.get("variables", {}).items():
            variables[k] = VariableEntry(**v)

        event_flags = {}
        for k, v in data.get("event_flags", {}).items():
            event_flags[k] = EventFlag(**v)

        scene_data = data.get("scene_state", {})
        scene_state = SceneState(**scene_data) if scene_data else SceneState()

        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            revision=data.get("revision", 0),
            variables=variables,
            event_flags=event_flags,
            active_stage_ids=data.get("active_stage_ids", []),
            scene_state=scene_state,
            diagnostics=data.get("diagnostics", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            last_accepted_turn_id=data.get("last_accepted_turn_id", ""),
        )

    def validate(self) -> list[str]:
        """Validate this CardState. Returns list of errors (empty = valid)."""
        errors = []
        if not self.card_id:
            errors.append("card_id is required")
        if not self.session_id:
            errors.append("session_id is required")
        if self.revision < 0:
            errors.append("revision must be non-negative")
        if self.schema_id != SCHEMA_ID:
            errors.append(f"schema_id must be {SCHEMA_ID}")
        return errors
