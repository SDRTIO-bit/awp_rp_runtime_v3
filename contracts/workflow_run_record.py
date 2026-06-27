"""WorkflowRunRecord — top-level identity for a single AWP workflow execution.

schemaId: awp.rp.workflow-run-record.v1

Binds together:
  workflowRunId  = AWP business run identity
  promptId       = ComfyUI scheduler identity
  turnId         = RP round identity
  attemptId      = retry / resume attempt identity

The four IDs must never be conflated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SCHEMA_ID = "awp.rp.workflow-run-record.v1"
SCHEMA_VERSION = 1


@dataclass
class WorkflowRunContext:
    """Unified run correlation context passed through all nodes.

    Nodes must not read promptId from ComfyUI global environment.
    This context is the single source of truth for run identity.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    # Identity quartet — must never be conflated
    workflow_run_id: str = ""    # AWP business run identity
    trace_id: str = ""           # Distributed trace identity
    turn_id: str = ""            # RP round identity
    attempt_id: str = ""         # Retry / resume attempt identity

    # ComfyUI binding (set by test executor, not by nodes)
    prompt_id: str = ""          # ComfyUI scheduler identity

    # Card context
    card_id: str = ""
    logical_card_id: str = ""
    card_version: str = ""
    session_id: str = ""

    # Workflow definition
    workflow_definition_hash: str = ""

    # Timing
    started_at: str = ""

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "workflow_run_id": self.workflow_run_id,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "attempt_id": self.attempt_id,
            "prompt_id": self.prompt_id,
            "card_id": self.card_id,
            "logical_card_id": self.logical_card_id,
            "card_version": self.card_version,
            "session_id": self.session_id,
            "workflow_definition_hash": self.workflow_definition_hash,
            "started_at": self.started_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowRunContext:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            workflow_run_id=data.get("workflow_run_id", ""),
            trace_id=data.get("trace_id", ""),
            turn_id=data.get("turn_id", ""),
            attempt_id=data.get("attempt_id", ""),
            prompt_id=data.get("prompt_id", ""),
            card_id=data.get("card_id", ""),
            logical_card_id=data.get("logical_card_id", ""),
            card_version=data.get("card_version", ""),
            session_id=data.get("session_id", ""),
            workflow_definition_hash=data.get("workflow_definition_hash", ""),
            started_at=data.get("started_at", ""),
        )


@dataclass
class WorkflowRunRecord:
    """Immutable record of a completed workflow run.

    Created at run start, finalized at run end.
    Contains the full context plus outcome summary.
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    context: WorkflowRunContext = field(default_factory=WorkflowRunContext)

    # Outcome
    outcome: str = "pending"  # pending | success | failure | timeout | cancelled
    error_summary: str = ""

    # Timing
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0

    # Node summary
    total_nodes: int = 0
    executed_nodes: int = 0
    cached_nodes: int = 0
    failed_nodes: int = 0
    blocked_nodes: int = 0
    not_reached_nodes: int = 0

    def __post_init__(self) -> None:
        if not self.started_at:
            self.started_at = self.context.started_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "context": self.context.to_dict(),
            "outcome": self.outcome,
            "error_summary": self.error_summary,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "total_nodes": self.total_nodes,
            "executed_nodes": self.executed_nodes,
            "cached_nodes": self.cached_nodes,
            "failed_nodes": self.failed_nodes,
            "blocked_nodes": self.blocked_nodes,
            "not_reached_nodes": self.not_reached_nodes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowRunRecord:
        ctx_data = data.get("context", {})
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            context=WorkflowRunContext.from_dict(ctx_data),
            outcome=data.get("outcome", "pending"),
            error_summary=data.get("error_summary", ""),
            started_at=data.get("started_at", ""),
            finished_at=data.get("finished_at", ""),
            duration_ms=data.get("duration_ms", 0),
            total_nodes=data.get("total_nodes", 0),
            executed_nodes=data.get("executed_nodes", 0),
            cached_nodes=data.get("cached_nodes", 0),
            failed_nodes=data.get("failed_nodes", 0),
            blocked_nodes=data.get("blocked_nodes", 0),
            not_reached_nodes=data.get("not_reached_nodes", 0),
        )
