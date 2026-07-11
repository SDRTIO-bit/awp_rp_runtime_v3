"""Tests for StatePolicy."""

import pytest
from awp_rp_runtime_v3.policies.state_policy import StatePolicy
from awp_rp_runtime_v3.contracts.card_state import CardState
from awp_rp_runtime_v3.contracts.state_update_proposal import (
    StateUpdateProposal, PatchOp, PatchOpEntry,
)


class TestStatePolicy:
    """Test StatePolicy validation rules."""

    def setup_method(self):
        self.policy = StatePolicy()
        self.state = CardState(
            card_id="card1",
            session_id="sess1",
            revision=5,
        )

    def test_valid_proposal(self):
        proposal = StateUpdateProposal(
            card_id="card1",
            session_id="sess1",
            operations=[
                PatchOpEntry(op=PatchOp.SET_VARIABLE, path="variables.hp", value=100),
            ],
        )
        result = self.policy.validate_proposal(proposal, self.state, expected_revision=5)
        assert result.valid

    def test_revision_conflict(self):
        proposal = StateUpdateProposal(
            card_id="card1",
            session_id="sess1",
            operations=[],
        )
        result = self.policy.validate_proposal(proposal, self.state, expected_revision=3)
        assert not result.valid
        assert any("Revision conflict" in e for e in result.errors)

    def test_card_id_mismatch(self):
        proposal = StateUpdateProposal(
            card_id="wrong_card",
            session_id="sess1",
            operations=[],
        )
        result = self.policy.validate_proposal(proposal, self.state, expected_revision=5)
        assert not result.valid
        assert any("card_id mismatch" in e for e in result.errors)

    def test_session_id_mismatch(self):
        proposal = StateUpdateProposal(
            card_id="card1",
            session_id="wrong_session",
            operations=[],
        )
        result = self.policy.validate_proposal(proposal, self.state, expected_revision=5)
        assert not result.valid
        assert any("session_id mismatch" in e for e in result.errors)

    def test_invalid_path(self):
        proposal = StateUpdateProposal(
            card_id="card1",
            session_id="sess1",
            operations=[
                PatchOpEntry(op=PatchOp.SET_VARIABLE, path="invalid"),
            ],
        )
        result = self.policy.validate_proposal(proposal, self.state, expected_revision=5)
        assert not result.valid

    def test_only_commit_runtime_can_write(self):
        assert self.policy.is_writable_by("card_state_commit_runtime")
        assert self.policy.is_writable_by("CardStateCommitNode")
        assert not self.policy.is_writable_by("writer")
        assert not self.policy.is_writable_by("director")
        assert not self.policy.is_writable_by("sub_agent")
