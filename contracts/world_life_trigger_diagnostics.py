"""WorldLifeTriggerDiagnostics — diagnostics for trigger evaluation.

schemaId: awp.rp.world-life-trigger-diagnostics.v1
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.world-life-trigger-diagnostics.v1"
SCHEMA_VERSION = 1

@dataclass
class WorldLifeTriggerDiagnostics:
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    diagnostics_id: str = ""
    trace_id: str = ""
    snapshot_id: str = ""
    task_run_id: str = ""
    should_trigger: bool = False
    trigger_reasons: list[str] = field(default_factory=list)
    world_life_domains: list[str] = field(default_factory=list)
    focus_entities: list[str] = field(default_factory=list)
    focus_locations: list[str] = field(default_factory=list)
    focus_event_stages: list[str] = field(default_factory=list)
    risk_level: str = "none"
    max_candidate_count: int = 2
    tool_calls_made: int = 0
    candidates_generated: int = 0
    candidates_accepted: int = 0
    candidates_rejected: int = 0
    total_duration_ms: int = 0
    degraded: bool = False
    degraded_reasons: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id, "schema_version": self.schema_version,
            "diagnostics_id": self.diagnostics_id, "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id, "task_run_id": self.task_run_id,
            "should_trigger": self.should_trigger,
            "trigger_reasons": self.trigger_reasons,
            "world_life_domains": self.world_life_domains,
            "focus_entities": self.focus_entities,
            "focus_locations": self.focus_locations,
            "focus_event_stages": self.focus_event_stages,
            "risk_level": self.risk_level,
            "max_candidate_count": self.max_candidate_count,
            "tool_calls_made": self.tool_calls_made,
            "candidates_generated": self.candidates_generated,
            "candidates_accepted": self.candidates_accepted,
            "candidates_rejected": self.candidates_rejected,
            "total_duration_ms": self.total_duration_ms,
            "degraded": self.degraded,
            "degraded_reasons": self.degraded_reasons,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldLifeTriggerDiagnostics:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            diagnostics_id=data.get("diagnostics_id", ""),
            trace_id=data.get("trace_id", ""),
            snapshot_id=data.get("snapshot_id", ""),
            task_run_id=data.get("task_run_id", ""),
            should_trigger=data.get("should_trigger", False),
            trigger_reasons=data.get("trigger_reasons", []),
            world_life_domains=data.get("world_life_domains", []),
            focus_entities=data.get("focus_entities", []),
            focus_locations=data.get("focus_locations", []),
            focus_event_stages=data.get("focus_event_stages", []),
            risk_level=data.get("risk_level", "none"),
            max_candidate_count=data.get("max_candidate_count", 2),
            tool_calls_made=data.get("tool_calls_made", 0),
            candidates_generated=data.get("candidates_generated", 0),
            candidates_accepted=data.get("candidates_accepted", 0),
            candidates_rejected=data.get("candidates_rejected", 0),
            total_duration_ms=data.get("total_duration_ms", 0),
            degraded=data.get("degraded", False),
            degraded_reasons=data.get("degraded_reasons", []),
            created_at=data.get("created_at", ""),
        )
