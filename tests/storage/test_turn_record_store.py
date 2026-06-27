"""Tests for TurnRecord store."""

import pytest
from awp_rp_runtime_v2.testing.fakes.fake_stores import FakeTurnRecordStore
from awp_rp_runtime_v2.contracts.turn_record import TurnRecord, TurnMode
from awp_rp_runtime_v2.storage.interfaces import DuplicateTurnError


class TestTurnRecordStore:

    def setup_method(self):
        self.store = FakeTurnRecordStore()

    def _make_record(self, turn_id="turn_1", player_input="hello", writer_output="world"):
        return TurnRecord(
            turn_id=turn_id, card_id="card1", session_id="sess1",
            player_input=player_input, writer_output=writer_output,
        )

    def test_save_and_load(self):
        self.store.save(self._make_record())
        loaded = self.store.load("turn_1")
        assert loaded is not None
        assert loaded.player_input == "hello"

    def test_duplicate_turn_error(self):
        self.store.save(self._make_record())
        with pytest.raises(DuplicateTurnError):
            self.store.save(self._make_record())

    def test_get_recent(self):
        for i in range(5):
            self.store.save(self._make_record(turn_id=f"turn_{i}"))
        recent = self.store.get_recent("card1", "sess1", limit=3)
        assert len(recent) == 3

    def test_get_last_accepted(self):
        for i in range(3):
            self.store.save(self._make_record(turn_id=f"turn_{i}"))
        last = self.store.get_last_accepted("card1", "sess1")
        assert last is not None

    def test_empty_session(self):
        assert self.store.get_last_accepted("card1", "sess1") is None
