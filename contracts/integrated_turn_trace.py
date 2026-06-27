"""IntegratedTurnTrace — full integration trace for D-Integration.

schemaId: awp.rp.integrated-turn-trace.v1

Aggregates agent execution reports, budget report, conflict records,
and resolution details for a complete turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agent_execution_report import AgentExecutionReport
from .turn_agent_budget_report import TurnAgentBudgetReport
from .suggestion_conflict import SuggestionConflict

SCHEMA_ID = "awp.rp.integrated-turn-trace.v1"
SCHEMA_VERSION = 1


@dataclass
class IntegratedTurnTrace:
    """Full integration trace for a single turn."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    turn_id: str = ""
    trace_id: str = ""
    card_id: str = ""
    session_id: str = ""

    # Per-agent reports
    agent_reports: list[AgentExecutionReport] = field(default_factory=list)

    # Budget
    budget_report: TurnAgentBudgetReport | None = None

    # Conflicts
    conflicts: list[SuggestionConflict] = field(default_factory=list)

    # Director resolution
    accepted_suggestion_ids: list[str] = field(default_factory=list)
    partially_accepted_suggestion_ids: list[str] = field(default_factory=list)
    rejected_suggestion_ids: list[str] = field(default_factory=list)
    rejection_reasons: dict[str, str] = field(default_factory=dict)

    # Writer input boundary
    dropped_suggestion_ids: list[str] = field(default_factory=list)
    truncated_sections: list[str] = field(default_factory=list)
    budget_reason: str = ""
    final_brief_size: int = 0

    # Timing
    total_duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "turn_id": self.turn_id,
            "trace_id": self.trace_id,
            "card_id": self.card_id,
            "session_id": self.session_id,
            "agent_reports": [r.to_dict() for r in self.agent_reports],
            "budget_report": self.budget_report.to_dict() if self.budget_report else None,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "accepted_suggestion_ids": self.accepted_suggestion_ids,
            "partially_accepted_suggestion_ids": self.partially_accepted_suggestion_ids,
            "rejected_suggestion_ids": self.rejected_suggestion_ids,
            "rejection_reasons": self.rejection_reasons,
            "dropped_suggestion_ids": self.dropped_suggestion_ids,
            "truncated_sections": self.truncated_sections,
            "budget_reason": self.budget_reason,
            "final_brief_size": self.final_brief_size,
            "total_duration_ms": self.total_duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntegratedTurnTrace:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            turn_id=data.get("turn_id", ""),
            trace_id=data.get("trace_id", ""),
            card_id=data.get("card_id", ""),
            session_id=data.get("session_id", ""),
            agent_reports=[
                AgentExecutionReport.from_dict(r) for r in data.get("agent_reports", [])
            ],
            budget_report=(
                TurnAgentBudgetReport.from_dict(data["budget_report"])
                if data.get("budget_report") else None
            ),
            conflicts=[
                SuggestionConflict.from_dict(c) for c in data.get("conflicts", [])
            ],
            accepted_suggestion_ids=data.get("accepted_suggestion_ids", []),
            partially_accepted_suggestion_ids=data.get("partially_accepted_suggestion_ids", []),
            rejected_suggestion_ids=data.get("rejected_suggestion_ids", []),
            rejection_reasons=data.get("rejection_reasons", {}),
            dropped_suggestion_ids=data.get("dropped_suggestion_ids", []),
            truncated_sections=data.get("truncated_sections", []),
            budget_reason=data.get("budget_reason", ""),
            final_brief_size=data.get("final_brief_size", 0),
            total_duration_ms=data.get("total_duration_ms", 0),
        )
