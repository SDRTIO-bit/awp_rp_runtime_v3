from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import json
import os

from ..contracts.card_definition import CardDefinition, CardDefinitionStatus
from ..contracts.card_session_binding import CardSessionBinding
from ..contracts.card_state_commit import CardStateCommitRequest
from ..contracts.card_state_patch import CardStatePatch
from ..contracts.card_state import CardState, SceneState
from ..contracts.final_turn_brief import FinalTurnBrief
from ..contracts.opening_record import OpeningRecord
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.turn_record import TurnMode, TurnRecord
from ..contracts.worldbook_binding import WorldbookBinding, WorldbookBindingEntry
from ..runtime.session_runtime_registry import SessionRuntimeStoreRegistry
from ..runtime.writer_input_bundle_v2_builder import WriterInputBundleV2Builder
from ..runtime.runtime_store_factory import clear_registry_cache
from ..storage.sqlite.card_definition_store import SqliteCardDefinitionStore
from ..storage.sqlite.database import Database


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _make_db(tmp_path: str) -> Database:
    db = Database(str(Path(tmp_path) / "test.db"))
    db.initialize()
    return db


def _close_db(db: Database) -> None:
    db.close()


def _make_card_definition(
    *,
    logical_card_id: str,
    card_version: int,
    source_hash: str,
    greeting_text: str,
    worldbook_entries: list[dict],
) -> CardDefinition:
    return CardDefinition(
        logical_card_id=logical_card_id,
        card_version=card_version,
        source_id=f"src_{card_version}",
        source_hash=source_hash,
        name="TestCard",
        display_name="TestCard",
        status=CardDefinitionStatus.READY,
        greetings=[{
            "schema_id": "awp.rp.card-greeting.v1",
            "schema_version": 1,
            "greeting_id": "g0",
            "index": 0,
            "label": "Default",
            "safe_display_content": greeting_text,
            "content_hash": f"gh_{card_version}",
            "is_default": True,
            "source_path": "data.first_mes",
        }],
        worldbook_catalog=worldbook_entries,
        worldbook_chunks=[],
        created_at=_now(),
        updated_at=_now(),
    )


def _seed_bound_session(
    registry: SessionRuntimeStoreRegistry,
    *,
    session_id: str,
    logical_card_id: str,
    card_version: int,
    source_hash: str,
    opening_text: str = "Welcome to the Hearthstone Tavern.",
) -> None:
    registry.card_session_binding_store.save(CardSessionBinding(
        session_id=session_id,
        logical_card_id=logical_card_id,
        card_version=card_version,
        source_hash=source_hash,
        selected_greeting_id="g0",
        opening_record_id=f"op_{session_id}",
        worldbook_binding_id=f"wb_{session_id}",
        status="ready",
        created_at=_now(),
    ))
    registry.opening_record_store.save(OpeningRecord(
        opening_record_id=f"op_{session_id}",
        session_id=session_id,
        logical_card_id=logical_card_id,
        card_version=card_version,
        greeting_id="g0",
        safe_display_content=opening_text,
        source_greeting_ref=f"{logical_card_id}/v{card_version}/greetings/g0",
        created_at=_now(),
    ))
    registry.worldbook_binding_store.save(WorldbookBinding(
        worldbook_binding_id=f"wb_{session_id}",
        session_id=session_id,
        logical_card_id=logical_card_id,
        card_version=card_version,
        source_hash=source_hash,
        bound_entry_ids=["wb_1", "wb_2"],
        disabled_entry_ids=[],
        deferred_entry_ids=[],
        unsupported_activation_entry_ids=[],
        entries=[
            WorldbookBindingEntry(
                entry_id="wb_1",
                source_uid=1,
                enabled=True,
                constant=True,
                selective=False,
                has_chunks=False,
                activation_status="candidate",
            ).to_dict(),
            WorldbookBindingEntry(
                entry_id="wb_2",
                source_uid=2,
                enabled=True,
                constant=False,
                selective=True,
                has_chunks=False,
                activation_status="candidate",
            ).to_dict(),
        ],
        created_at=_now(),
    ))
    registry.card_state_store.initialize(logical_card_id, session_id)


class TestVersionLockedWorldbookResolver:

    def test_resolves_exact_bound_card_version_not_latest(self):
        from ..runtime.version_locked_worldbook_resolver import VersionLockedWorldbookResolver

        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            registry = SessionRuntimeStoreRegistry(db)
            defs = SqliteCardDefinitionStore(db)

            defs.save(_make_card_definition(
                logical_card_id="card_alpha",
                card_version=1,
                source_hash="hash_v1",
                greeting_text="V1 greeting",
                worldbook_entries=[
                    {
                        "schema_id": "awp.rp.card-worldbook-entry.v1",
                        "schema_version": 1,
                        "entry_id": "wb_1",
                        "source_uid": 1,
                        "title": "Tavern",
                        "content": "V1 tavern facts with the original hearthfire details.",
                        "keys": ["tavern", "hearthstone"],
                        "secondary_keys": [],
                        "priority": 100,
                        "enabled": True,
                        "constant": True,
                        "selective": False,
                        "activation_raw": {},
                        "source_order": 0,
                        "source_path": "data.character_book.entries[0]",
                        "metadata": {},
                        "quarantine_refs": [],
                        "has_chunks": False,
                    },
                    {
                        "schema_id": "awp.rp.card-worldbook-entry.v1",
                        "schema_version": 1,
                        "entry_id": "wb_2",
                        "source_uid": 2,
                        "title": "Quest Board",
                        "content": "V1 quest board lore appears when the player asks about quests.",
                        "keys": ["quest", "quests", "adventure"],
                        "secondary_keys": [],
                        "priority": 80,
                        "enabled": True,
                        "constant": False,
                        "selective": True,
                        "activation_raw": {},
                        "source_order": 1,
                        "source_path": "data.character_book.entries[1]",
                        "metadata": {},
                        "quarantine_refs": [],
                        "has_chunks": False,
                    },
                ],
            ))
            defs.save(_make_card_definition(
                logical_card_id="card_alpha",
                card_version=2,
                source_hash="hash_v2",
                greeting_text="V2 greeting",
                worldbook_entries=[
                    {
                        "schema_id": "awp.rp.card-worldbook-entry.v1",
                        "schema_version": 1,
                        "entry_id": "wb_1",
                        "source_uid": 1,
                        "title": "Tavern",
                        "content": "V2 rewritten tavern facts that must not leak into the old session.",
                        "keys": ["tavern", "hearthstone"],
                        "secondary_keys": [],
                        "priority": 100,
                        "enabled": True,
                        "constant": True,
                        "selective": False,
                        "activation_raw": {},
                        "source_order": 0,
                        "source_path": "data.character_book.entries[0]",
                        "metadata": {},
                        "quarantine_refs": [],
                        "has_chunks": False,
                    },
                ],
            ))

            _seed_bound_session(
                registry,
                session_id="sess_v1",
                logical_card_id="card_alpha",
                card_version=1,
                source_hash="hash_v1",
            )
            binding = registry.card_session_binding_store.load("sess_v1")
            opening = registry.opening_record_store.get_by_session("sess_v1")
            wb_binding = registry.worldbook_binding_store.get_by_session("sess_v1")

            resolver = VersionLockedWorldbookResolver(defs)
            result = resolver.resolve(
                binding=binding,
                worldbook_binding=wb_binding,
                opening_record=opening,
                player_input="Tell me about the quest board in this tavern.",
                recent_turns=[],
            )

            activated = result["activated_content"]
            assert any(item["entry_id"] == "wb_1" for item in activated)
            assert any(item["entry_id"] == "wb_2" for item in activated)
            assert all("V2 rewritten" not in item["content_excerpt"] for item in activated)
            assert any("V1 tavern facts" in item["content_excerpt"] for item in activated)
            assert any("V1 quest board lore" in item["content_excerpt"] for item in activated)
            _close_db(db)

    def test_missing_exact_source_hash_fails_closed(self):
        from ..runtime.version_locked_worldbook_resolver import VersionLockedWorldbookResolver

        with tempfile.TemporaryDirectory() as tmp:
            db = _make_db(tmp)
            registry = SessionRuntimeStoreRegistry(db)
            defs = SqliteCardDefinitionStore(db)

            defs.save(_make_card_definition(
                logical_card_id="card_alpha",
                card_version=2,
                source_hash="hash_v2",
                greeting_text="V2 greeting",
                worldbook_entries=[],
            ))
            _seed_bound_session(
                registry,
                session_id="sess_v1",
                logical_card_id="card_alpha",
                card_version=1,
                source_hash="hash_v1",
            )

            binding = registry.card_session_binding_store.load("sess_v1")
            opening = registry.opening_record_store.get_by_session("sess_v1")
            wb_binding = registry.worldbook_binding_store.get_by_session("sess_v1")
            resolver = VersionLockedWorldbookResolver(defs)

            with pytest.raises(ValueError, match="hash_v1"):
                resolver.resolve(
                    binding=binding,
                    worldbook_binding=wb_binding,
                    opening_record=opening,
                    player_input="Hello",
                    recent_turns=[],
                )
            _close_db(db)


class TestWriterInputBundleV2BuilderP0:

    def test_build_includes_opening_worldbook_recent_turns_and_state_contexts(self):
        builder = WriterInputBundleV2Builder()
        snapshot = RoundSnapshot(
            snapshot_id="snap_001",
            trace_id="trace_001",
            card_id="card_alpha",
            session_id="sess_001",
            base_card_state_revision=3,
            card_state=CardState(
                card_id="card_alpha",
                session_id="sess_001",
                revision=3,
                scene_state=SceneState(location="Hearthstone Tavern", description="Busy common room"),
            ),
            player_input="Tell me what happened last night.",
            recent_turn_records=[
                TurnRecord(
                    turn_id="turn_002",
                    trace_id="trc_002",
                    card_id="card_alpha",
                    session_id="sess_001",
                    turn_index=2,
                    mode=TurnMode.NORMAL,
                    player_input="What are you hiding?",
                    writer_output="The keeper hesitates and glances toward the bar.",
                ),
                TurnRecord(
                    turn_id="turn_001",
                    trace_id="trc_001",
                    card_id="card_alpha",
                    session_id="sess_001",
                    turn_index=1,
                    mode=TurnMode.NORMAL,
                    player_input="Hello there.",
                    writer_output="Welcome to the tavern, traveler.",
                ),
            ],
            active_worldbook_entries=[
                {
                    "entry_id": "wb_1",
                    "title": "Tavern",
                    "content_excerpt": "The tavern sits on old stone foundations.",
                    "activation_reason": "constant",
                    "matched_keywords": [],
                    "source_entry_id": "wb_1",
                    "source_hash": "hash_v1",
                    "budget_rank": 1,
                    "entry_kind": "constant",
                }
            ],
            active_memories=[{"memory_id": "mem_1", "summary": "Player promised to return tomorrow."}],
            rag_recall=[{"memory_id": "rag_1", "summary": "Ancient ruins under the tavern."}],
        )
        brief = FinalTurnBrief(
            brief_id="brief_001",
            trace_id="trace_001",
            snapshot_id="snap_001",
            card_id="card_alpha",
            session_id="sess_001",
            base_card_state_revision=3,
            turn_goal="Advance the tavern mystery",
            scene_focus="Bar counter",
            writer_constraints=["Stay in character"],
        )

        bundle = builder.build(
            snapshot,
            brief,
            merge_result=None,
            opening_context={
                "opening_record_id": "op_sess_001",
                "greeting_id": "g0",
                "safe_display_content": "Welcome to the Hearthstone Tavern.",
                "source_hash_ref": "hash_v1",
            },
            worldbook_context=snapshot.active_worldbook_entries,
        )

        assert bundle.player_input == "Tell me what happened last night."
        assert bundle.opening_context["greeting_id"] == "g0"
        assert bundle.worldbook_context[0]["content_excerpt"].startswith("The tavern sits")
        assert bundle.recent_turns_context[0]["player_input"] == "What are you hiding?"
        assert bundle.recent_turns_context[0]["writer_output"] == "The keeper hesitates and glances toward the bar."
        assert bundle.card_state_context["scene_state"]["location"] == "Hearthstone Tavern"
        assert bundle.active_memory_context[0]["summary"] == "Player promised to return tomorrow."
        assert bundle.rag_memory_context[0]["summary"] == "Ancient ruins under the tavern."


class TestAcceptedTextOutputNode:

    def test_outputs_full_writer_text_without_extra_query_inputs(self):
        from ..nodes.accepted_text_output_node import AWPV2AcceptedTextOutput

        node = AWPV2AcceptedTextOutput()
        turn_record = TurnRecord(
            turn_id="turn_001",
            trace_id="trc_001",
            card_id="card_alpha",
            session_id="sess_001",
            turn_index=1,
            mode=TurnMode.NORMAL,
            player_input="Hello",
            writer_output="Full accepted writer output.",
        )

        result = node.execute(turn_record=turn_record.to_dict())

        assert result == {"ui": {"awp_accepted_text": ["Full accepted writer output."]}}
        input_types = node.INPUT_TYPES()
        assert set(input_types["required"].keys()) == {"turn_record"}


class TestPersistentNodeCacheContracts:

    def test_first_turn_cache_identity_changes_with_new_request(self):
        from ..nodes.persistent_first_turn_node import AWPV2PersistentFirstTurn

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AWP_RUNTIME_PROFILE"] = "test"
            os.environ["AWP_TEST_STORE_ROOT"] = tmp
            os.environ["AWP_TEST_RUNTIME_NAMESPACE"] = "cache_first_turn"
            clear_registry_cache()
            try:
                from ..runtime.runtime_store_factory import RuntimeStoreFactory

                registry = RuntimeStoreFactory.from_env().registry
                _seed_bound_session(
                    registry,
                    session_id="sess_cache",
                    logical_card_id="card_alpha",
                    card_version=1,
                    source_hash="hash_v1",
                )
                fp1 = AWPV2PersistentFirstTurn.IS_CHANGED(
                    session_id="sess_cache",
                    player_input="Hello there",
                    turn_id="turn_001",
                    request_id="req_001",
                )
                fp2 = AWPV2PersistentFirstTurn.IS_CHANGED(
                    session_id="sess_cache",
                    player_input="Hello there",
                    turn_id="turn_002",
                    request_id="req_002",
                )
                assert fp1 != fp2
                assert "hash_v1" in fp1
                assert any("op_sess_cache" == item for item in fp1)
            finally:
                clear_registry_cache()
                os.environ.pop("AWP_TEST_STORE_ROOT", None)
                os.environ.pop("AWP_TEST_RUNTIME_NAMESPACE", None)

    def test_continuation_cache_identity_tracks_latest_turn_and_revision(self):
        from ..nodes.persistent_continuation_turn_node import AWPV2PersistentContinuationTurn

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AWP_RUNTIME_PROFILE"] = "test"
            os.environ["AWP_TEST_STORE_ROOT"] = tmp
            os.environ["AWP_TEST_RUNTIME_NAMESPACE"] = "cache_continuation"
            clear_registry_cache()
            try:
                from ..runtime.runtime_store_factory import RuntimeStoreFactory

                registry = RuntimeStoreFactory.from_env().registry
                _seed_bound_session(
                    registry,
                    session_id="sess_cache",
                    logical_card_id="card_alpha",
                    card_version=1,
                    source_hash="hash_v1",
                )
                fp_before = AWPV2PersistentContinuationTurn.IS_CHANGED(
                    session_id="sess_cache",
                    player_input="Continue",
                    turn_id="turn_002",
                    request_id="req_002",
                )
                registry.turn_record_store.save(TurnRecord(
                    turn_id="turn_001",
                    trace_id="trc_001",
                    card_id="card_alpha",
                    session_id="sess_cache",
                    turn_index=1,
                    mode=TurnMode.NORMAL,
                    player_input="Hello",
                    writer_output="Accepted output",
                    base_card_state_revision=0,
                    result_card_state_revision=1,
                    created_at=_now(),
                ))
                current_state = registry.card_state_store.load("card_alpha", "sess_cache")
                registry.card_state_store.commit(
                    CardStateCommitRequest(
                        expected_revision=0,
                        patch=CardStatePatch(
                            patch_id="patch_001",
                            card_id="card_alpha",
                            session_id="sess_cache",
                            trace_id="trc_patch",
                        ),
                    ),
                    CardState(
                        card_id="card_alpha",
                        session_id="sess_cache",
                        revision=1,
                        created_at=current_state.created_at,
                        updated_at=_now(),
                    ),
                )
                fp_after = AWPV2PersistentContinuationTurn.IS_CHANGED(
                    session_id="sess_cache",
                    player_input="Continue",
                    turn_id="turn_002",
                    request_id="req_002",
                )
                assert fp_before != fp_after
                assert "turn_001" in fp_after
                assert 1 in fp_after
            finally:
                clear_registry_cache()
                os.environ.pop("AWP_TEST_STORE_ROOT", None)
                os.environ.pop("AWP_TEST_RUNTIME_NAMESPACE", None)

    def test_bootstrap_cache_identity_tracks_source_hash_changes(self):
        from ..nodes.persistent_bootstrap_node import AWPV2PersistentBootstrap

        with tempfile.TemporaryDirectory() as tmp:
            card_path = Path(tmp) / "card.json"
            payload_v1 = {
                "spec": "chara_card_v3",
                "data": {
                    "name": "Cache Card",
                    "first_mes": "Greeting v1",
                    "character_book": {"entries": []},
                },
            }
            payload_v2 = {
                "spec": "chara_card_v3",
                "data": {
                    "name": "Cache Card",
                    "first_mes": "Greeting v2",
                    "character_book": {"entries": []},
                },
            }
            card_path.write_text(json.dumps(payload_v1, ensure_ascii=False), encoding="utf-8")
            fp1 = AWPV2PersistentBootstrap.IS_CHANGED(
                source_path=str(card_path),
                session_id="sess_bootstrap",
                greeting_id="g0",
                request_id="req_bootstrap",
            )
            card_path.write_text(json.dumps(payload_v2, ensure_ascii=False), encoding="utf-8")
            fp2 = AWPV2PersistentBootstrap.IS_CHANGED(
                source_path=str(card_path),
                session_id="sess_bootstrap",
                greeting_id="g0",
                request_id="req_bootstrap_2",
            )
            assert fp1 != fp2
            assert str(card_path) in fp1
            assert str(card_path) in fp2
