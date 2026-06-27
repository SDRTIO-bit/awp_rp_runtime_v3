"""DynamicSubAgentPool — manages dynamic sub-agent execution.

Sub-agents run within strict envelopes. They cannot write state, memory,
or delegate further. Each task gets its own trace.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..contracts.delegation_plan import DelegationPlan, DelegationTask
from ..contracts.agent_task_envelope import AgentTaskEnvelope
from ..contracts.agent_suggestion import AgentSuggestion
from ..contracts.agent_execution_result import AgentExecutionResult
from ..contracts.round_snapshot import RoundSnapshot
from .agent_runtime_registry import AgentRuntimeRegistry
from .task_envelope_builder import TaskEnvelopeBuilder
from .tool_permission_runtime import ToolPermissionRuntime


class DynamicSubAgentPool:
    """Manages dynamic sub-agent execution with strict constraints."""

    def __init__(
        self,
        registry: AgentRuntimeRegistry,
        envelope_builder: TaskEnvelopeBuilder,
        tool_permission: ToolPermissionRuntime | None = None,
    ):
        self.registry = registry
        self.envelope_builder = envelope_builder
        self.tool_permission = tool_permission or ToolPermissionRuntime()

    def execute(
        self,
        plan: DelegationPlan,
        snapshot: RoundSnapshot,
    ) -> list[AgentExecutionResult]:
        """Execute all tasks in the delegation plan.

        Returns list of execution results. Empty plan → empty results.
        """
        if not plan.tasks:
            return []

        results: list[AgentExecutionResult] = []
        tokens_budget_used = 0

        for task in plan.tasks:
            # Budget check (use allocated budget, not actual usage)
            if tokens_budget_used + task.max_tokens > plan.total_token_budget:
                results.append(AgentExecutionResult(
                    task_id=task.task_id, role=task.role,
                    trace_id=plan.trace_id,
                    error_message="Budget exceeded",
                    degraded=True,
                ))
                continue

            # Validate role
            if not self.registry.is_registered(task.role):
                results.append(AgentExecutionResult(
                    task_id=task.task_id, role=task.role,
                    trace_id=plan.trace_id,
                    error_message=f"Unknown role: {task.role}",
                ))
                continue

            # Build envelope
            envelope = self.envelope_builder.build(task, snapshot, plan.brief_id)
            if not envelope:
                results.append(AgentExecutionResult(
                    task_id=task.task_id, role=task.role,
                    trace_id=plan.trace_id,
                    error_message="Failed to build envelope",
                ))
                continue

            # Execute
            result = self._execute_single(task, envelope)
            tokens_budget_used += task.max_tokens  # Track allocated budget
            results.append(result)

        return results

    def _execute_single(
        self, task: DelegationTask, envelope: AgentTaskEnvelope
    ) -> AgentExecutionResult:
        """Execute a single sub-agent task."""
        runner = self.registry.get_runner(task.role)
        if not runner:
            return AgentExecutionResult(
                task_run_id=envelope.task_run_id,
                task_id=task.task_id, role=task.role,
                trace_id=envelope.trace_id,
                error_message=f"No runner registered for role: {task.role}",
            )

        try:
            suggestions = runner.run(envelope)

            # Validate suggestions
            valid_suggestions = []
            for sug in suggestions:
                errors = self.registry.validate_suggestion_kinds(
                    task.role, [sug.kind]
                )
                if errors:
                    continue  # Skip invalid suggestions
                valid_suggestions.append(sug)

            return AgentExecutionResult(
                task_run_id=envelope.task_run_id,
                task_id=task.task_id, role=task.role,
                trace_id=envelope.trace_id,
                success=True,
                suggestions=valid_suggestions,
            )
        except Exception as e:
            return AgentExecutionResult(
                task_run_id=envelope.task_run_id,
                task_id=task.task_id, role=task.role,
                trace_id=envelope.trace_id,
                error_message=str(e),
            )
