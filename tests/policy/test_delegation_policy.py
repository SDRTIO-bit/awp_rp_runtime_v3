"""Tests for DelegationPolicy — updated for P2 contract changes."""

import pytest
from awp_rp_runtime_v2.contracts.delegation_plan import DelegationPlan, DelegationTask


class TestDelegationPolicy:

    def test_empty_plan_valid(self):
        plan = DelegationPlan(tasks=[])
        assert plan.tasks == []

    def test_valid_task(self):
        task = DelegationTask(role="continuity-checker", purpose="Check consistency")
        assert task.role == "continuity-checker"

    def test_task_with_allowlist(self):
        task = DelegationTask(
            role="worldbook-researcher",
            purpose="Search worldbook",
            input_field_allowlist=["card_state", "active_worldbook_entries"],
            tool_allowlist=["worldbook.search"],
        )
        assert task.input_field_allowlist == ["card_state", "active_worldbook_entries"]

    def test_task_budget(self):
        task = DelegationTask(
            role="memory-curator", purpose="curate",
            max_tokens=500, timeout_ms=10000,
        )
        assert task.max_tokens == 500
        assert task.timeout_ms == 10000

    def test_allowed_roles(self):
        valid_roles = {
            "continuity-checker", "worldbook-researcher",
            "emotion-relationship-analyst", "memory-curator",
            "state-updater", "rp-critic",
        }
        from awp_rp_runtime_v2.runtime.agent_runtime_registry import AgentRuntimeRegistry
        registry = AgentRuntimeRegistry()
        for role in valid_roles:
            assert registry.is_registered(role)
        assert not registry.is_registered("unknown-role")
