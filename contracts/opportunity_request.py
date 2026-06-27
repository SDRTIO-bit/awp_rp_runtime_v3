"""OpportunityRequest — request for opportunity analysis.

schemaId: awp.rp.opportunity-request.v1
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.opportunity-request.v1"
SCHEMA_VERSION = 1

@dataclass
class OpportunityRequest:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    request_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    task_run_id: str = ""
    card_id: str = ""
    session_id: str = ""
    focus_entities: list[str] = field(default_factory=list)
    focus_threads: list[str] = field(default_factory=list)
    focus_relationship_tensions: list[str] = field(default_factory=list)
    focus_scene_pressures: list[str] = field(default_factory=list)
    player_intent: str = ""
    max_candidates: int = 5
    required_evidence: bool = True
    must_not_create_facts: bool = True
    must_preserve_facts: list[str] = field(default_factory=list)
    must_not_do: list[str] = field(default_factory=list)
    budget: int = 1000
    deadline: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "request_id": self.request_id, "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id, "task_run_id": self.task_run_id,
            "card_id": self.card_id, "session_id": self.session_id,
            "focus_entities": self.focus_entities, "focus_threads": self.focus_threads,
            "focus_relationship_tensions": self.focus_relationship_tensions,
            "focus_scene_pressures": self.focus_scene_pressures,
            "player_intent": self.player_intent,
            "max_candidates": self.max_candidates,
            "required_evidence": self.required_evidence,
            "must_not_create_facts": self.must_not_create_facts,
            "must_preserve_facts": self.must_preserve_facts,
            "must_not_do": self.must_not_do,
            "budget": self.budget, "deadline": self.deadline,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OpportunityRequest:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            request_id=data.get("request_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            task_run_id=data.get("task_run_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            focus_entities=data.get("focus_entities", []),
            focus_threads=data.get("focus_threads", []),
            focus_relationship_tensions=data.get("focus_relationship_tensions", []),
            focus_scene_pressures=data.get("focus_scene_pressures", []),
            player_intent=data.get("player_intent", ""),
            max_candidates=data.get("max_candidates", 5),
            required_evidence=data.get("required_evidence", True),
            must_not_create_facts=data.get("must_not_create_facts", True),
            must_preserve_facts=data.get("must_preserve_facts", []),
            must_not_do=data.get("must_not_do", []),
            budget=data.get("budget", 1000),
            deadline=data.get("deadline", ""),
            created_at=data.get("created_at", ""),
        )
