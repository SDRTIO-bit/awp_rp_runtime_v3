"""Tests for CardState contract."""

import pytest
from awp_rp_runtime_v2.contracts.card_state import (
    CardState, VariableEntry, EventFlag, SceneState,
    SCHEMA_ID, SCHEMA_VERSION,
)


class TestCardStateContract:
    """Test CardState data contract."""

    def test_schema_id(self):
        state = CardState()
        assert state.schema_id == SCHEMA_ID

    def test_schema_version(self):
        state = CardState()
        assert state.schema_version == SCHEMA_VERSION

    def test_card_id_session_id_required(self):
        state = CardState(card_id="", session_id="")
        errors = state.validate()
        assert "card_id is required" in errors
        assert "session_id is required" in errors

    def test_revision_non_negative(self):
        state = CardState(card_id="c", session_id="s", revision=-1)
        errors = state.validate()
        assert "revision must be non-negative" in errors

    def test_valid_state(self):
        state = CardState(card_id="c", session_id="s", revision=0)
        errors = state.validate()
        assert errors == []

    def test_serialize_roundtrip(self):
        state = CardState(
            card_id="card1",
            session_id="sess1",
            revision=5,
            variables={
                "hp": VariableEntry(name="hp", value=100, var_type="int"),
            },
            event_flags={
                "quest_started": EventFlag(event_id="quest_started", fired=True),
            },
            active_stage_ids=["stage1"],
            scene_state=SceneState(location="森林", time_of_day="黄昏"),
        )

        data = state.to_dict()
        restored = CardState.from_dict(data)

        assert restored.card_id == state.card_id
        assert restored.session_id == state.session_id
        assert restored.revision == state.revision
        assert restored.variables["hp"].value == 100
        assert restored.event_flags["quest_started"].fired is True
        assert restored.active_stage_ids == ["stage1"]
        assert restored.scene_state.location == "森林"

    def test_variable_types(self):
        for val, expected_type in [
            ("hello", "str"),
            (42, "int"),
            (3.14, "float"),
            (True, "bool"),
        ]:
            entry = VariableEntry(name="test", value=val)
            assert entry.value == val

    def test_empty_state_is_valid(self):
        state = CardState(card_id="c", session_id="s")
        errors = state.validate()
        assert errors == []
