"""BudgetPolicy — token and cost budget rules.

Enforces:
- Max total tokens per turn
- Max LLM calls per turn
- Max sub-agent concurrency
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BudgetStatus:
    """Current budget status."""
    total_tokens_used: int = 0
    total_llm_calls: int = 0
    total_sub_agents_spawned: int = 0
    within_budget: bool = True
    errors: list[str] | None = None


class BudgetPolicy:
    """Policy for token and cost budgets.

    Pure policy — no side effects, no I/O.
    """

    # Default limits
    MAX_TOTAL_TOKENS = 50000
    MAX_LLM_CALLS = 10
    MAX_SUB_AGENT_CONCURRENCY = 3

    def __init__(
        self,
        max_total_tokens: int | None = None,
        max_llm_calls: int | None = None,
        max_sub_agent_concurrency: int | None = None,
    ):
        self.max_total_tokens = max_total_tokens or self.MAX_TOTAL_TOKENS
        self.max_llm_calls = max_llm_calls or self.MAX_LLM_CALLS
        self.max_sub_agent_concurrency = max_sub_agent_concurrency or self.MAX_SUB_AGENT_CONCURRENCY

    def check_budget(self, status: BudgetStatus) -> BudgetStatus:
        """Check if current usage is within budget."""
        errors = []

        if status.total_tokens_used > self.max_total_tokens:
            errors.append(
                f"Token budget exceeded: {status.total_tokens_used} > {self.max_total_tokens}"
            )

        if status.total_llm_calls > self.max_llm_calls:
            errors.append(
                f"LLM call budget exceeded: {status.total_llm_calls} > {self.max_llm_calls}"
            )

        if status.total_sub_agents_spawned > self.max_sub_agent_concurrency:
            errors.append(
                f"Sub-agent concurrency exceeded: {status.total_sub_agents_spawned} > "
                f"{self.max_sub_agent_concurrency}"
            )

        status.within_budget = len(errors) == 0
        status.errors = errors if errors else None
        return status
