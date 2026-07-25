"""CLI tests for autonomous NPC observability commands."""

from __future__ import annotations

import json
from argparse import Namespace
from dataclasses import replace
from pathlib import Path

import pytest

from awp_rp_runtime_v3.contracts.novel_character import NovelCharacter
from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan
from awp_rp_runtime_v3.contracts.novel_ledger import LedgerItem
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.contracts.novel_profile import default_autonomous_profile
from awp_rp_runtime_v3.scripts import novel_cli


@pytest.fixture
def novel_dir(tmp_path: Path) -> Path:
    d = tmp_path / "novel-cli"
    novel_cli.cmd_init(Namespace(dir=str(d)))
    novel_cli.cmd_seed(Namespace(dir=str(d), db=None))
    return d


def _engine(novel_dir: Path):
    return novel_cli._get_engine(novel_cli._load_state(novel_dir)["db_path"])


def _add_npc_action_ledger_item(novel_dir: Path) -> str:
    engine = _engine(novel_dir)
    pid = novel_cli._load_state(novel_dir)["project_id"]
    engine._registry.novel_character_store.save(NovelCharacter(
        character_id="c1",
        project_id=pid,
        name="陈默",
        role="主角",
        first_appearance=1,
    ))
    engine._registry.novel_chapter_plan_store.save(ChapterPlan(
        chapter_id="ch1", project_id=pid, chapter_index=1, target_chars=100
    ))
    item = LedgerItem(
        item_id="npc-action-1",
        project_id=pid,
        section="npc_action",
        entity="配角甲",
        content="在暗处观察主角",
        status="active",
        source_chapter=1,
    )
    engine._registry.novel_ledger_store.upsert(item)
    return item.item_id


def test_init_writes_the_complete_default_autonomous_profile(tmp_path: Path) -> None:
    novel_dir = tmp_path / "initialized-novel"

    novel_cli.cmd_init(Namespace(dir=str(novel_dir)))

    project = json.loads((novel_dir / "project.json").read_text(encoding="utf-8"))["project"]
    assert project["config"]["autonomous_profile"] == (
        default_autonomous_profile().model_dump(mode="json")
    )


def test_promote_state_cli_updates_character_state(novel_dir: Path, capsys) -> None:
    item_id = _add_npc_action_ledger_item(novel_dir)
    args = Namespace(
        dir=str(novel_dir),
        character_id="c1",
        source=item_id,
        patch=json.dumps({"emotion": "紧张", "location": "走廊"}),
    )
    novel_cli.cmd_promote_state(args)

    engine = _engine(novel_dir)
    character = engine._registry.novel_character_store.load("c1")
    assert character.current_state["emotion"] == "紧张"
    assert character.current_state["location"] == "走廊"
    assert character.current_state["promoted_from_item_id"] == item_id
    assert "promoted_at" in character.current_state

    captured = capsys.readouterr().out
    assert "已提升角色状态" in captured


def test_promote_state_cli_rejects_forbidden_keys(novel_dir: Path, capsys) -> None:
    item_id = _add_npc_action_ledger_item(novel_dir)
    args = Namespace(
        dir=str(novel_dir),
        character_id="c1",
        source=item_id,
        patch=json.dumps({"identity": "卧底"}),
    )
    novel_cli.cmd_promote_state(args)

    engine = _engine(novel_dir)
    character = engine._registry.novel_character_store.load("c1")
    assert "identity" not in character.current_state

    captured = capsys.readouterr().out
    assert "禁止写入的键" in captured


def test_promote_state_cli_rejects_non_npc_action_source(novel_dir: Path, capsys) -> None:
    engine = _engine(novel_dir)
    pid = novel_cli._load_state(novel_dir)["project_id"]
    engine._registry.novel_character_store.save(NovelCharacter(
        character_id="c1",
        project_id=pid,
        name="陈默",
        role="主角",
        first_appearance=1,
    ))
    engine._registry.novel_ledger_store.upsert(LedgerItem(
        item_id="not-npc-action",
        project_id=pid,
        section="chapter_summary",
        entity="ch1",
        content="summary",
        status="active",
        source_chapter=1,
    ))

    args = Namespace(
        dir=str(novel_dir),
        character_id="c1",
        source="not-npc-action",
        patch=json.dumps({"emotion": "紧张"}),
    )
    novel_cli.cmd_promote_state(args)

    captured = capsys.readouterr().out
    assert "source 必须是本项目已接受的 npc_action" in captured
