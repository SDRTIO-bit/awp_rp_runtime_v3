"""DynamicAgentScheduler — wave-based scheduling for D1-D5 agents.

Separates agents into Wave A (D1-D4, writer-pre, concurrent) and
Wave B (D5 Continuity, barrier after Wave A). Determines which agents
to trigger based on DelegationPlan, DirectorPlan risk flags, and budget.

Priority ordering for deterministic skip when over budget:
  explicit history reference / fact risk
  > player agency risk
  > continuity risk
  > relationship boundary risk
  > unresolved promise / secret
  > world-life atmosphere
  > ordinary opportunity
"""

from __future__ import annotations

from ..contracts.delegation_plan import DelegationPlan, DelegationTask
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.director_plan import DirectorPlan
from .turn_agent_budget_policy import TurnAgentBudgetPolicy
from .agent_runtime_registry import AgentRuntimeRegistry

# Wave A roles: writer-pre, can run concurrently
WAVE_A_ROLES = {"history-recall", "opportunity", "world-life", "emotion-relationship"}

# Wave B roles: continuity barrier, runs after Wave A
WAVE_B_ROLES = {"continuity"}

# D6 is NEVER in pre-writer scheduling
EXCLUDED_PRE_WRITER_ROLES = {"memory-curator"}

# Priority ordering for deterministic skip
ROLE_PRIORITY: dict[str, float] = {
    "history-recall": 1.0,       # highest: explicit history / fact risk
    "continuity": 0.95,          # player agency / continuity risk
    "emotion-relationship": 0.7, # relationship boundary
    "opportunity": 0.6,          # unresolved promise / secret
    "world-life": 0.5,           # atmosphere / world activity
}


class ScheduledWave:
    """Result of scheduling: which agents go in which wave."""

    def __init__(self):
        self.wave_a_tasks: list[DelegationTask] = []
        self.wave_b_tasks: list[DelegationTask] = []
        self.skipped_tasks: list[tuple[DelegationTask, str]] = []  # (task, reason)
        self.policy: TurnAgentBudgetPolicy | None = None


class DynamicAgentScheduler:
    """Deterministic wave-based agent scheduler."""

    def __init__(
        self,
        registry: AgentRuntimeRegistry | None = None,
        policy: TurnAgentBudgetPolicy | None = None,
    ):
        self.registry = registry or AgentRuntimeRegistry()
        self.policy = policy or TurnAgentBudgetPolicy()

    def schedule(
        self,
        plan: DelegationPlan,
        snapshot: RoundSnapshot,
        director_plan: DirectorPlan | None = None,
    ) -> ScheduledWave:
        """Schedule tasks into Wave A and Wave B.

        Filters out memory-curator (D6) and unknown roles.
        Sorts by priority, enforces budget limits.
        """
        result = ScheduledWave()
        result.policy = self.policy

        # Filter and classify tasks
        wave_a_candidates: list[tuple[DelegationTask, float]] = []
        wave_b_candidates: list[tuple[DelegationTask, float]] = []

        for task in plan.tasks:
            # Never schedule memory-curator in pre-writer
            if task.role in EXCLUDED_PRE_WRITER_ROLES:
                result.skipped_tasks.append((task, "memory-curator excluded from pre-writer"))
                continue

            # Validate role is registered
            if not self.registry.is_registered(task.role):
                result.skipped_tasks.append((task, f"unknown role: {task.role}"))
                continue

            # Classify into wave
            priority = ROLE_PRIORITY.get(task.role, 0.3)
            if task.role in WAVE_A_ROLES:
                wave_a_candidates.append((task, priority))
            elif task.role in WAVE_B_ROLES:
                wave_b_candidates.append((task, priority))
            else:
                result.skipped_tasks.append((task, f"role not in any wave: {task.role}"))

        # Sort by priority descending (deterministic)
        wave_a_candidates.sort(key=lambda x: (-x[1], x[0].task_id))
        wave_b_candidates.sort(key=lambda x: (-x[1], x[0].task_id))

        # Enforce budget: Wave A
        scheduled_count = 0
        for task, priority in wave_a_candidates:
            if scheduled_count >= self.policy.wave_a_max_agents:
                result.skipped_tasks.append((task, "wave_a budget exceeded"))
                continue
            if scheduled_count >= self.policy.max_agents_per_turn:
                result.skipped_tasks.append((task, "max_agents_per_turn exceeded"))
                continue
            result.wave_a_tasks.append(task)
            scheduled_count += 1

        # Enforce budget: Wave B (continuity)
        for task, priority in wave_b_candidates:
            if scheduled_count >= self.policy.max_agents_per_turn:
                result.skipped_tasks.append((task, "max_agents_per_turn exceeded"))
                continue
            if self.policy.wave_b_max_agents <= 0:
                result.skipped_tasks.append((task, "wave_b disabled for this turn"))
                continue
            result.wave_b_tasks.append(task)
            scheduled_count += 1

        return result
