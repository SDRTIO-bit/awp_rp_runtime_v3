"""DynamicAgentWaveExecutor — executes Wave A and Wave B agents.

Wave A: D1-D4 agents execute concurrently (within parallelism limits).
Wave B: D5 Continuity executes after Wave A results are normalized.
The barrier between waves ensures Continuity sees all Wave A suggestions.
"""

from __future__ import annotations

import time
import uuid

from ..contracts.delegation_plan import DelegationTask
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.agent_execution_result import AgentExecutionResult
from ..contracts.agent_execution_report import AgentExecutionReport, AgentExecutionOutcome
from ..contracts.turn_agent_budget_report import TurnAgentBudgetReport
from .dynamic_subagent_pool import DynamicSubAgentPool
from .turn_agent_budget_policy import TurnAgentBudgetPolicy
from .dynamic_agent_scheduler import ScheduledWave


class WaveExecutionResult:
    """Result of executing one wave."""

    def __init__(self):
        self.execution_results: list[AgentExecutionResult] = []
        self.reports: list[AgentExecutionReport] = []
        self.all_succeeded: bool = True
        self.any_degraded: bool = False


class DynamicAgentWaveExecutor:
    """Executes scheduled waves of agents with budget enforcement."""

    def __init__(
        self,
        subagent_pool: DynamicSubAgentPool,
        policy: TurnAgentBudgetPolicy | None = None,
    ):
        self.subagent_pool = subagent_pool
        self.policy = policy or TurnAgentBudgetPolicy()

    def execute_waves(
        self,
        scheduled: ScheduledWave,
        snapshot: RoundSnapshot,
        budget_report: TurnAgentBudgetReport,
        brief_id: str = "",
    ) -> tuple[list[AgentExecutionResult], list[AgentExecutionReport]]:
        """Execute Wave A then Wave B, returning all results and reports.

        Returns:
            (all_execution_results, all_reports)
        """
        all_results: list[AgentExecutionResult] = []
        all_reports: list[AgentExecutionReport] = []

        # Wave A
        wave_a_result = self._execute_wave(
            tasks=scheduled.wave_a_tasks,
            snapshot=snapshot,
            wave="wave_a",
            budget_report=budget_report,
            brief_id=brief_id,
        )
        all_results.extend(wave_a_result.execution_results)
        all_reports.extend(wave_a_result.reports)
        budget_report.wave_a_agent_count = len(scheduled.wave_a_tasks)

        # ── Continuity Barrier ──
        # Wave B only runs if Wave A produced suggestions to check
        wave_a_suggestions = sum(
            len(r.suggestions) for r in wave_a_result.execution_results if r.success
        )
        if scheduled.wave_b_tasks and wave_a_suggestions > 0:
            wave_b_result = self._execute_wave(
                tasks=scheduled.wave_b_tasks,
                snapshot=snapshot,
                wave="wave_b",
                budget_report=budget_report,
                brief_id=brief_id,
            )
            all_results.extend(wave_b_result.execution_results)
            all_reports.extend(wave_b_result.reports)
            budget_report.wave_b_agent_count = len(scheduled.wave_b_tasks)
        elif scheduled.wave_b_tasks:
            # Skip Wave B if no Wave A suggestions
            for task in scheduled.wave_b_tasks:
                report = AgentExecutionReport(
                    agent_role=task.role,
                    task_id=task.task_id,
                    trace_id=snapshot.trace_id,
                    skipped=True,
                    skip_reason="No Wave A suggestions to check",
                    outcome=AgentExecutionOutcome.SKIPPED_POLICY,
                    wave="wave_b",
                )
                all_reports.append(report)
                budget_report.agents_skipped += 1

        # Record skipped tasks from scheduling
        for task, reason in scheduled.skipped_tasks:
            report = AgentExecutionReport(
                agent_role=task.role,
                task_id=task.task_id,
                trace_id=snapshot.trace_id,
                skipped=True,
                skip_reason=reason,
                outcome=AgentExecutionOutcome.SKIPPED_BUDGET,
                wave="scheduled_skip",
            )
            all_reports.append(report)
            budget_report.agents_skipped += 1

        return all_results, all_reports

    def _execute_wave(
        self,
        tasks: list[DelegationTask],
        snapshot: RoundSnapshot,
        wave: str,
        budget_report: TurnAgentBudgetReport,
        brief_id: str,
    ) -> WaveExecutionResult:
        """Execute a single wave of tasks."""
        result = WaveExecutionResult()

        # Build a mini DelegationPlan for the pool
        from ..contracts.delegation_plan import DelegationPlan

        mini_plan = DelegationPlan(
            plan_id=f"wave_{wave}_{uuid.uuid4().hex[:8]}",
            trace_id=snapshot.trace_id,
            snapshot_id=snapshot.snapshot_id,
            brief_id=brief_id,
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            tasks=tasks,
            max_task_count=len(tasks),
            total_token_budget=sum(t.max_tokens for t in tasks),
        )

        start_time = time.monotonic()

        # Execute via pool
        exec_results = self.subagent_pool.execute(mini_plan, snapshot)

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        for i, exec_result in enumerate(exec_results):
            task = tasks[i] if i < len(tasks) else None
            budget_report.agents_executed += 1

            # Determine outcome
            if exec_result.success:
                outcome = AgentExecutionOutcome.SUCCESS
                budget_report.total_tool_calls += exec_result.tool_calls_made
                budget_report.total_tokens_used += exec_result.tokens_used
            elif exec_result.degraded:
                outcome = AgentExecutionOutcome.DEGRADED
                budget_report.agents_degraded += 1
                result.any_degraded = True
            elif "timeout" in (exec_result.error_message or "").lower():
                outcome = AgentExecutionOutcome.TIMEOUT
                budget_report.agents_timeout += 1
                result.all_succeeded = False
            elif "budget" in (exec_result.error_message or "").lower():
                outcome = AgentExecutionOutcome.SKIPPED_BUDGET
                budget_report.agents_skipped += 1
            else:
                outcome = AgentExecutionOutcome.FAILED
                budget_report.agents_failed += 1
                result.all_succeeded = False

            report = AgentExecutionReport(
                agent_role=exec_result.role,
                task_id=exec_result.task_id,
                task_run_id=exec_result.task_run_id,
                trace_id=exec_result.trace_id,
                triggered=True,
                outcome=outcome,
                suggestion_count=len(exec_result.suggestions),
                duration_ms=exec_result.duration_ms or elapsed_ms,
                tool_calls_made=exec_result.tool_calls_made,
                tokens_used=exec_result.tokens_used,
                wave=wave,
            )
            result.execution_results.append(exec_result)
            result.reports.append(report)

        budget_report.total_duration_ms += elapsed_ms
        return result
