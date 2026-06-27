"""ContinuityRequest — request for continuity analysis.

schemaId: awp.rp.continuity-request.v1

Continuity Agent checks whether confirmed facts, character states,
timelines, locations, knowledge boundaries, relationship states,
event stages, or adopted suggestions conflict with each other.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.continuity-request.v1"
SCHEMA_VERSION = 1


@dataclass
class ContinuityRequest:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    request_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    task_run_id: str = ""
    card_id: str = ""
    session_id: str = ""
    focus_entities: list[str] = field(default_factory=list)
    focus_locations: list[str] = field(default_factory=list)
    focus_turns: list[str] = field(default_factory=list)
    focus_event_stages: list[str] = field(default_factory=list)
    focus_relationship_states: list[str] = field(default_factory=list)
    focus_knowledge_boundaries: list[str] = field(default_factory=list)
    director_plan_ref: str = ""
    candidate_suggestion_refs: list[str] = field(default_factory=list)
    max_issues: int = 6
    required_evidence: bool = True
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
            "focus_entities": self.focus_entities,
            "focus_locations": self.focus_locations,
            "focus_turns": self.focus_turns,
            "focus_event_stages": self.focus_event_stages,
            "focus_relationship_states": self.focus_relationship_states,
            "focus_knowledge_boundaries": self.focus_knowledge_boundaries,
            "director_plan_ref": self.director_plan_ref,
            "candidate_suggestion_refs": self.candidate_suggestion_refs,
            "max_issues": self.max_issues,
            "required_evidence": self.required_evidence,
            "must_preserve_facts": self.must_preserve_facts,
            "must_not_do": self.must_not_do,
            "budget": self.budget, "deadline": self.deadline,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContinuityRequest:
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
            focus_locations=data.get("focus_locations", []),
            focus_turns=data.get("focus_turns", []),
            focus_event_stages=data.get("focus_event_stages", []),
            focus_relationship_states=data.get("focus_relationship_states", []),
            focus_knowledge_boundaries=data.get("focus_knowledge_boundaries", []),
            director_plan_ref=data.get("director_plan_ref", ""),
            candidate_suggestion_refs=data.get("candidate_suggestion_refs", []),
            max_issues=data.get("max_issues", 6),
            required_evidence=data.get("required_evidence", True),
            must_preserve_facts=data.get("must_preserve_facts", []),
            must_not_do=data.get("must_not_do", []),
            budget=data.get("budget", 1000),
            deadline=data.get("deadline", ""),
            created_at=data.get("created_at", ""),
        )
