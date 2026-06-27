"""P2 Tests: AgentRuntimeRegistry."""

import pytest
from awp_rp_runtime_v2.runtime.agent_runtime_registry import (
    AgentRuntimeRegistry, AgentRoleSpec, AgentRunner,
)
from awp_rp_runtime_v2.contracts.agent_suggestion import SuggestionKind


class TestAgentRuntimeRegistry:

    def test_builtin_roles_registered(self):
        registry = AgentRuntimeRegistry()
        assert registry.is_registered("continuity-checker")
        assert registry.is_registered("worldbook-researcher")
        assert registry.is_registered("emotion-relationship-analyst")
        assert registry.is_registered("memory-curator")
        assert registry.is_registered("state-updater")
        assert registry.is_registered("rp-critic")

    def test_unknown_role_rejected(self):
        registry = AgentRuntimeRegistry()
        assert not registry.is_registered("unknown-role")

    def test_validate_suggestion_kinds(self):
        registry = AgentRuntimeRegistry()
        # continuity-checker can produce CONTINUITY_ISSUE
        errors = registry.validate_suggestion_kinds(
            "continuity-checker", [SuggestionKind.CONTINUITY_ISSUE]
        )
        assert errors == []

        # continuity-checker cannot produce MEMORY_CANDIDATE
        errors = registry.validate_suggestion_kinds(
            "continuity-checker", [SuggestionKind.MEMORY_CANDIDATE]
        )
        assert len(errors) == 1

    def test_register_runner_requires_known_role(self):
        registry = AgentRuntimeRegistry()
        with pytest.raises(ValueError, match="unknown role"):
            registry.register_runner("fake-role", None)

    def test_can_delegate_false_for_all(self):
        registry = AgentRuntimeRegistry()
        for role in registry.get_all_roles():
            spec = registry.get_spec(role)
            assert spec.can_delegate is False
            assert spec.can_write_state is False
            assert spec.can_write_memory is False
            assert spec.can_generate_final_text is False
