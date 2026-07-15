"""Contracts for autonomous novel NPC agenda planning."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest
from pydantic import ValidationError

from awp_rp_runtime_v3.contracts.novel_director_guidance import DirectorGuidance
from awp_rp_runtime_v3.contracts.novel_npc_agenda import NpcAgenda, VisibleConsequence
from awp_rp_runtime_v3.contracts.novel_profile import (
    PROFILE_CONFIG_KEY,
    NovelProfileError,
    NovelWritingProfile,
    load_autonomous_profile,
)
from awp_rp_runtime_v3.contracts.novel_write_packet import NovelWritePacket
from awp_rp_runtime_v3.scripts import novel_cli


def test_load_autonomous_profile_rejects_missing_profile() -> None:
    with pytest.raises(NovelProfileError, match="profile"):
        load_autonomous_profile({})


def test_load_autonomous_profile_rejects_rp_mode() -> None:
    with pytest.raises(NovelProfileError, match="mode"):
        load_autonomous_profile(
            {
                "autonomous_profile": {
                    "schema_id": "awp.novel.writing-profile.v1",
                    "schema_version": 1,
                    "mode": "rp",
                    "name": "legacy",
                    "narrative": {},
                    "world": {},
                    "history": {},
                    "scene": {},
                    "agent_contracts": {},
                }
            }
        )


def test_npc_agenda_rejects_non_id_fact_reference() -> None:
    with pytest.raises(ValidationError):
        NpcAgenda.model_validate_json(
            json.dumps(
                {
                    "agenda_id": "agenda-1",
                    "thread_key": "thread-1",
                    "npc": "李四",
                    "private_goal": "藏起证据",
                    "known_fact_ids": [{"item_id": "ledger-1", "content": "证据在抽屉"}],
                    "resources": ["钥匙"],
                    "cost": "失去信任",
                    "next_action": "转移证据",
                    "trigger": "主角接近抽屉",
                    "risk": "被目击",
                    "visible_consequence": {
                        "agenda_id": "agenda-1",
                        "beat_id": "beat-1",
                        "observable_event": "抽屉被打开过",
                        "observable_clue": "锁孔有新划痕",
                        "affected_characters": ["主角"],
                    },
                    "deadline": "本章结束前",
                }
            )
        )


def test_npc_agenda_rejects_fact_description_instead_of_id() -> None:
    with pytest.raises(ValidationError):
        NpcAgenda.model_validate(
            {
                "agenda_id": "agenda-1",
                "thread_key": "thread-1",
                "npc": "李四",
                "private_goal": "藏起证据",
                "known_fact_ids": ["证据在抽屉里"],
                "resources": ["钥匙"],
                "cost": "失去信任",
                "next_action": "转移证据",
                "trigger": "主角接近抽屉",
                "risk": "被目击",
                "visible_consequence": {
                    "agenda_id": "agenda-1",
                    "beat_id": "beat-1",
                    "observable_event": "抽屉被打开过",
                    "observable_clue": "锁孔有新划痕",
                    "affected_characters": ["主角"],
                },
                "deadline": "本章结束前",
            }
        )


def test_profile_is_frozen_and_forbids_unknown_fields() -> None:
    profile = NovelWritingProfile(
        mode="novel",
        name="test-profile",
        narrative={},
        world={},
        history={},
        scene={},
        agent_contracts={},
    )

    with pytest.raises(ValidationError):
        NovelWritingProfile.model_validate({**profile.model_dump(), "unknown": True})
    with pytest.raises(ValidationError):
        profile.name = "changed"  # type: ignore[misc]


def test_visible_consequences_round_trip_to_director_and_writer_packet() -> None:
    consequence = VisibleConsequence(
        agenda_id="agenda-1",
        beat_id="beat-1",
        observable_event="窗户被打开",
        observable_clue="窗台有泥印",
        affected_characters=("主角", "李四"),
    )
    assert set(consequence.model_dump()) == {
        "agenda_id",
        "beat_id",
        "observable_event",
        "observable_clue",
        "affected_characters",
    }

    guidance = DirectorGuidance(visible_consequences=(consequence,))
    restored_guidance = DirectorGuidance.from_dict(guidance.to_dict())
    assert restored_guidance.visible_consequences == (consequence,)

    packet = NovelWritePacket(visible_consequences=(consequence,))
    restored_packet = NovelWritePacket.from_dict(packet.to_dict())
    assert restored_packet.visible_consequences == (consequence,)


def test_init_and_seed_keep_the_default_profile_explicit(tmp_path: Path) -> None:
    novel_dir = tmp_path / "new-novel"
    novel_cli.cmd_init(Namespace(dir=str(novel_dir)))

    project = json.loads((novel_dir / "project.json").read_text(encoding="utf-8"))
    profile = load_autonomous_profile(project["project"]["config"])
    assert profile.mode == "novel"

    novel_cli.cmd_seed(Namespace(dir=str(novel_dir), db=None))
    state = novel_cli._load_state(novel_dir)
    engine = novel_cli._get_engine(state["db_path"])
    saved = engine._registry.novel_project_store.load(state["project_id"])
    assert saved is not None
    assert load_autonomous_profile(saved.config) == profile


def test_seed_requires_old_projects_to_run_profile_init(tmp_path: Path) -> None:
    (tmp_path / "project.json").write_text(
        json.dumps({"project": {"id": "old", "title": "Old project"}}),
        encoding="utf-8",
    )

    with pytest.raises(NovelProfileError, match="profile-init"):
        novel_cli.cmd_seed(Namespace(dir=str(tmp_path), db=None))

    novel_cli.cmd_profile_init(Namespace(dir=str(tmp_path)))
    project = json.loads((tmp_path / "project.json").read_text(encoding="utf-8"))
    assert PROFILE_CONFIG_KEY in project["project"]["config"]
