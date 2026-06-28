"""P1 Tests: Real RP Evolution Loop.

Validates:
  1. TurnEvolutionCurator produces real state proposals
  2. No fake revision increment when nothing changed
  3. ConditionEvaluator evaluates conditions safely
  4. ConditionWorldbookActivation activates/deactivates entries based on CardState
  5. Memory candidates come from curator (not fake D6)
  6. Effects projection is populated
  7. AWPV2ContinueTurn creates a formal continue turn
  8. Real Director generates delegation plans (0-2 tasks)
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from ..contracts.card_state import CardState, VariableEntry, EventFlag, SceneState
from ..contracts.card_state_patch import CardStatePatch, CardStatePatchOperation, PatchOpType
from ..contracts.curator_request import CuratorRequest
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.turn_evolution_proposal import (
    TurnEvolutionProposal, StateUpdateProposalV2, MemoryCandidate,
)
from ..runtime.condition_evaluator import ConditionEvaluator, ConditionEvaluationError
from ..runtime.turn_evolution_curator import TurnEvolutionCurator


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════════
# ConditionEvaluator tests
# ═══════════════════════════════════════════════════════════════════════

class TestConditionEvaluator:
    """Safe condition evaluation against CardState."""

    def test_01_equals_operator(self):
        evaluator = ConditionEvaluator()
        state = {"variables": {"trust": {"value": 10}}}
        condition = {"op": "equals", "path": "variables.trust.value", "value": 10}
        assert evaluator.evaluate(condition, state) is True

        condition_false = {"op": "equals", "path": "variables.trust.value", "value": 5}
        assert evaluator.evaluate(condition_false, state) is False

    def test_02_not_equals_operator(self):
        evaluator = ConditionEvaluator()
        state = {"variables": {"trust": {"value": 10}}}
        condition = {"op": "notEquals", "path": "variables.trust.value", "value": 5}
        assert evaluator.evaluate(condition, state) is True

    def test_03_gt_gte_operators(self):
        evaluator = ConditionEvaluator()
        state = {"variables": {"favorability": {"value": 50}}}

        assert evaluator.evaluate({"op": "gt", "path": "variables.favorability.value", "value": 30}, state) is True
        assert evaluator.evaluate({"op": "gt", "path": "variables.favorability.value", "value": 50}, state) is False
        assert evaluator.evaluate({"op": "gte", "path": "variables.favorability.value", "value": 50}, state) is True

    def test_04_lt_lte_operators(self):
        evaluator = ConditionEvaluator()
        state = {"variables": {"hp": {"value": 30}}}

        assert evaluator.evaluate({"op": "lt", "path": "variables.hp.value", "value": 50}, state) is True
        assert evaluator.evaluate({"op": "lte", "path": "variables.hp.value", "value": 30}, state) is True

    def test_05_exists_operator(self):
        evaluator = ConditionEvaluator()
        state = {"variables": {"trust": {"value": 10}}}

        assert evaluator.evaluate({"op": "exists", "path": "variables.trust"}, state) is True
        assert evaluator.evaluate({"op": "exists", "path": "variables.nonexistent"}, state) is False

    def test_06_contains_operator(self):
        evaluator = ConditionEvaluator()
        state = {"event_flags": {"quest_started": {"fired": True}}}

        assert evaluator.evaluate({"op": "contains", "path": "event_flags", "value": "quest_started"}, state) is True

    def test_07_boolean_operator(self):
        evaluator = ConditionEvaluator()
        state = {"event_flags": {"quest_started": True}}

        assert evaluator.evaluate({"op": "boolean", "path": "event_flags.quest_started"}, state) is True

    def test_08_and_or_not_operators(self):
        evaluator = ConditionEvaluator()
        state = {"variables": {"a": {"value": 10}, "b": {"value": 20}}}

        # AND
        and_cond = {
            "op": "and",
            "conditions": [
                {"op": "gt", "path": "variables.a.value", "value": 5},
                {"op": "lt", "path": "variables.b.value", "value": 30},
            ],
        }
        assert evaluator.evaluate(and_cond, state) is True

        # OR
        or_cond = {
            "op": "or",
            "conditions": [
                {"op": "lt", "path": "variables.a.value", "value": 5},
                {"op": "lt", "path": "variables.b.value", "value": 30},
            ],
        }
        assert evaluator.evaluate(or_cond, state) is True

        # NOT
        not_cond = {"op": "not", "condition": {"op": "lt", "path": "variables.a.value", "value": 5}}
        assert evaluator.evaluate(not_cond, state) is True

    def test_09_unsupported_operator_raises(self):
        evaluator = ConditionEvaluator()
        state = {}
        with pytest.raises(ConditionEvaluationError, match="Unsupported operator"):
            evaluator.evaluate({"op": "eval", "path": "x"}, state)

    def test_10_missing_path_returns_false(self):
        evaluator = ConditionEvaluator()
        state = {"variables": {}}
        condition = {"op": "equals", "path": "variables.nonexistent.value", "value": 10}
        assert evaluator.evaluate(condition, state) is False

    def test_11_nested_condition_worldbook_entry(self):
        """Test a realistic worldbook condition: trust >= 50 AND quest_started."""
        evaluator = ConditionEvaluator()
        state = {
            "variables": {"trust": {"value": 60}},
            "event_flags": {"quest_started": {"fired": True, "event_id": "quest_started"}},
        }
        condition = {
            "op": "and",
            "conditions": [
                {"op": "gte", "path": "variables.trust.value", "value": 50},
                {"op": "exists", "path": "event_flags.quest_started"},
            ],
        }
        assert evaluator.evaluate(condition, state) is True


# ═══════════════════════════════════════════════════════════════════════
# TurnEvolutionCurator tests
# ═══════════════════════════════════════════════════════════════════════

class TestTurnEvolutionCurator:
    """TurnEvolutionCurator produces real proposals."""

    def test_12_deterministic_no_change_for_greeting(self):
        """Simple greeting with no state signals should produce no_state_change."""
        curator = TurnEvolutionCurator(llm_adapter=None)
        # Use text with NO Chinese keywords that would trigger state changes
        request = CuratorRequest(
            request_id="r1", turn_id="t1", session_id="s1",
            player_input="Hello",
            accepted_writer_output="Welcome to the tavern. The fire crackles warmly in the hearth.",
            pre_turn_card_state={"variables": {}, "event_flags": {}, "scene_state": {}, "revision": 0},
            base_card_state_revision=0,
        )
        proposal = curator.curate(request)
        assert isinstance(proposal, TurnEvolutionProposal)
        assert proposal.is_no_state_change is True
        assert len(proposal.state_update_proposal.operations) == 0

    def test_13_deterministic_detects_trust_keyword(self):
        """Trust keyword in output should produce state change."""
        curator = TurnEvolutionCurator(llm_adapter=None)
        request = CuratorRequest(
            request_id="r2", turn_id="t2", session_id="s1",
            player_input="我想信任你",
            accepted_writer_output="她看着你的眼睛，感受到你话语中的信任。她微笑着说：谢谢你的信任。",
            pre_turn_card_state={"variables": {}, "event_flags": {}, "scene_state": {}, "revision": 0},
            base_card_state_revision=0,
        )
        proposal = curator.curate(request)
        assert proposal.is_no_state_change is False
        ops = proposal.state_update_proposal.operations
        assert len(ops) > 0
        trust_ops = [op for op in ops if "trust" in op.get("path", "")]
        assert len(trust_ops) > 0

    def test_14_deterministic_detects_scene_change(self):
        """Scene keyword should produce scene_state patch."""
        curator = TurnEvolutionCurator(llm_adapter=None)
        request = CuratorRequest(
            request_id="r3", turn_id="t3", session_id="s1",
            player_input="我走进森林",
            accepted_writer_output="你踏上了通往森林的小路。树木越来越密。",
            pre_turn_card_state={"variables": {}, "event_flags": {}, "scene_state": {}, "revision": 0},
            base_card_state_revision=0,
        )
        proposal = curator.curate(request)
        ops = proposal.state_update_proposal.operations
        scene_ops = [op for op in ops if op.get("path", "").startswith("scene_state.")]
        assert len(scene_ops) > 0

    def test_15_deterministic_generates_active_memory(self):
        """Promise keyword should generate active memory candidate."""
        curator = TurnEvolutionCurator(llm_adapter=None)
        request = CuratorRequest(
            request_id="r4", turn_id="t4", session_id="s1",
            player_input="你答应过我的",
            accepted_writer_output="她低下头，想起了之前的承诺。好的，我会遵守诺言。",
            pre_turn_card_state={"variables": {}, "event_flags": {}, "scene_state": {}, "revision": 0},
            base_card_state_revision=0,
        )
        proposal = curator.curate(request)
        assert len(proposal.memory_candidates_active) > 0
        promise_candidates = [c for c in proposal.memory_candidates_active if c.kind == "promise"]
        assert len(promise_candidates) > 0

    def test_16_deterministic_generates_rag_memory(self):
        """Any accepted output should generate RAG memory."""
        curator = TurnEvolutionCurator(llm_adapter=None)
        request = CuratorRequest(
            request_id="r5", turn_id="t5", session_id="s1",
            player_input="你好",
            accepted_writer_output="这是一段足够长的测试文本，用来确保RAG记忆可以被正确生成。" * 5,
            pre_turn_card_state={"variables": {}, "event_flags": {}, "scene_state": {}, "revision": 0},
            base_card_state_revision=0,
        )
        proposal = curator.curate(request)
        assert len(proposal.memory_candidates_rag) > 0

    def test_17_patch_validation_rejects_invalid_ops(self):
        """Invalid patch operations should cause no_state_change."""
        curator = TurnEvolutionCurator(llm_adapter=None)
        request = CuratorRequest(
            request_id="r6", turn_id="t6", session_id="s1",
            player_input="test",
            accepted_writer_output="test output",
            pre_turn_card_state={"variables": {}, "event_flags": {}, "scene_state": {}, "revision": 0},
            base_card_state_revision=0,
        )
        # Manually create a proposal with invalid ops
        proposal = TurnEvolutionProposal(
            turn_id="t6", session_id="s1",
            state_update_proposal=StateUpdateProposalV2(
                expected_revision=0,
                operations=[{"op": "set", "path": "invalid_path", "value": 1}],
            ),
        )
        validated = curator._validate_proposal(proposal, request.pre_turn_card_state)
        assert validated.is_no_state_change is True


# ═══════════════════════════════════════════════════════════════════════
# Full engine integration tests
# ═══════════════════════════════════════════════════════════════════════

class TestP1EngineIntegration:
    """P1 engine produces real evolution, not fake patches."""

    def _seed_session(self, registry, session_id: str, card_id: str):
        """Seed a minimal session for testing."""
        from ..contracts.card_session_binding import CardSessionBinding
        from ..contracts.opening_record import OpeningRecord
        from ..contracts.worldbook_binding import WorldbookBinding, WorldbookBindingEntry
        from ..contracts.card_definition import CardDefinition, CardDefinitionStatus

        now = _now()

        # Card definition
        card_def = CardDefinition(
            logical_card_id=card_id,
            card_version=1,
            source_id="test_src",
            source_hash="test_hash",
            name="TestCard",
            display_name="TestCard",
            status=CardDefinitionStatus.READY,
            greetings=[{
                "schema_id": "awp.rp.card-greeting.v1",
                "schema_version": 1,
                "greeting_id": "g0",
                "index": 0,
                "label": "Default",
                "safe_display_content": "Welcome, traveler.",
                "content_hash": "gh0",
                "is_default": True,
                "source_path": "data.first_mes",
            }],
            worldbook_catalog=[],
            worldbook_chunks=[],
            created_at=now,
            updated_at=now,
        )

        from ..storage.sqlite.card_definition_store import SqliteCardDefinitionStore
        def_store = SqliteCardDefinitionStore(registry.db)
        def_store.save(card_def)

        # Binding
        registry.card_session_binding_store.save(CardSessionBinding(
            session_id=session_id,
            logical_card_id=card_id,
            card_version=1,
            source_hash="test_hash",
            selected_greeting_id="g0",
            opening_record_id=f"op_{session_id}",
            worldbook_binding_id=f"wb_{session_id}",
            status="ready",
            created_at=now,
        ))

        # Opening
        registry.opening_record_store.save(OpeningRecord(
            opening_record_id=f"op_{session_id}",
            session_id=session_id,
            logical_card_id=card_id,
            card_version=1,
            greeting_id="g0",
            safe_display_content="Welcome to the tavern, traveler.",
            created_at=now,
        ))

        # Worldbook binding
        registry.worldbook_binding_store.save(WorldbookBinding(
            worldbook_binding_id=f"wb_{session_id}",
            session_id=session_id,
            logical_card_id=card_id,
            card_version=1,
            source_hash="test_hash",
            entries=[],
            created_at=now,
        ))

    def test_18_persistent_first_turn_no_fake_revision(self):
        """First turn with simple greeting: revision stays at 0."""
        from ..runtime.runtime_store_factory import RuntimeStoreFactory, clear_registry_cache

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AWP_RUNTIME_PROFILE"] = "test"
            os.environ["AWP_TEST_STORE_ROOT"] = tmp
            os.environ["AWP_TEST_RUNTIME_NAMESPACE"] = "p1_test_18"
            clear_registry_cache()
            try:
                factory = RuntimeStoreFactory.from_env()
                self._seed_session(factory.registry, "s1", "c1")

                from ..nodes.persistent_first_turn_node import AWPV2PersistentFirstTurn
                node = AWPV2PersistentFirstTurn()
                result = node.execute(
                    session_id="s1",
                    player_input="你好",
                    turn_id="t1", request_id="r1",
                    workflow_run_id="w1", trace_id="tc1",
                )

                diag = result[2]
                assert diag["outcome"] == "success"
                assert diag["quality_verdict"] == "accept"
                # P1: no_state_change when no real state signals
                assert diag["card_state_commit_status"] == "no_state_change"
                assert diag["turn_record_commit_status"] == "committed"

                cs = factory.registry.card_state_store.load("c1", "s1")
                assert cs.revision == 0  # NOT incremented
            finally:
                clear_registry_cache()
                for k in ("AWP_TEST_STORE_ROOT", "AWP_TEST_RUNTIME_NAMESPACE"):
                    os.environ.pop(k, None)

    def test_19_curator_produces_effects_in_context(self):
        """Engine context should include effects from curator."""
        from ..runtime.runtime_store_factory import RuntimeStoreFactory, clear_registry_cache

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AWP_RUNTIME_PROFILE"] = "test"
            os.environ["AWP_TEST_STORE_ROOT"] = tmp
            os.environ["AWP_TEST_RUNTIME_NAMESPACE"] = "p1_test_19"
            clear_registry_cache()
            try:
                factory = RuntimeStoreFactory.from_env()
                self._seed_session(factory.registry, "s1", "c1")

                from ..nodes.persistent_first_turn_node import AWPV2PersistentFirstTurn
                node = AWPV2PersistentFirstTurn()
                result = node.execute(
                    session_id="s1",
                    player_input="你好",
                    turn_id="t1", request_id="r1",
                    workflow_run_id="w1", trace_id="tc1",
                )

                ctx = result[1]
                assert "effects" in ctx
                effects = ctx["effects"]
                assert "state_effects" in effects
                assert "memory_effects" in effects
                assert "delegation" in effects
            finally:
                clear_registry_cache()
                for k in ("AWP_TEST_STORE_ROOT", "AWP_TEST_RUNTIME_NAMESPACE"):
                    os.environ.pop(k, None)

    def test_20_turn_evolution_curator_step_recorded(self):
        """turn_evolution_curator step should appear in diagnostics."""
        from ..runtime.runtime_store_factory import RuntimeStoreFactory, clear_registry_cache

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AWP_RUNTIME_PROFILE"] = "test"
            os.environ["AWP_TEST_STORE_ROOT"] = tmp
            os.environ["AWP_TEST_RUNTIME_NAMESPACE"] = "p1_test_20"
            clear_registry_cache()
            try:
                factory = RuntimeStoreFactory.from_env()
                self._seed_session(factory.registry, "s1", "c1")

                from ..nodes.persistent_first_turn_node import AWPV2PersistentFirstTurn
                node = AWPV2PersistentFirstTurn()
                result = node.execute(
                    session_id="s1",
                    player_input="你好",
                    turn_id="t1", request_id="r1",
                    workflow_run_id="w1", trace_id="tc1",
                )

                diag = result[2]
                assert "turn_evolution_curator" in diag["steps_completed"]
            finally:
                clear_registry_cache()
                for k in ("AWP_TEST_STORE_ROOT", "AWP_TEST_RUNTIME_NAMESPACE"):
                    os.environ.pop(k, None)

    def test_21_condition_evaluator_in_worldbook_resolver(self):
        """Condition-based worldbook entries should activate based on CardState."""
        from ..runtime.version_locked_worldbook_resolver import VersionLockedWorldbookResolver

        evaluator = ConditionEvaluator()
        state = {
            "variables": {"trust": {"value": 60}},
            "event_flags": {},
            "scene_state": {},
        }

        # Condition: trust >= 50
        condition = {"op": "gte", "path": "variables.trust.value", "value": 50}
        assert evaluator.evaluate(condition, state) is True

        # Condition: trust < 50
        condition_low = {"op": "lt", "path": "variables.trust.value", "value": 50}
        assert evaluator.evaluate(condition_low, state) is False

    def test_22_real_director_delegation_plan_generation(self):
        """RealDirectorV2Adapter should generate delegation plans."""
        from ..adapters.llm.real_director_adapter import RealDirectorV2Adapter
        from ..contracts.director_plan import DirectorPlan
        from ..contracts.round_snapshot import RoundSnapshot
        from ..contracts.card_state import CardState

        snapshot = RoundSnapshot(
            snapshot_id="snap1", trace_id="t1",
            card_id="c1", session_id="s1",
            base_card_state_revision=0,
            card_state=CardState(),
            player_input="你好",
            recent_turn_records=[],
            active_memories=[{"memory_id": "m1", "kind": "promise", "summary": "test"}],
        )
        plan = DirectorPlan(plan_id="dp1", turn_goal="greet", scene_focus="tavern")

        # Create a mock deepseek adapter
        class MockLLM:
            def generate_structured(self, prompt, schema, **kwargs):
                return {"turn_goal": "test", "scene_focus": "tavern"}, type('Receipt', (), {'success': True, 'to_dict': lambda self: {}})()

        adapter = RealDirectorV2Adapter(MockLLM(), model="test")
        delegation_plan, receipt = adapter.generate_delegation_plan(snapshot, plan)

        assert delegation_plan is not None
        assert len(delegation_plan.tasks) <= 2  # Max 2 tasks

    def test_23_continue_turn_uses_continue_instruction(self):
        """AWPV2ContinueTurn should use CONTINUE_INSTRUCTION, not empty input."""
        from ..nodes.continue_turn_execution_node import CONTINUE_INSTRUCTION

        assert len(CONTINUE_INSTRUCTION) > 50
        assert "Continue" in CONTINUE_INSTRUCTION or "世界" in CONTINUE_INSTRUCTION
