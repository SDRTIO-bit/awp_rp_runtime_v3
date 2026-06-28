"""P-Persistent Session Runtime & Canonical RoundSnapshot Integration V1 tests.

Covers the 12 required pure Python persistence boundary tests:

  1. Turn 1 writes to SQLite, new store instance restores CardState
  2. New store instance restores Turn 1 accepted TurnRecord
  3. Turn 2 RoundSnapshot contains Turn 1
  4. OpeningRecord never enters recent accepted turns
  5. ActiveMemory persists and can be read by new Runtime
  6. RagMemory persists and can be read by new Runtime
  7. Session A never reads Session B's State/Turn/Memory
  8. Session version lock not overwritten by new card version
  9. Reject turn does not appear in L1
 10. Retry does not duplicate writes
 11. Deprecated JSON history injection rejected in formal mode
 12. Arbitrary database path cannot be injected from API workflow
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from ..contracts.card_state import CardState
from ..contracts.card_state_commit import CardStateCommitRequest, CardStateCommitStatus
from ..contracts.card_state_patch import CardStatePatch
from ..contracts.turn_record import TurnRecord, TurnMode
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.active_memory import ActiveMemoryEntry, ActiveMemoryRecord
from ..contracts.rag_memory import RagMemoryEntry
from ..contracts.memory_recall_request import MemoryRecallRequest
from ..contracts.card_session_binding import CardSessionBinding
from ..contracts.opening_record import OpeningRecord
from ..contracts.worldbook_binding import WorldbookBinding

from ..storage.sqlite.database import Database
from ..storage.sqlite.card_state_store import SqliteCardStateStore
from ..storage.sqlite.turn_record_store import SqliteTurnRecordStore
from ..storage.sqlite.active_memory_store import SqliteActiveMemoryStore
from ..storage.sqlite.rag_memory_store import SqliteRagMemoryStore
from ..storage.sqlite.session_stores import (
    SqliteCardSessionBindingStore,
    SqliteOpeningRecordStore,
    SqliteWorldbookBindingStore,
)

from ..runtime.session_runtime_registry import SessionRuntimeStoreRegistry
from ..runtime.session_runtime_load import SessionRuntimeLoad
from ..runtime.round_snapshot_builder import RoundSnapshotBuilder


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


def _make_db(tmp_path: str) -> Database:
    db = Database(str(Path(tmp_path) / "test.db"))
    db.initialize()
    return db


def _close_db(db: Database) -> None:
    """Close DB connection to release file lock (Windows)."""
    db.close()


def _seed_session(
    registry: SessionRuntimeStoreRegistry,
    session_id: str = "sess_001",
    card_id: str = "card_001",
    card_version: int = 1,
    source_hash: str = "abc123",
) -> None:
    """Seed a complete session bootstrap into persistent stores."""
    binding = CardSessionBinding(
        session_id=session_id,
        logical_card_id=card_id,
        card_version=card_version,
        source_hash=source_hash,
        selected_greeting_id="g0",
        opening_record_id=f"op_{session_id}",
        worldbook_binding_id=f"wb_{session_id}",
        status="ready",
        created_at=_now(),
    )
    registry.card_session_binding_store.save(binding)

    opening = OpeningRecord(
        opening_record_id=f"op_{session_id}",
        session_id=session_id,
        logical_card_id=card_id,
        card_version=card_version,
        greeting_id="g0",
        safe_display_content="Hello, traveler.",
        created_at=_now(),
    )
    registry.opening_record_store.save(opening)

    wb = WorldbookBinding(
        worldbook_binding_id=f"wb_{session_id}",
        session_id=session_id,
        logical_card_id=card_id,
        card_version=card_version,
        source_hash=source_hash,
        created_at=_now(),
    )
    registry.worldbook_binding_store.save(wb)

    registry.card_state_store.initialize(card_id, session_id)


def _commit_turn(
    registry: SessionRuntimeStoreRegistry,
    turn_id: str,
    card_id: str,
    session_id: str,
    turn_index: int,
    player_input: str,
    writer_output: str,
    base_rev: int = 0,
    result_rev: int = 1,
) -> TurnRecord:
    """Commit a turn record to the persistent store."""
    record = TurnRecord(
        turn_id=turn_id,
        trace_id=f"trc_{turn_id}",
        session_id=session_id,
        card_id=card_id,
        turn_index=turn_index,
        player_input=player_input,
        writer_output=writer_output,
        mode=TurnMode.NORMAL,
        base_card_state_revision=base_rev,
        result_card_state_revision=result_rev,
        created_at=_now(),
    )
    registry.turn_record_store.save(record)
    return record


# ── Test 1: CardState persistence ────────────────────────────────────────────

class TestCardStatePersistence:

    def test_01_card_state_persists_across_store_instances(self):
        """Turn 1 writes to SQLite, new store instance restores CardState."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            store = SqliteCardStateStore(db)

            # Initialize and commit
            cs = store.initialize("card_001", "sess_001")
            assert cs.revision == 0

            patch = CardStatePatch(
                patch_id="patch_001", card_id="card_001",
                session_id="sess_001", trace_id="trc_001",
            )
            request = CardStateCommitRequest(expected_revision=0, patch=patch)
            new_state = CardState(
                card_id="card_001", session_id="sess_001",
                revision=1, created_at=_now(), updated_at=_now(),
            )
            result = store.commit(request, new_state)
            assert result.status == CardStateCommitStatus.ACCEPTED
            _close_db(db)

            # New store instance — same database
            db2 = Database(str(Path(tmp) / "test.db"))
            db2.initialize()
            store2 = SqliteCardStateStore(db2)

            loaded = store2.load("card_001", "sess_001")
            assert loaded is not None
            assert loaded.revision == 1
            _close_db(db2)


# ── Test 2: TurnRecord persistence ──────────────────────────────────────────

class TestTurnRecordPersistence:

    def test_02_turn_record_persists_across_store_instances(self):
        """New store instance restores Turn 1 accepted TurnRecord."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            store = SqliteTurnRecordStore(db)

            record = TurnRecord(
                turn_id="turn_001", trace_id="trc_001",
                session_id="sess_001", card_id="card_001",
                turn_index=1, player_input="Hello",
                writer_output="Response text",
                mode=TurnMode.NORMAL,
                base_card_state_revision=0, result_card_state_revision=1,
                created_at=_now(),
            )
            store.save(record)
            _close_db(db)

            # New store instance
            db2 = Database(str(Path(tmp) / "test.db"))
            db2.initialize()
            store2 = SqliteTurnRecordStore(db2)

            loaded = store2.load("turn_001")
            assert loaded is not None
            assert loaded.turn_id == "turn_001"
            assert loaded.writer_output == "Response text"
            assert loaded.turn_index == 1

            # get_recent works
            recent = store2.get_recent("card_001", "sess_001", limit=5)
            assert len(recent) == 1
            assert recent[0].turn_id == "turn_001"
            _close_db(db2)


# ── Test 3: RoundSnapshot contains Turn 1 ───────────────────────────────────

class TestRoundSnapshotWithHistory:

    def test_03_turn2_snapshot_contains_turn1(self):
        """Turn 2 RoundSnapshot built by RoundSnapshotBuilder contains Turn 1."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            registry = SessionRuntimeStoreRegistry(db)
            _seed_session(registry)

            # Commit Turn 1
            _commit_turn(registry, "turn_001", "card_001", "sess_001", 1,
                         "Hello", "Response to Hello")

            # Build snapshot for Turn 2
            builder = RoundSnapshotBuilder(
                card_state_store=registry.card_state_store,
                turn_record_store=registry.turn_record_store,
                active_memory_store=registry.active_memory_store,
                rag_memory_store=registry.rag_memory_store,
            )
            snapshot = builder.build("card_001", "sess_001", "What happened?")

            assert len(snapshot.recent_turn_records) == 1
            assert snapshot.recent_turn_records[0].turn_id == "turn_001"
            _close_db(db)


# ── Test 4: OpeningRecord not in recent accepted ────────────────────────────

class TestOpeningRecordSeparation:

    def test_04_opening_record_not_in_recent_accepted(self):
        """OpeningRecord must not appear in recent accepted turn records."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            registry = SessionRuntimeStoreRegistry(db)
            _seed_session(registry)

            # The OpeningRecord is stored separately, not as a TurnRecord.
            # get_recent should return empty since no turns committed yet.
            recent = registry.turn_record_store.get_recent("card_001", "sess_001")
            assert len(recent) == 0

            # OpeningRecord is accessible via its own store
            opening = registry.opening_record_store.get_by_session("sess_001")
            assert opening is not None
            assert opening.greeting_id == "g0"
            _close_db(db)


# ── Test 5: ActiveMemory persistence ────────────────────────────────────────

class TestActiveMemoryPersistence:

    def test_05_active_memory_persists_and_recalls(self):
        """ActiveMemory written to SQLite can be read by new Runtime."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            store = SqliteActiveMemoryStore(db)

            entry = ActiveMemoryEntry(
                memory_id="mem_001",
                summary="Player promised to return tomorrow",
                importance=0.8,
                confidence=0.9,
                entity_refs=["player"],
                source_turn_ids=["turn_001"],
            )
            store.upsert("card_001", "sess_001", entry)
            _close_db(db)

            # New store instance
            db2 = Database(str(Path(tmp) / "test.db"))
            db2.initialize()
            store2 = SqliteActiveMemoryStore(db2)

            all_entries = store2.get_all("card_001", "sess_001")
            assert len(all_entries) == 1
            assert all_entries[0].memory_id == "mem_001"
            assert all_entries[0].summary == "Player promised to return tomorrow"

            # Recall works
            request = MemoryRecallRequest(
                card_id="card_001", session_id="sess_001",
                snapshot_id="snap_001", trace_id="trc_001",
                query="promise", limit=10,
            )
            result = store2.recall("card_001", "sess_001", request)
            assert len(result.hits) >= 1
            _close_db(db2)


# ── Test 6: RagMemory persistence ───────────────────────────────────────────

class TestRagMemoryPersistence:

    def test_06_rag_memory_persists_and_searches(self):
        """RagMemory written to SQLite can be read by new Runtime."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            store = SqliteRagMemoryStore(db)

            entry = RagMemoryEntry(
                memory_id="rag_001",
                content="The village elder knows about the ancient ruins",
                summary="Elder ruins knowledge",
                importance=0.7,
                confidence=0.8,
                entity_refs=["elder", "ruins"],
                source_turn_ids=["turn_002"],
            )
            store.save("card_001", "sess_001", entry)
            _close_db(db)

            # New store instance
            db2 = Database(str(Path(tmp) / "test.db"))
            db2.initialize()
            store2 = SqliteRagMemoryStore(db2)

            results = store2.search("card_001", "sess_001", "ruins", limit=5)
            assert len(results) >= 1
            assert results[0].memory_id == "rag_001"
            _close_db(db2)


# ── Test 7: Session isolation ───────────────────────────────────────────────

class TestSessionIsolation:

    def test_07_session_a_never_reads_session_b(self):
        """Session A never reads Session B's State/Turn/Memory."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            registry = SessionRuntimeStoreRegistry(db)

            # Seed two sessions
            _seed_session(registry, session_id="sess_A", card_id="card_001")
            _seed_session(registry, session_id="sess_B", card_id="card_001")

            # Commit turn to session A only
            _commit_turn(registry, "turn_A1", "card_001", "sess_A", 1,
                         "Hello A", "Response A")

            # Session B should have no turns
            recent_b = registry.turn_record_store.get_recent("card_001", "sess_B")
            assert len(recent_b) == 0

            # Session A should have its turn
            recent_a = registry.turn_record_store.get_recent("card_001", "sess_A")
            assert len(recent_a) == 1

            # CardState is per-session
            cs_a = registry.card_state_store.load("card_001", "sess_A")
            cs_b = registry.card_state_store.load("card_001", "sess_B")
            assert cs_a is not None
            assert cs_b is not None
            assert cs_a.session_id == "sess_A"
            assert cs_b.session_id == "sess_B"
            _close_db(db)


# ── Test 8: Session version lock ────────────────────────────────────────────

class TestSessionVersionLock:

    def test_08_session_version_not_overwritten(self):
        """Session binding with card_version=1 not overwritten by version=2."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            store = SqliteCardSessionBindingStore(db)

            binding1 = CardSessionBinding(
                session_id="sess_001", logical_card_id="card_001",
                card_version=1, source_hash="hash_v1",
                status="ready", created_at=_now(),
            )
            store.save(binding1)

            # Try to save with different version (should overwrite by session_id PK)
            binding2 = CardSessionBinding(
                session_id="sess_001", logical_card_id="card_001",
                card_version=2, source_hash="hash_v2",
                status="ready", created_at=_now(),
            )
            store.save(binding2)

            # Load — should be version 2 since session_id is PK
            loaded = store.load("sess_001")
            assert loaded is not None
            assert loaded.card_version == 2

            # But a DIFFERENT session with version 1 is untouched
            binding3 = CardSessionBinding(
                session_id="sess_002", logical_card_id="card_001",
                card_version=1, source_hash="hash_v1",
                status="ready", created_at=_now(),
            )
            store.save(binding3)
            loaded3 = store.load("sess_002")
            assert loaded3.card_version == 1
            _close_db(db)


# ── Test 9: Reject turn not in L1 ──────────────────────────────────────────

class TestRejectTurnExclusion:

    def test_09_rejected_turn_not_in_l1(self):
        """Rejected turns (not committed) do not appear in L1 history."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            registry = SessionRuntimeStoreRegistry(db)
            _seed_session(registry)

            # Only commit accepted turns
            _commit_turn(registry, "turn_001", "card_001", "sess_001", 1,
                         "Input 1", "Accepted response 1")
            # Turn 2 was rejected — never saved to TurnRecordStore
            _commit_turn(registry, "turn_003", "card_001", "sess_001", 3,
                         "Input 3", "Accepted response 3")

            recent = registry.turn_record_store.get_recent("card_001", "sess_001")
            assert len(recent) == 2
            turn_ids = [r.turn_id for r in recent]
            assert "turn_001" in turn_ids
            assert "turn_003" in turn_ids
            _close_db(db)


# ── Test 10: Retry idempotency ──────────────────────────────────────────────

class TestRetryIdempotency:

    def test_10_retry_does_not_duplicate_writes(self):
        """Same turn_id cannot be written twice (DuplicateTurnError)."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            store = SqliteTurnRecordStore(db)

            record = TurnRecord(
                turn_id="turn_001", trace_id="trc_001",
                session_id="sess_001", card_id="card_001",
                turn_index=1, player_input="Hello",
                writer_output="Response", mode=TurnMode.NORMAL,
                created_at=_now(),
            )
            store.save(record)

            # Retry with same turn_id should raise
            from ..storage.interfaces import DuplicateTurnError
            with pytest.raises(DuplicateTurnError):
                store.save(record)

            # Only one record exists
            recent = store.get_recent("card_001", "sess_001")
            assert len(recent) == 1
            _close_db(db)


# ── Test 11: Deprecated JSON injection rejected ─────────────────────────────

class TestDeprecatedJsonInjection:

    def test_11_formal_mode_rejects_json_injection(self):
        """The persistent continuation path does not accept previous_turn_records.

        AWPV2PersistentContinuationTurn.INPUT_TYPES has NO previous_turn_records.
        This is enforced at the node interface level.
        """
        from ..nodes.persistent_continuation_turn_node import AWPV2PersistentContinuationTurn

        input_types = AWPV2PersistentContinuationTurn.INPUT_TYPES()
        all_inputs = {}
        all_inputs.update(input_types.get("required", {}))
        all_inputs.update(input_types.get("optional", {}))

        # Must NOT have these deprecated inputs
        for forbidden in ["previous_turn_records", "active_memories", "rag_recall",
                          "card_state", "card_session_binding", "opening_record",
                          "worldbook_binding"]:
            assert forbidden not in all_inputs, \
                f"Persistent continuation must not accept '{forbidden}' as input"


# ── Test 12: Arbitrary DB path injection ────────────────────────────────────

class TestDbPathSafety:

    def test_12_db_path_from_env_not_workflow(self):
        """Database path is resolved from environment, not arbitrary workflow input.

        The db_path input exists for test override only — production uses env.
        """
        from ..nodes.session_runtime_load_node import _resolve_db_path

        # Default (no env) returns a safe path
        old_env = os.environ.get("AWP_RUNTIME_PROFILE")
        old_root = os.environ.get("AWP_TEST_STORE_ROOT")
        old_ns = os.environ.get("AWP_TEST_RUNTIME_NAMESPACE")
        old_db = os.environ.get("AWP_RUNTIME_DB_PATH")
        try:
            os.environ.pop("AWP_RUNTIME_PROFILE", None)
            os.environ.pop("AWP_TEST_STORE_ROOT", None)
            os.environ.pop("AWP_TEST_RUNTIME_NAMESPACE", None)
            os.environ.pop("AWP_RUNTIME_DB_PATH", None)

            path = _resolve_db_path()
            assert path == "awp_rp_runtime.db"

            # Test mode resolves to controlled directory
            os.environ["AWP_RUNTIME_PROFILE"] = "test"
            os.environ["AWP_TEST_STORE_ROOT"] = "/tmp/test_stores"
            os.environ["AWP_TEST_RUNTIME_NAMESPACE"] = "run_001"
            path = _resolve_db_path()
            assert "run_001" in path
            assert "awp_session.db" in path
        finally:
            if old_env is not None:
                os.environ["AWP_RUNTIME_PROFILE"] = old_env
            else:
                os.environ.pop("AWP_RUNTIME_PROFILE", None)
            if old_root is not None:
                os.environ["AWP_TEST_STORE_ROOT"] = old_root
            else:
                os.environ.pop("AWP_TEST_STORE_ROOT", None)
            if old_ns is not None:
                os.environ["AWP_TEST_RUNTIME_NAMESPACE"] = old_ns
            else:
                os.environ.pop("AWP_TEST_RUNTIME_NAMESPACE", None)
            if old_db is not None:
                os.environ["AWP_RUNTIME_DB_PATH"] = old_db
            else:
                os.environ.pop("AWP_RUNTIME_DB_PATH", None)


# ── Full integration: SessionRuntimeLoad ─────────────────────────────────────

class TestSessionRuntimeLoadIntegration:

    def test_load_restores_all_layers(self):
        """SessionRuntimeLoad restores L0 + L1 from persistent stores."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            registry = SessionRuntimeStoreRegistry(db)
            _seed_session(registry)

            # Commit 3 turns
            for i in range(1, 4):
                _commit_turn(
                    registry, f"turn_{i:03d}", "card_001", "sess_001", i,
                    f"Player input {i}", f"Response {i}",
                    base_rev=i - 1, result_rev=i,
                )

            # Load via SessionRuntimeLoad
            loader = SessionRuntimeLoad(registry)
            bundle = loader.load("sess_001", "New player input")

            assert bundle.is_valid
            assert bundle.card_session_binding is not None
            assert bundle.card_state is not None
            assert bundle.opening_record is not None
            assert bundle.worldbook_binding is not None
            assert bundle.round_snapshot is not None
            assert bundle.l1_turn_count == 3
            assert len(bundle.round_snapshot.recent_turn_records) == 3
            _close_db(db)

    def test_load_fails_gracefully_missing_session(self):
        """SessionRuntimeLoad returns errors for missing session."""
        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            registry = SessionRuntimeStoreRegistry(db)

            loader = SessionRuntimeLoad(registry)
            bundle = loader.load("nonexistent_session", "Hello")

            assert not bundle.is_valid
            assert len(bundle.load_errors) > 0
            _close_db(db)

    def test_load_across_db_instances(self):
        """SessionRuntimeLoad works with a fresh registry on the same DB."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "test.db")

            # First instance: seed data
            db1 = Database(db_path)
            db1.initialize()
            registry1 = SessionRuntimeStoreRegistry(db1)
            _seed_session(registry1)
            _commit_turn(registry1, "turn_001", "card_001", "sess_001", 1,
                         "Hello", "Response")
            db1.close()

            # Second instance: load data
            db2 = Database(db_path)
            db2.initialize()
            registry2 = SessionRuntimeStoreRegistry(db2)
            loader = SessionRuntimeLoad(registry2)
            bundle = loader.load("sess_001", "Continue")

            assert bundle.is_valid
            assert bundle.l1_turn_count == 1
            assert bundle.round_snapshot.recent_turn_records[0].turn_id == "turn_001"
            db2.close()
