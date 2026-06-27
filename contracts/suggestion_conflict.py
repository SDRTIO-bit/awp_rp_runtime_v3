"""SuggestionConflict — unified conflict record for D-Integration.

schemaId: awp.rp.suggestion-conflict.v1

Records when two or more suggestions cannot coexist.
Tracks involved suggestions, conflict kind, evidence-based priority
decision, and final resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.suggestion-conflict.v1"
SCHEMA_VERSION = 1


class ConflictKind(str, Enum):
    """What kind of conflict this is."""
    FACT_CONTRADICTION = "fact_contradiction"
    STATE_PATH_COLLISION = "state_path_collision"
    PLAYER_AGENCY_VIOLATION = "player_agency_violation"
    EVIDENCE_PRIORITY_OVERRIDE = "evidence_priority_override"
    TEMPORAL_CONTRADICTION = "temporal_contradiction"
    RELATIONSHIP_BOUNDARY = "relationship_boundary"
    WORLD_LIFE_FACT_LEAK = "world_life_fact_leak"
    OPPORTUNITY_FACT_LEAK = "opportunity_fact_leak"
    EMOTION_FACT_LEAK = "emotion_fact_leak"
    CONTINUITY_HARD_BLOCK = "continuity_hard_block"


class ConflictResolution(str, Enum):
    """How the conflict was resolved."""
    ACCEPTED = "accepted"
    PARTIALLY_ACCEPTED = "partially_accepted"
    REJECTED = "rejected"
    DOWNGRADED_TO_SOFT_GUIDANCE = "downgraded_to_soft_guidance"
    DEFERRED = "deferred"
    BLOCKED_BY_PLAYER_AGENCY = "blocked_by_player_agency"
    BLOCKED_BY_HARD_FACT = "blocked_by_hard_fact"


@dataclass
class SuggestionConflict:
    """A single conflict between two or more suggestions."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    conflict_id: str = ""
    trace_id: str = ""
    turn_id: str = ""

    involved_suggestion_ids: list[str] = field(default_factory=list)
    conflict_kind: ConflictKind = ConflictKind.FACT_CONTRADICTION
    evidence_refs: list[str] = field(default_factory=list)

    priority_decision: str = ""
    resolution: ConflictResolution = ConflictResolution.REJECTED
    rejected_suggestion_ids: list[str] = field(default_factory=list)
    downgraded_suggestion_ids: list[str] = field(default_factory=list)

    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "conflict_id": self.conflict_id,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "involved_suggestion_ids": self.involved_suggestion_ids,
            "conflict_kind": self.conflict_kind.value,
            "evidence_refs": self.evidence_refs,
            "priority_decision": self.priority_decision,
            "resolution": self.resolution.value,
            "rejected_suggestion_ids": self.rejected_suggestion_ids,
            "downgraded_suggestion_ids": self.downgraded_suggestion_ids,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SuggestionConflict:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            conflict_id=data.get("conflict_id", ""),
            trace_id=data.get("trace_id", ""),
            turn_id=data.get("turn_id", ""),
            involved_suggestion_ids=data.get("involved_suggestion_ids", []),
            conflict_kind=ConflictKind(data.get("conflict_kind", "fact_contradiction")),
            evidence_refs=data.get("evidence_refs", []),
            priority_decision=data.get("priority_decision", ""),
            resolution=ConflictResolution(data.get("resolution", "rejected")),
            rejected_suggestion_ids=data.get("rejected_suggestion_ids", []),
            downgraded_suggestion_ids=data.get("downgraded_suggestion_ids", []),
            created_at=data.get("created_at", ""),
        )
