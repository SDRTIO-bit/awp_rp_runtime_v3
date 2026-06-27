"""Tests for CardState store."""

import pytest
from awp_rp_runtime_v2.testing.fakes.fake_stores import FakeCardStateStore
from awp_rp_runtime_v2.contracts.card_state import CardState, VariableEntry
from awp_rp_runtime_v2.contracts.card_state_patch import CardStatePatch, CardStatePatchOperation, PatchOpType
from awp_rp_runtime_v2.contracts.card_state_commit import CardStateCommitRequest, CardStateCommitStatus
from awp_rp_runtime_v2.storage.interfaces import RevisionConflictError, DuplicatePatchError


class TestCardStateStore:

    def setup_method(self):
        self.store = FakeCardStateStore()

    def test_initialize_creates_state(self):
        state = self.store.initialize("card1", "sess1")
        assert state.card_id == "card1"
        assert state.revision == 0

    def test_initialize_idempotent(self):
        s1 = self.store.initialize("card1", "sess1")
        s2 = self.store.initialize("card1", "sess1")
        assert s1.revision == s2.revision

    def test_load_existing(self):
        self.store.initialize("card1", "sess1")
        loaded = self.store.load("card1", "sess1")
        assert loaded is not None

    def test_load_nonexistent(self):
        assert self.store.load("card1", "sess1") is None

    def test_commit_success(self):
        self.store.initialize("card1", "sess1")
        patch = CardStatePatch(
            patch_id="p1", card_id="card1", session_id="sess1",
            operations=[CardStatePatchOperation(op=PatchOpType.SET, path="variables.hp", value=100)],
        )
        new_state = CardState(card_id="card1", session_id="sess1", revision=0,
                              variables={"hp": VariableEntry(name="hp", value=100)})
        req = CardStateCommitRequest(patch=patch, expected_revision=0)
        result = self.store.commit(req, new_state)
        assert result.success
        assert result.to_revision == 1

    def test_commit_revision_conflict(self):
        self.store.initialize("card1", "sess1")
        patch = CardStatePatch(patch_id="p1", card_id="card1", session_id="sess1", operations=[])
        req = CardStateCommitRequest(patch=patch, expected_revision=99)
        result = self.store.commit(req, CardState(card_id="card1", session_id="sess1"))
        assert result.status == CardStateCommitStatus.REVISION_CONFLICT

    def test_commit_duplicate_patch(self):
        self.store.initialize("card1", "sess1")
        patch = CardStatePatch(
            patch_id="p1", card_id="card1", session_id="sess1",
            operations=[CardStatePatchOperation(op=PatchOpType.SET, path="variables.x", value=1)],
        )
        new_state = CardState(card_id="card1", session_id="sess1", revision=0,
                              variables={"x": VariableEntry(name="x", value=1)})
        req = CardStateCommitRequest(patch=patch, expected_revision=0)
        self.store.commit(req, new_state)
        result = self.store.commit(req, new_state)
        assert result.status == CardStateCommitStatus.DUPLICATE_PATCH

    def test_isolation_between_sessions(self):
        self.store.initialize("card1", "sess1")
        self.store.initialize("card1", "sess2")
        assert self.store.load("card1", "sess1").session_id == "sess1"
        assert self.store.load("card1", "sess2").session_id == "sess2"

    def test_patch_log(self):
        self.store.initialize("card1", "sess1")
        patch = CardStatePatch(
            patch_id="p1", card_id="card1", session_id="sess1",
            operations=[CardStatePatchOperation(op=PatchOpType.SET, path="variables.x", value=1)],
        )
        new_state = CardState(card_id="card1", session_id="sess1", revision=0,
                              variables={"x": VariableEntry(name="x", value=1)})
        req = CardStateCommitRequest(patch=patch, expected_revision=0)
        self.store.commit(req, new_state)
        log = self.store.get_patch_log("card1", "sess1")
        assert len(log) == 1
        assert log[0]["patch_id"] == "p1"
