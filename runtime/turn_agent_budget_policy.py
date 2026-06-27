"""TurnAgentBudgetPolicy — per-turn budget governance for dynamic agents.

Defines and enforces budget limits for agent scheduling, tool calls,
output size, timeouts, and retries. Deterministic, configurable,
safe defaults.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.turn_agent_budget_report import TurnAgentBudgetReport


@dataclass(frozen=True)
class TurnAgentBudgetPolicy:
    """Budget limits for a single turn's agent execution."""
    max_agents_per_turn: int = 3
    max_parallel_agents: int = 3
    max_tool_calls_per_turn: int = 20
    max_tool_calls_per_agent: int = 5
    max_agent_output_chars: int = 5000
    max_final_turn_brief_chars: int = 15000
    agent_timeout_ms: int = 30000
    turn_deadline_ms: int = 120000
    max_retries_per_agent: int = 1

    # Wave A: writer-pre agents (D1-D4)
    wave_a_max_agents: int = 3
    # Wave B: continuity barrier (D5)
    wave_b_max_agents: int = 1

    def create_report(self, turn_id: str = "", trace_id: str = "") -> TurnAgentBudgetReport:
        """Create a budget report initialized from this policy."""
        return TurnAgentBudgetReport(
            turn_id=turn_id,
            trace_id=trace_id,
            max_agents_per_turn=self.max_agents_per_turn,
            max_parallel_agents=self.max_parallel_agents,
            max_tool_calls_per_turn=self.max_tool_calls_per_turn,
            max_tool_calls_per_agent=self.max_tool_calls_per_agent,
            max_agent_output_chars=self.max_agent_output_chars,
            agent_timeout_ms=self.agent_timeout_ms,
            turn_deadline_ms=self.turn_deadline_ms,
            max_retries_per_agent=self.max_retries_per_agent,
        )

    def can_schedule_more(self, report: TurnAgentBudgetReport) -> bool:
        """Check if more agents can be scheduled."""
        return report.agents_scheduled < self.max_agents_per_turn

    def can_run_more_parallel(self, report: TurnAgentBudgetReport) -> bool:
        """Check if more parallel agents can run."""
        running = report.agents_executed - report.agents_skipped - report.agents_failed
        return running < self.max_parallel_agents

    def check_tool_budget(self, report: TurnAgentBudgetReport, tool_calls: int) -> bool:
        """Check if agent can make more tool calls."""
        return (report.total_tool_calls + tool_calls) <= self.max_tool_calls_per_turn


# Default policy for simple turns: 0 agents
SIMPLE_TURN_POLICY = TurnAgentBudgetPolicy(
    max_agents_per_turn=0,
    max_parallel_agents=0,
    max_tool_calls_per_turn=0,
    wave_a_max_agents=0,
    wave_b_max_agents=0,
)

# Default policy for normal turns: 1 Wave A agent, continuity only on high risk
NORMAL_TURN_POLICY = TurnAgentBudgetPolicy(
    max_agents_per_turn=1,
    max_parallel_agents=1,
    max_tool_calls_per_turn=5,
    wave_a_max_agents=1,
    wave_b_max_agents=0,  # Continuity only on high risk
)

# Default policy for complex turns: up to 3 Wave A + continuity
COMPLEX_TURN_POLICY = TurnAgentBudgetPolicy(
    max_agents_per_turn=4,  # 3 Wave A + 1 Wave B
    max_parallel_agents=3,
    max_tool_calls_per_turn=20,
    wave_a_max_agents=3,
    wave_b_max_agents=1,
)
