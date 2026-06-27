"""P1 End-to-End Integration Test.

Full chain:
  Init CardState → Snapshot → QualityGate accept → StateCommit
  → TurnRecord → Replay same patchId → Verify revision bumps once
  → Verify TurnRecord not duplicated
"""

import pytest
from awp_rp_runtime_v2.contracts.card_state import CardState, VariableEntry
from awp_rp_runtime_v2.contracts.card_state_patch import (
    CardStatePatch, CardStatePatchOperation, PatchOpType,
)
from awp_rp_runtime_v2.contracts.card_state_commit import CardStateCommitRequest, CardStateCommitStatus
from awp_rp_runtime_v2.contracts.quality_decision import QualityDecision, QualityVerdict
from awp_rp_runtime_v2.contracts.turn_record import TurnRecord, TurnMode
from awp_rp_runtime_v2.contracts.round_snapshot import RoundSnapshot
from awp_rp_runtime_v2.testing.fakes.fake_stores import (
    FakeCardStateStore, FakeTurnRecordStore, FakeActiveMemoryStore, FakeRagMemoryStore,
)
from awp_rp_runtime_v2.runtime.round_snapshot_builder import RoundSnapshotBuilder
from awp_rp_runtime_v2.runtime.card_state_commit_runtime import CardStateCommitRuntime
from awp_rp_runtime_v2.runtime.turn_record_commit_runtime import TurnRecordCommitRuntime


class TestEndToEnd:
    """Complete end-to-end P1 test."""

    def test_full_turn_lifecycle(self):
        # Setup stores
        cs_store = FakeCardStateStore()
        tr_store = FakeTurnRecordStore()
        am_store = FakeActiveMemoryStore()
        rm_store = FakeRagMemoryStore()

        snapshot_builder = RoundSnapshotBuilder(cs_store, tr_store, am_store, rm_store)
        state_commit = CardStateCommitRuntime(cs_store)
        turn_commit = TurnRecordCommitRuntime(tr_store)

        # 1. Initialize CardState
        cs_store.initialize("card1", "sess1")
        state = cs_store.load("card1", "sess1")
        assert state.revision == 0

        # 2. Build snapshot
        snapshot = snapshot_builder.build("card1", "sess1", "我走进了月光庭院")
        assert snapshot.base_card_state_revision == 0
        assert snapshot.card_state.card_id == "card1"

        # 3. Quality gate accepts
        decision = QualityDecision(
            verdict=QualityVerdict.ACCEPTED,
            trace_id=snapshot.trace_id,
            source_turn_id=snapshot.snapshot_id,
        )
        assert decision.allows_side_effects()

        # 4. Create and commit state patch
        patch = CardStatePatch(
            patch_id="patch_001",
            card_id="card1", session_id="sess1",
            operations=[
                CardStatePatchOperation(op=PatchOpType.SET, path="variables.favorability", value=10),
                CardStatePatchOperation(op=PatchOpType.SET_FLAG, path="event_flags.first_meeting"),
            ],
            trace_id=snapshot.trace_id,
        )

        result = state_commit.commit(patch, decision, expected_revision=0)
        assert result.success
        assert result.from_revision == 0
        assert result.to_revision == 1

        # 5. Verify state updated
        updated = cs_store.load("card1", "sess1")
        assert updated.revision == 1
        assert "favorability" in updated.variables
        assert "first_meeting" in updated.event_flags

        # 6. Commit TurnRecord
        turn_record = turn_commit.commit(
            player_input="我走进了月光庭院",
            accepted_text="月光如水，洒在青石板路上...",
            snapshot=snapshot,
            quality_decision=decision,
            base_card_state_revision=0,
            result_card_state_revision=1,
            state_commit_patch_id="patch_001",
        )
        assert turn_record.base_card_state_revision == 0
        assert turn_record.result_card_state_revision == 1

        # 7. Replay same patchId — should be idempotent
        result2 = state_commit.commit(patch, decision, expected_revision=0)
        assert result2.status == CardStateCommitStatus.DUPLICATE_PATCH

        # 8. Verify revision only grew once
        final = cs_store.load("card1", "sess1")
        assert final.revision == 1  # Still 1, not 2

        # 9. Verify TurnRecord not duplicated
        records = tr_store.get_recent("card1", "sess1")
        assert len(records) == 1
        assert records[0].turn_id == turn_record.turn_id

        # 10. Verify patch log
        log = cs_store.get_patch_log("card1", "sess1")
        assert len(log) == 1
        assert log[0]["patch_id"] == "patch_001"

    def test_replay_restores_revision_sequence(self):
        """Test 16: replay can restore CardState revision sequence."""
        cs_store = FakeCardStateStore()
        cs_store.initialize("c1", "s1")

        # Apply 3 patches
        for i in range(1, 4):
            patch = CardStatePatch(
                patch_id=f"patch_{i:03d}", card_id="c1", session_id="s1",
                operations=[
                    CardStatePatchOperation(op=PatchOpType.SET, path=f"variables.v{i}", value=i),
                ],
            )
            new_state = CardState(card_id="c1", session_id="s1", revision=i-1,
                                  variables={f"v{i}": VariableEntry(name=f"v{i}", value=i)})
            req = CardStateCommitRequest(patch=patch, expected_revision=i-1)
            result = cs_store.commit(req, new_state)
            assert result.success
            assert result.to_revision == i

        # Verify patch log has all 3
        log = cs_store.get_patch_log("c1", "s1")
        assert len(log) == 3
        assert log[0]["from_revision"] == 0 and log[0]["to_revision"] == 1
        assert log[1]["from_revision"] == 1 and log[1]["to_revision"] == 2
        assert log[2]["from_revision"] == 2 and log[2]["to_revision"] == 3

        # Verify final state
        final = cs_store.load("c1", "s1")
        assert final.revision == 3
