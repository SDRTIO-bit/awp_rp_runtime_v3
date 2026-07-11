"""P1 Tests: CardState commit, isolation, idempotency, validation."""

import pytest
from awp_rp_runtime_v3.contracts.card_state import CardState, VariableEntry
from awp_rp_runtime_v3.contracts.card_state_patch import (
    CardStatePatch, CardStatePatchOperation, PatchOpType,
    validate_patch_operations,
)
from awp_rp_runtime_v3.contracts.card_state_commit import (
    CardStateCommitRequest, CardStateCommitResult, CardStateCommitStatus,
)
from awp_rp_runtime_v3.contracts.quality_decision import (
    QualityDecision, QualityVerdict, assert_side_effects_allowed, SideEffectBlockedError,
)
from awp_rp_runtime_v3.testing.fakes.fake_stores import FakeCardStateStore


class TestCardStateIsolation:
    """Tests 1-2: cardId+sessionId isolation."""

    def test_different_sessions_isolated(self):
        """Same cardId, different sessionId → separate states."""
        store = FakeCardStateStore()
        store.initialize("card1", "sess1")
        store.initialize("card1", "sess2")

        s1 = store.load("card1", "sess1")
        s2 = store.load("card1", "sess2")
        assert s1.session_id == "sess1"
        assert s2.session_id == "sess2"

        # Modify one, other unchanged
        patch = CardStatePatch(
            patch_id="p1", card_id="card1", session_id="sess1",
            operations=[CardStatePatchOperation(op=PatchOpType.SET, path="variables.hp", value=100)],
        )
        req = CardStateCommitRequest(patch=patch, expected_revision=0)
        new_state = CardState(card_id="card1", session_id="sess1", revision=0,
                              variables={"hp": VariableEntry(name="hp", value=100)})
        store.commit(req, new_state)

        s1_after = store.load("card1", "sess1")
        s2_after = store.load("card1", "sess2")
        assert "hp" in s1_after.variables
        assert "hp" not in s2_after.variables

    def test_different_cards_isolated(self):
        """Same sessionId, different cardId → separate states."""
        store = FakeCardStateStore()
        store.initialize("card1", "sess1")
        store.initialize("card2", "sess1")

        s1 = store.load("card1", "sess1")
        s2 = store.load("card2", "sess1")
        assert s1.card_id == "card1"
        assert s2.card_id == "card2"


class TestCardStateIdempotency:
    """Tests 3, 5: initialization idempotent, patchId replay idempotent."""

    def test_initialize_idempotent(self):
        store = FakeCardStateStore()
        s1 = store.initialize("c1", "s1")
        s2 = store.initialize("c1", "s1")
        assert s1.revision == s2.revision == 0

    def test_patch_id_replay_idempotent(self):
        """Same patchId → returns DUPLICATE_PATCH, no revision change."""
        store = FakeCardStateStore()
        store.initialize("c1", "s1")

        patch = CardStatePatch(
            patch_id="patch_001", card_id="c1", session_id="s1",
            operations=[CardStatePatchOperation(op=PatchOpType.SET, path="variables.x", value=1)],
        )
        req = CardStateCommitRequest(patch=patch, expected_revision=0)
        new_state = CardState(card_id="c1", session_id="s1", revision=0,
                              variables={"x": VariableEntry(name="x", value=1)})

        r1 = store.commit(req, new_state)
        assert r1.success
        assert r1.to_revision == 1

        # Replay same patchId
        r2 = store.commit(req, new_state)
        assert r2.status == CardStateCommitStatus.DUPLICATE_PATCH
        assert r2.to_revision == 1  # No revision bump


class TestRevisionConflict:
    """Test 4: expectedRevision conflict."""

    def test_revision_conflict_rejected(self):
        store = FakeCardStateStore()
        store.initialize("c1", "s1")

        patch = CardStatePatch(
            patch_id="p1", card_id="c1", session_id="s1",
            operations=[],
        )
        # Wrong expected revision
        req = CardStateCommitRequest(patch=patch, expected_revision=99)
        result = store.commit(req, CardState(card_id="c1", session_id="s1"))
        assert result.status == CardStateCommitStatus.REVISION_CONFLICT


class TestMultiOpValidation:
    """Test 6: any illegal op → zero writes."""

    def test_all_or_nothing(self):
        store = FakeCardStateStore()
        store.initialize("c1", "s1")

        # One valid op + one invalid op
        patch = CardStatePatch(
            patch_id="p1", card_id="c1", session_id="s1",
            operations=[
                CardStatePatchOperation(op=PatchOpType.SET, path="variables.hp", value=100),
                CardStatePatchOperation(op=PatchOpType.INCREMENT, path="variables.nonexistent"),
            ],
        )
        req = CardStateCommitRequest(patch=patch, expected_revision=0)
        new_state = CardState(card_id="c1", session_id="s1", revision=0)
        result = store.commit(req, new_state)
        assert result.status == CardStateCommitStatus.VALIDATION_FAILED
        # Revision unchanged
        assert result.from_revision == result.to_revision == 0


class TestGateBlocking:
    """Tests 7-10: gate blocks side effects."""

    def test_gate_revise_blocks_commit(self):
        decision = QualityDecision(verdict=QualityVerdict.REVISE)
        with pytest.raises(SideEffectBlockedError):
            assert_side_effects_allowed(decision)

    def test_gate_reject_blocks_commit(self):
        decision = QualityDecision(verdict=QualityVerdict.REJECTED)
        with pytest.raises(SideEffectBlockedError):
            assert_side_effects_allowed(decision)

    def test_gate_accept_allows_commit(self):
        decision = QualityDecision(verdict=QualityVerdict.ACCEPTED)
        assert_side_effects_allowed(decision)  # Should not raise

    def test_none_decision_blocks(self):
        with pytest.raises(SideEffectBlockedError):
            assert_side_effects_allowed(None)

    def test_trace_id_mismatch_blocks(self):
        from awp_rp_runtime_v3.runtime.card_state_commit_runtime import CardStateCommitRuntime
        store = FakeCardStateStore()
        store.initialize("c1", "s1")
        runtime = CardStateCommitRuntime(store)

        patch = CardStatePatch(
            patch_id="p1", card_id="c1", session_id="s1",
            operations=[], trace_id="trace_A",
        )
        decision = QualityDecision(
            verdict=QualityVerdict.ACCEPTED,
            trace_id="trace_B",
        )
        result = runtime.commit(patch, decision, expected_revision=0)
        assert result.status == CardStateCommitStatus.TRACE_MISMATCH


class TestRevisionIncrement:
    """Test 8: revision increases by exactly 1."""

    def test_revision_increments_by_one(self):
        store = FakeCardStateStore()
        store.initialize("c1", "s1")

        patch = CardStatePatch(
            patch_id="p1", card_id="c1", session_id="s1",
            operations=[CardStatePatchOperation(op=PatchOpType.SET, path="variables.x", value=1)],
        )
        new_state = CardState(card_id="c1", session_id="s1", revision=0,
                              variables={"x": VariableEntry(name="x", value=1)})
        req = CardStateCommitRequest(patch=patch, expected_revision=0)
        result = store.commit(req, new_state)
        assert result.success
        assert result.to_revision == result.from_revision + 1


class TestPatchValidation:
    """Test various op validations."""

    def test_set_requires_value(self):
        ops = [CardStatePatchOperation(op=PatchOpType.SET, path="variables.x")]
        errors = validate_patch_operations(ops, set(), set(), [])
        assert len(errors) == 1
        assert "non-None" in errors[0].message

    def test_increment_requires_existing_variable(self):
        ops = [CardStatePatchOperation(op=PatchOpType.INCREMENT, path="variables.x")]
        errors = validate_patch_operations(ops, set(), set(), [])
        assert len(errors) == 1
        assert "does not exist" in errors[0].message

    def test_deactivate_requires_active_stage(self):
        ops = [CardStatePatchOperation(op=PatchOpType.DEACTIVATE_STAGE, path="active_stage_ids.x", value="x")]
        errors = validate_patch_operations(ops, set(), set(), [])
        assert len(errors) == 1
        assert "not active" in errors[0].message

    def test_set_scene_field_invalid_name(self):
        ops = [CardStatePatchOperation(op=PatchOpType.SET_SCENE_FIELD, path="scene_state.nonexistent", value="x")]
        errors = validate_patch_operations(ops, set(), set(), [])
        assert len(errors) == 1
        assert "Unknown scene field" in errors[0].message

    def test_set_scene_field_wrong_type(self):
        ops = [CardStatePatchOperation(op=PatchOpType.SET_SCENE_FIELD, path="scene_state.location", value=123)]
        errors = validate_patch_operations(ops, set(), set(), [])
        assert len(errors) == 1
        assert "expects str" in errors[0].message

    def test_valid_operations_pass(self):
        ops = [
            CardStatePatchOperation(op=PatchOpType.SET, path="variables.hp", value=100),
            CardStatePatchOperation(op=PatchOpType.SET_FLAG, path="event_flags.quest_started"),
            CardStatePatchOperation(op=PatchOpType.ACTIVATE_STAGE, path="active_stage_ids.s1", value="s1"),
            CardStatePatchOperation(op=PatchOpType.SET_SCENE_FIELD, path="scene_state.location", value="forest"),
        ]
        errors = validate_patch_operations(ops, set(), set(), [])
        assert errors == []
