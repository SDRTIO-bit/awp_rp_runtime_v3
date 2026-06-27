"""TurnAgentBudgetReport — per-turn budget report for D-Integration.

schemaId: awp.rp.turn-agent-budget-report.v1

Records budget allocation and consumption for all agents in a turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.rp.turn-agent-budget-report.v1"
SCHEMA_VERSION = 1


@dataclass
class TurnAgentBudgetReport:
    """Budget report for all agents in a single turn."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    turn_id: str = ""
    trace_id: str = ""

    # Configuration
    max_agents_per_turn: int = 3
    max_parallel_agents: int = 3
    max_tool_calls_per_turn: int = 20
    max_tool_calls_per_agent: int = 5
    max_agent_output_chars: int = 5000
    agent_timeout_ms: int = 30000
    turn_deadline_ms: int = 120000
    max_retries_per_agent: int = 1

    # Actual usage
    agents_scheduled: int = 0
    agents_executed: int = 0
    agents_skipped: int = 0
    agents_degraded: int = 0
    agents_failed: int = 0
    agents_timeout: int = 0

    total_tool_calls: int = 0
    total_tokens_used: int = 0
    total_duration_ms: int = 0

    wave_a_agent_count: int = 0
    wave_b_agent_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "turn_id": self.turn_id,
            "trace_id": self.trace_id,
            "max_agents_per_turn": self.max_agents_per_turn,
            "max_parallel_agents": self.max_parallel_agents,
            "max_tool_calls_per_turn": self.max_tool_calls_per_turn,
            "max_tool_calls_per_agent": self.max_tool_calls_per_agent,
            "max_agent_output_chars": self.max_agent_output_chars,
            "agent_timeout_ms": self.agent_timeout_ms,
            "turn_deadline_ms": self.turn_deadline_ms,
            "max_retries_per_agent": self.max_retries_per_agent,
            "agents_scheduled": self.agents_scheduled,
            "agents_executed": self.agents_executed,
            "agents_skipped": self.agents_skipped,
            "agents_degraded": self.agents_degraded,
            "agents_failed": self.agents_failed,
            "agents_timeout": self.agents_timeout,
            "total_tool_calls": self.total_tool_calls,
            "total_tokens_used": self.total_tokens_used,
            "total_duration_ms": self.total_duration_ms,
            "wave_a_agent_count": self.wave_a_agent_count,
            "wave_b_agent_count": self.wave_b_agent_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TurnAgentBudgetReport:
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            turn_id=data.get("turn_id", ""),
            trace_id=data.get("trace_id", ""),
            max_agents_per_turn=data.get("max_agents_per_turn", 3),
            max_parallel_agents=data.get("max_parallel_agents", 3),
            max_tool_calls_per_turn=data.get("max_tool_calls_per_turn", 20),
            max_tool_calls_per_agent=data.get("max_tool_calls_per_agent", 5),
            max_agent_output_chars=data.get("max_agent_output_chars", 5000),
            agent_timeout_ms=data.get("agent_timeout_ms", 30000),
            turn_deadline_ms=data.get("turn_deadline_ms", 120000),
            max_retries_per_agent=data.get("max_retries_per_agent", 1),
            agents_scheduled=data.get("agents_scheduled", 0),
            agents_executed=data.get("agents_executed", 0),
            agents_skipped=data.get("agents_skipped", 0),
            agents_degraded=data.get("agents_degraded", 0),
            agents_failed=data.get("agents_failed", 0),
            agents_timeout=data.get("agents_timeout", 0),
            total_tool_calls=data.get("total_tool_calls", 0),
            total_tokens_used=data.get("total_tokens_used", 0),
            total_duration_ms=data.get("total_duration_ms", 0),
            wave_a_agent_count=data.get("wave_a_agent_count", 0),
            wave_b_agent_count=data.get("wave_b_agent_count", 0),
        )
