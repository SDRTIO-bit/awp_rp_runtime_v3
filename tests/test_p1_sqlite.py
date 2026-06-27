"""P1 Tests: SQLite storage, migrations, atomic commits."""

import pytest
import tempfile
import os
import json
from pathlib import Path

from awp_rp_runtime_v2.storage.sqlite.database import Database
from awp_rp_runtime_v2.storage.sqlite.card_state_store import SqliteCardStateStore
from awp_rp_runtime_v2.storage.sqlite.turn_record_store import SqliteTurnRecordStore
from awp_rp_runtime_v2.storage.sqlite.round_snapshot_store import SqliteRoundSnapshotStore
from awp_rp_runtime_v2.contracts.card_state import CardState, VariableEntry
from awp_rp_runtime_v2.contracts.card_state_patch import (
    CardStatePatch, CardStatePatchOperation, PatchOpType,
)
from awp_rp_runtime_v2.contracts.card_state_commit import (
    CardStateCommitRequest, CardStateCommitStatus,
)
from awp_rp_runtime_v2.contracts.turn_record import TurnRecord, TurnMode
from awp_rp_runtime_v2.contracts.round_snapshot import RoundSnapshot
from awp_rp_runtime_v2.contracts.quality_decision import QualityDecision, QualityVerdict


@pytest.fixture
def tmp_db():
    """Create a temporary SQLite database for each test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(path)
    db.initialize()
    yield db
    db.close()
    os.unlink(path)


class TestMigration:
    """Tests 17: migration is idempotent."""

    def test_migration_idempotent(self, tmp_db):
        # tmp_db fixture already calls initialize() which applies migrations
        # So first call returns empty (already applied)
        v1 = tmp_db.apply_migrations()
        assert v1 == []  # Already applied by fixture

        # Second call also returns empty
        v2 = tmp_db.apply_migrations()
        assert v2 == []

    def test_schema_version(self, tmp_db):
        tmp_db.apply_migrations()
        assert tmp_db.get_schema_version() >= 1


class TestSqliteCardStateCommit:
    """Test 18: atomic commit (patch receipt + state in same tx)."""

    def test_commit_atomic(self, tmp_db):
        store = SqliteCardStateStore(tmp_db)
        store.initialize("c1", "s1")

        patch = CardStatePatch(
            patch_id="p1", card_id="c1", session_id="s1",
            operations=[
                CardStatePatchOperation(op=PatchOpType.SET, path="variables.hp", value=100),
            ],
        )
        req = CardStateCommitRequest(patch=patch, expected_revision=0)
        new_state = CardState(card_id="c1", session_id="s1", revision=0,
                              variables={"hp": VariableEntry(name="hp", value=100)})
        result = store.commit(req, new_state)

        assert result.success
        assert result.to_revision == 1

        # Check receipt exists
        log = store.get_patch_log("c1", "s1")
        assert len(log) == 1
        assert log[0]["patch_id"] == "p1"
        assert log[0]["from_revision"] == 0
        assert log[0]["to_revision"] == 1

        # Check state is updated
        loaded = store.load("c1", "s1")
        assert loaded.revision == 1

    def test_duplicate_patch_returns_original(self, tmp_db):
        store = SqliteCardStateStore(tmp_db)
        store.initialize("c1", "s1")

        patch = CardStatePatch(
            patch_id="p1", card_id="c1", session_id="s1",
            operations=[CardStatePatchOperation(op=PatchOpType.SET, path="variables.x", value=1)],
        )
        new_state = CardState(card_id="c1", session_id="s1", revision=0,
                              variables={"x": VariableEntry(name="x", value=1)})
        req = CardStateCommitRequest(patch=patch, expected_revision=0)

        r1 = store.commit(req, new_state)
        assert r1.success
        assert r1.to_revision == 1

        # Replay
        r2 = store.commit(req, new_state)
        assert r2.status == CardStateCommitStatus.DUPLICATE_PATCH
        assert r2.to_revision == 1  # No bump

    def test_isolation(self, tmp_db):
        store = SqliteCardStateStore(tmp_db)
        store.initialize("c1", "s1")
        store.initialize("c1", "s2")

        patch = CardStatePatch(
            patch_id="p1", card_id="c1", session_id="s1",
            operations=[CardStatePatchOperation(op=PatchOpType.SET, path="variables.hp", value=100)],
        )
        new_state = CardState(card_id="c1", session_id="s1", revision=0,
                              variables={"hp": VariableEntry(name="hp", value=100)})
        req = CardStateCommitRequest(patch=patch, expected_revision=0)
        store.commit(req, new_state)

        s1 = store.load("c1", "s1")
        s2 = store.load("c1", "s2")
        assert "hp" in s1.variables
        assert "hp" not in s2.variables


class TestSqliteTurnRecord:
    """Test TurnRecord in SQLite."""

    def test_save_and_load(self, tmp_db):
        store = SqliteTurnRecordStore(tmp_db)
        record = TurnRecord(
            turn_id="t1", trace_id="tr1", card_id="c1", session_id="s1",
            turn_index=1, mode=TurnMode.NORMAL,
            player_input="hello", writer_output="world",
            base_card_state_revision=0, result_card_state_revision=1,
        )
        store.save(record)

        loaded = store.load("t1")
        assert loaded is not None
        assert loaded.turn_id == "t1"
        assert loaded.base_card_state_revision == 0
        assert loaded.result_card_state_revision == 1

    def test_next_turn_index(self, tmp_db):
        store = SqliteTurnRecordStore(tmp_db)
        assert store.get_next_turn_index("c1", "s1") == 1

        store.save(TurnRecord(turn_id="t1", card_id="c1", session_id="s1", turn_index=1))
        assert store.get_next_turn_index("c1", "s1") == 2


class TestSqliteRoundSnapshot:
    """Test RoundSnapshot persistence."""

    def test_save_and_load(self, tmp_db):
        store = SqliteRoundSnapshotStore(tmp_db)
        snapshot = RoundSnapshot(
            snapshot_id="snap1", trace_id="tr1",
            card_id="c1", session_id="s1",
            base_card_state_revision=5,
            player_input="hello",
        )
        store.save(snapshot)

        loaded = store.load("snap1")
        assert loaded is not None
        assert loaded.snapshot_id == "snap1"
        assert loaded.base_card_state_revision == 5
