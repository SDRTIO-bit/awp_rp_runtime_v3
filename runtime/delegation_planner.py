"""DelegationPlanner — validates DelegationPlan against policy."""

from __future__ import annotations

from ..contracts.delegation_plan import DelegationPlan
from ..runtime.agent_runtime_registry import AgentRuntimeRegistry


class DelegationValidation:
    def __init__(self, valid: bool, errors: list[str]):
        self.valid = valid
        self.errors = errors


class DelegationPlanner:

    def __init__(self, registry: AgentRuntimeRegistry | None = None):
        self.registry = registry or AgentRuntimeRegistry()

    def validate_and_filter(self, plan: DelegationPlan) -> tuple[DelegationPlan, DelegationValidation]:
        errors = []

        # Validate task count
        if len(plan.tasks) > plan.max_task_count:
            errors.append(f"Too many tasks: {len(plan.tasks)} > {plan.max_task_count}")

        # Validate roles
        valid_tasks = []
        for task in plan.tasks:
            if not self.registry.is_registered(task.role):
                errors.append(f"Unknown role: {task.role}")
            else:
                valid_tasks.append(task)

        if errors:
            filtered = DelegationPlan(
                plan_id=plan.plan_id, trace_id=plan.trace_id,
                snapshot_id=plan.snapshot_id, brief_id=plan.brief_id,
                card_id=plan.card_id, session_id=plan.session_id,
                tasks=valid_tasks,
                max_task_count=plan.max_task_count,
                total_token_budget=plan.total_token_budget,
            )
            return filtered, DelegationValidation(False, errors)

        return plan, DelegationValidation(True, [])
