"""P1 Tests: TurnRecord, Retry, Continue, Snapshot."""

import pytest
from awp_rp_runtime_v3.contracts.turn_record import TurnRecord, TurnMode
from awp_rp_runtime_v3.contracts.round_snapshot import RoundSnapshot
from awp_rp_runtime_v3.contracts.card_state import CardState
from awp_rp_runtime_v3.contracts.quality_decision import (
    QualityDecision, QualityVerdict, SideEffectBlockedError,
)
from awp_rp_runtime_v3.testing.fakes.fake_stores import (
    FakeTurnRecordStore, FakeCardStateStore,
)
from awp_rp_runtime_v3.runtime.turn_record_commit_runtime import TurnRecordCommitRuntime


class TestTurnRecordRevisionBinding:
    """Test 11: TurnRecord binds base/result revision."""

    def test_revision_binding(self):
        store = FakeTurnRecordStore()
        runtime = TurnRecordCommitRuntime(store)

        snapshot = RoundSnapshot(
            snapshot_id="snap1", trace_id="trace1",
            card_id="c1", session_id="s1",
            base_card_state_revision=5,
        )
        decision = QualityDecision(verdict=QualityVerdict.ACCEPTED, trace_id="trace1")

        record = runtime.commit(
            player_input="hello", accepted_text="world",
            snapshot=snapshot, quality_decision=decision,
            base_card_state_revision=5, result_card_state_revision=6,
        )

        assert record.base_card_state_revision == 5
        assert record.result_card_state_revision == 6
        assert record.base_card_state_revision < record.result_card_state_revision


class TestContinue:
    """Test 12: continue from last accepted TurnRecord."""

    def test_continue_from_last_accepted(self):
        store = FakeTurnRecordStore()
        # Save two records
        r1 = TurnRecord(turn_id="t1", card_id="c1", session_id="s1",
                        turn_index=1, mode=TurnMode.NORMAL, writer_output="first")
        r2 = TurnRecord(turn_id="t2", card_id="c1", session_id="s1",
                        turn_index=2, mode=TurnMode.NORMAL, writer_output="second")
        store.save(r1)
        store.save(r2)

        last = store.get_last_accepted("c1", "s1")
        assert last is not None
        assert last.turn_id == "t2"
        assert last.writer_output == "second"


class TestRetry:
    """Test 13: retry does not overwrite accepted TurnRecords."""

    def test_retry_creates_new_record(self):
        store = FakeTurnRecordStore()
        runtime = TurnRecordCommitRuntime(store)

        snapshot = RoundSnapshot(
            snapshot_id="snap1", trace_id="trace1",
            card_id="c1", session_id="s1",
        )
        decision = QualityDecision(verdict=QualityVerdict.ACCEPTED, trace_id="trace1")

        # First attempt accepted
        r1 = runtime.commit(
            player_input="hello", accepted_text="first attempt",
            snapshot=snapshot, quality_decision=decision,
            base_card_state_revision=0, result_card_state_revision=1,
            mode=TurnMode.NORMAL,
        )

        # Retry creates NEW record (not overwrite)
        r2 = runtime.commit(
            player_input="hello", accepted_text="retry attempt",
            snapshot=snapshot, quality_decision=decision,
            base_card_state_revision=1, result_card_state_revision=2,
            mode=TurnMode.RETRY, parent_turn_id=r1.turn_id,
        )

        assert r1.turn_id != r2.turn_id
        assert r1.writer_output == "first attempt"
        assert r2.writer_output == "retry attempt"
        assert r2.parent_turn_id == r1.turn_id

        # Both exist in store
        assert store.load(r1.turn_id) is not None
        assert store.load(r2.turn_id) is not None


class TestRetryGateBlocking:
    """Test 8: gate reject → TurnRecord zero write."""

    def test_reject_blocks_turn_record(self):
        store = FakeTurnRecordStore()
        runtime = TurnRecordCommitRuntime(store)

        snapshot = RoundSnapshot(snapshot_id="s1", trace_id="t1", card_id="c1", session_id="s1")
        decision = QualityDecision(verdict=QualityVerdict.REJECTED)

        with pytest.raises(SideEffectBlockedError):
            runtime.commit(
                player_input="x", accepted_text="y",
                snapshot=snapshot, quality_decision=decision,
                base_card_state_revision=0, result_card_state_revision=0,
            )

        assert store.get_recent("c1", "s1") == []


class TestTurnIndex:
    """Test turn_index is strictly increasing."""

    def test_turn_index_increments(self):
        store = FakeTurnRecordStore()
        runtime = TurnRecordCommitRuntime(store)

        snapshot = RoundSnapshot(snapshot_id="s1", trace_id="t1", card_id="c1", session_id="s1")
        decision = QualityDecision(verdict=QualityVerdict.ACCEPTED, trace_id="t1")

        r1 = runtime.commit("i1", "o1", snapshot, decision, 0, 1)
        r2 = runtime.commit("i2", "o2", snapshot, decision, 1, 2)
        r3 = runtime.commit("i3", "o3", snapshot, decision, 2, 3)

        assert r1.turn_index < r2.turn_index < r3.turn_index


class TestSnapshotImmutability:
    """Test 14: snapshot is frozen."""

    def test_snapshot_immutable(self):
        snapshot = RoundSnapshot(
            snapshot_id="s1", card_id="c1", session_id="s1",
            player_input="hello",
        )
        with pytest.raises(AttributeError):
            snapshot.player_input = "changed"

    def test_snapshot_includes_at_most_5_turns(self):
        """Test 15: snapshot has max 5 recent turns."""
        from awp_rp_runtime_v3.runtime.round_snapshot_builder import RoundSnapshotBuilder
        from awp_rp_runtime_v3.testing.fakes.fake_stores import (
            FakeCardStateStore, FakeTurnRecordStore, FakeActiveMemoryStore, FakeRagMemoryStore,
        )

        cs = FakeCardStateStore()
        ts = FakeTurnRecordStore()
        am = FakeActiveMemoryStore()
        rm = FakeRagMemoryStore()

        builder = RoundSnapshotBuilder(cs, ts, am, rm, max_turn_history=5)
        cs.initialize("c1", "s1")

        # Save 8 turns
        for i in range(8):
            ts.save(TurnRecord(
                turn_id=f"t{i}", card_id="c1", session_id="s1",
                turn_index=i+1, player_input=f"input_{i}", writer_output=f"output_{i}",
            ))

        snapshot = builder.build("c1", "s1", "latest")
        assert len(snapshot.recent_turn_records) <= 5
