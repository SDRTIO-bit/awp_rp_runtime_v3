"""P2 Tests: DynamicSubAgentPool, TaskEnvelopeBuilder, ToolPermission."""

import pytest
from awp_rp_runtime_v3.runtime.agent_runtime_registry import (
    AgentRuntimeRegistry, AgentRunner,
)
from awp_rp_runtime_v3.runtime.task_envelope_builder import TaskEnvelopeBuilder
from awp_rp_runtime_v3.runtime.dynamic_subagent_pool import DynamicSubAgentPool
from awp_rp_runtime_v3.runtime.tool_permission_runtime import ToolPermissionRuntime
from awp_rp_runtime_v3.contracts.agent_task_envelope import AgentTaskEnvelope
from awp_rp_runtime_v3.contracts.agent_suggestion import AgentSuggestion, SuggestionKind
from awp_rp_runtime_v3.contracts.delegation_plan import DelegationPlan, DelegationTask
from awp_rp_runtime_v3.contracts.round_snapshot import RoundSnapshot
from awp_rp_runtime_v3.contracts.card_state import CardState


def _make_snapshot() -> RoundSnapshot:
    return RoundSnapshot(
        snapshot_id="snap1", trace_id="trace1",
        card_id="c1", session_id="s1",
        base_card_state_revision=0,
        card_state=CardState(card_id="c1", session_id="s1", revision=0),
        player_input="Hello",
    )


class TestTaskEnvelopeBuilder:

    def test_envelope_crops_snapshot(self):
        registry = AgentRuntimeRegistry()
        builder = TaskEnvelopeBuilder(registry)
        snapshot = _make_snapshot()

        task = DelegationTask(
            task_id="t1", role="continuity-checker",
            input_field_allowlist=["card_state", "player_input"],
        )
        envelope = builder.build(task, snapshot, "brief1")
        assert envelope is not None
        assert "card_state" in envelope.allowed_snapshot_data
        assert envelope.player_input == "Hello"  # from snapshot

    def test_unknown_role_returns_none(self):
        registry = AgentRuntimeRegistry()
        builder = TaskEnvelopeBuilder(registry)
        task = DelegationTask(task_id="t1", role="unknown-role")
        envelope = builder.build(task, _make_snapshot())
        assert envelope is None

    def test_empty_allowlist_gives_empty_data(self):
        registry = AgentRuntimeRegistry()
        builder = TaskEnvelopeBuilder(registry)
        task = DelegationTask(task_id="t1", role="continuity-checker")
        envelope = builder.build(task, _make_snapshot())
        assert envelope.allowed_snapshot_data == {}


class TestDynamicSubAgentPool:

    def test_empty_plan_returns_empty(self):
        registry = AgentRuntimeRegistry()
        builder = TaskEnvelopeBuilder(registry)
        pool = DynamicSubAgentPool(registry, builder)

        plan = DelegationPlan(tasks=[])
        results = pool.execute(plan, _make_snapshot())
        assert results == []

    def test_unknown_role_recorded_as_failure(self):
        registry = AgentRuntimeRegistry()
        builder = TaskEnvelopeBuilder(registry)
        pool = DynamicSubAgentPool(registry, builder)

        plan = DelegationPlan(
            tasks=[DelegationTask(task_id="t1", role="unknown-role", purpose="test")],
            total_token_budget=10000,
        )
        results = pool.execute(plan, _make_snapshot())
        assert len(results) == 1
        assert not results[0].success
        assert "Unknown role" in results[0].error_message

    def test_runner_failure_recorded(self):
        registry = AgentRuntimeRegistry()
        builder = TaskEnvelopeBuilder(registry)

        class FailingRunner:
            def run(self, envelope):
                raise RuntimeError("boom")

        registry.register_runner("continuity-checker", FailingRunner())
        pool = DynamicSubAgentPool(registry, builder)

        plan = DelegationPlan(
            tasks=[DelegationTask(task_id="t1", role="continuity-checker", purpose="test")],
            total_token_budget=10000,
        )
        results = pool.execute(plan, _make_snapshot())
        assert len(results) == 1
        assert not results[0].success
        assert "boom" in results[0].error_message

    def test_successful_runner_returns_suggestions(self):
        registry = AgentRuntimeRegistry()
        builder = TaskEnvelopeBuilder(registry)

        class SuccessRunner:
            def run(self, envelope):
                return [AgentSuggestion(
                    suggestion_id="s1", kind=SuggestionKind.CONTINUITY_ISSUE,
                    summary="Found issue", confidence=0.9,
                    evidence=["Turn 3"], source_refs=["turn_record:t3"],
                )]

        registry.register_runner("continuity-checker", SuccessRunner())
        pool = DynamicSubAgentPool(registry, builder)

        plan = DelegationPlan(
            tasks=[DelegationTask(task_id="t1", role="continuity-checker", purpose="test")],
            total_token_budget=10000,
        )
        results = pool.execute(plan, _make_snapshot())
        assert len(results) == 1
        assert results[0].success
        assert len(results[0].suggestions) == 1

    def test_budget_exceeded(self):
        registry = AgentRuntimeRegistry()
        builder = TaskEnvelopeBuilder(registry)

        # Register a runner that reports some token usage
        class TokenRunner:
            def run(self, envelope):
                return []

        registry.register_runner("continuity-checker", TokenRunner())
        registry.register_runner("memory-curator", TokenRunner())

        pool = DynamicSubAgentPool(registry, builder)

        plan = DelegationPlan(
            tasks=[
                DelegationTask(task_id="t1", role="continuity-checker", max_tokens=8000),
                DelegationTask(task_id="t2", role="memory-curator", max_tokens=8000),
            ],
            total_token_budget=10000,
        )
        results = pool.execute(plan, _make_snapshot())
        assert len(results) == 2
        # Second task should be budget-exceeded since 8000 + 8000 > 10000
        assert results[1].degraded
        assert "Budget exceeded" in results[1].error_message

    def test_subagent_cannot_get_db_connection(self):
        """Test 11: sub-agent envelope has no db access."""
        registry = AgentRuntimeRegistry()
        builder = TaskEnvelopeBuilder(registry)
        task = DelegationTask(task_id="t1", role="continuity-checker")
        envelope = builder.build(task, _make_snapshot())
        # No database-related fields in envelope
        assert not hasattr(envelope, 'db_connection')
        assert not hasattr(envelope, 'store')


class TestToolPermission:

    def test_empty_tools_all_denied(self):
        tp = ToolPermissionRuntime()
        allowed, reason = tp.check_tool_call([], "state.read")
        assert not allowed

    def test_tool_in_allowlist(self):
        tp = ToolPermissionRuntime()
        allowed, _ = tp.check_tool_call(["state.read", "memory.search"], "state.read")
        assert allowed

    def test_tool_not_in_allowlist(self):
        tp = ToolPermissionRuntime()
        allowed, _ = tp.check_tool_call(["state.read"], "state.write")
        assert not allowed
