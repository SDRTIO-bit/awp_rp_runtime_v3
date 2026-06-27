"""AgentExecutionReport — per-agent execution report for D-Integration tracing.

schemaId: awp.rp.agent-execution-report.v1

Records trigger/skip/timeout/budget/outcome for each agent in a turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

SCHEMA_ID = "awp.rp.agent-execution-report.v1"
SCHEMA_VERSION = 1


class AgentExecutionOutcome(str, Enum):
    """Outcome of agent execution."""
    SUCCESS = "success"
    NO_TRIGGER = "no_trigger"
    SKIPPED_BUDGET = "skipped_budget"
    SKIPPED_PRIORITY = "skipped_priority"
    SKIPPED_POLICY = "skipped_policy"
    TIMEOUT = "timeout"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass
class AgentExecutionReport:
    """Report for a single agent's execution within a turn."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    agent_role: str = ""
    task_id: str = ""
    task_run_id: str = ""
    trace_id: str = ""

    triggered: bool = False
    trigger_reasons: list[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""

    outcome: AgentExecutionOutcome = AgentExecutionOutcome.NO_TRIGGER
    suggestion_count: int = 0
    adopted_count: int = 0
    rejected_count: int = 0

    duration_ms: int = 0
    tool_calls_made: int = 0
    tokens_used: int = 0
    timeout_occurred: bool = False
    budget_exceeded: bool = False

    wave: str = ""  # "wave_a" or "wave_b"
    priority_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "agent_role": self.agent_role,
            "task_id": self.task_id,
            "task_run_id": self.task_run_id,
            "trace_id": self.trace_id,
            "triggered": self.triggered,
            "trigger_reasons": self.trigger_reasons,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "outcome": self.outcome.value,
            "suggestion_count": self.suggestion_count,
            "adopted_count": self.adopted_count,
            "rejected_count": self.rejected_count,
            "duration_ms": self.duration_ms,
            "tool_calls_made": self.tool_calls_made,
            "tokens_used": self.tokens_used,
            "timeout_occurred": self.timeout_occurred,
            "budget_exceeded": self.budget_exceeded,
            "wave": self.wave,
            "priority_score": self.priority_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentExecutionReport:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            agent_role=data.get("agent_role", ""),
            task_id=data.get("task_id", ""),
            task_run_id=data.get("task_run_id", ""),
            trace_id=data.get("trace_id", ""),
            triggered=data.get("triggered", False),
            trigger_reasons=data.get("trigger_reasons", []),
            skipped=data.get("skipped", False),
            skip_reason=data.get("skip_reason", ""),
            outcome=AgentExecutionOutcome(data.get("outcome", "no_trigger")),
            suggestion_count=data.get("suggestion_count", 0),
            adopted_count=data.get("adopted_count", 0),
            rejected_count=data.get("rejected_count", 0),
            duration_ms=data.get("duration_ms", 0),
            tool_calls_made=data.get("tool_calls_made", 0),
            tokens_used=data.get("tokens_used", 0),
            timeout_occurred=data.get("timeout_occurred", False),
            budget_exceeded=data.get("budget_exceeded", False),
            wave=data.get("wave", ""),
            priority_score=data.get("priority_score", 0.0),
        )
