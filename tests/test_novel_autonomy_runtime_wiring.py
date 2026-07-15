"""Runtime wiring tests for autonomous novel NPC planning."""

from __future__ import annotations

import json

import pytest

from awp_rp_runtime_v3.contracts.novel_character import NovelCharacter
from awp_rp_runtime_v3.contracts.novel_chapter import ContentSummary
from awp_rp_runtime_v3.contracts.novel_npc_agenda import (
    NpcAgenda,
    SelectedNpcAction,
    VisibleConsequence,
)
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.contracts.novel_profile import (
    PROFILE_CONFIG_KEY,
    default_autonomous_profile,
)
from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan
from awp_rp_runtime_v3.contracts.novel_director_guidance import DirectorGuidance
from awp_rp_runtime_v3.contracts.novel_npc_agenda import NpcAction
from awp_rp_runtime_v3.runtime.novel_director_adapter import NovelDirectorAdapter
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.novel_npc_agenda_adapter import NovelNpcAgendaAdapter
from awp_rp_runtime_v3.runtime.novel_profile_compiler import NovelProfileCompiler


def test_profile_is_nonempty_and_role_layered() -> None:
    p = default_autonomous_profile()
    assert p.narrative["language"] == "zh-CN"
    assert p.agent_contracts["npc_planner"]["response_format"] == "npc_agenda_json"
    planner = NovelProfileCompiler().compile_for(
        "npc_planner",
        p,
        world_rules=["守恒"],
        history="已接受",
        scene="雨夜",
        character_context={},
    )
    writer = NovelProfileCompiler().compile_for(
        "writer",
        p,
        world_rules=["守恒"],
        history="已接受",
        scene="雨夜",
        character_context={},
    )
    assert planner["world_rules"] == ["守恒"]
    assert "world_rules" not in writer


# ────────────────────────────────────────────────────────────────────────────
# Task 2: the real write path must call the Pi planner and the Director selection
# ────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def reg(tmp_path):
    from awp_rp_runtime_v3.runtime.session_runtime_registry import (
        SessionRuntimeStoreRegistry,
    )
    from awp_rp_runtime_v3.storage.sqlite.database import Database

    db = Database(str(tmp_path / "novel.db"))
    db.initialize()
    return SessionRuntimeStoreRegistry(db)


@pytest.fixture
def engine(reg):
    return NovelEngine(reg)


def _agenda(agenda_id: str = "agenda-1", npc: str = "配角甲") -> NpcAgenda:
    return NpcAgenda(
        agenda_id=agenda_id,
        thread_key="observe",
        npc=npc,
        private_goal="私密目标",
        known_fact_ids=("fact-1",),
        resources=(),
        cost="",
        next_action="",
        trigger="",
        risk="",
        visible_consequence=VisibleConsequence(
            agenda_id=agenda_id,
            beat_id="b1",
            observable_event="配角甲截走药材",
            observable_clue="墙角残留药渣",
            affected_characters=("主角",),
        ),
        deadline="3",
    )


def _selected(agenda_id: str = "agenda-1") -> SelectedNpcAction:
    return SelectedNpcAction(
        agenda_id=agenda_id,
        character_name="配角甲",
        reasoning="推进观察线",
        visible_consequence=_agenda(agenda_id).visible_consequence,
    )


def _setup_real_path_project(reg):
    """A project whose plan text names a character so the planner finds a candidate."""
    reg.novel_project_store.create(
        NovelProject(project_id="p1", title="测试", status="writing")
    )
    # Plan text must mention the candidate character so the agenda service marks it eligible.
    reg.novel_chapter_plan_store.save(
        ChapterPlan(
            chapter_id="ch1",
            project_id="p1",
            chapter_index=1,
            target_chars=100,
            title="截药",
            content_summary=ContentSummary(
                cause="主角发现药材失窃",
                development="配角甲在暗处行动",
            ),
        )
    )
    reg.novel_character_store.save(
        NovelCharacter(
            character_id="c1",
            project_id="p1",
            name="配角甲",
            role="配角",
            first_appearance=1,
            core_motivation="夺回药材",
        )
    )


def test_real_write_path_calls_planner_and_director(
    monkeypatch, reg, engine, fake_novel_role_runtime,
):
    """Both write_chapter paths must invoke the Pi planner then the Director selection."""
    _setup_real_path_project(reg)

    calls: list[str] = []

    # Record planner invocations and return one deterministic agenda.
    monkeypatch.setattr(
        NovelNpcAgendaAdapter,
        "propose",
        lambda *a, **k: calls.append("planner") or (_agenda(),),
    )
    # Record Director selection invocations and return one selected action.
    def _select(self, agendas, selected_ids):
        calls.append("director")
        return (_selected(),)

    monkeypatch.setattr(NovelDirectorAdapter, "select_npc_actions", _select)

    engine.write_chapter(project_id="p1", chapter_index=1)
    assert calls == ["planner", "director"]


def test_real_stream_path_calls_planner_and_director(
    monkeypatch, reg, engine, fake_novel_role_runtime,
):
    _setup_real_path_project(reg)
    calls: list[str] = []

    monkeypatch.setattr(
        NovelNpcAgendaAdapter,
        "propose",
        lambda *a, **k: calls.append("planner") or (_agenda(),),
    )
    monkeypatch.setattr(
        NovelDirectorAdapter,
        "select_npc_actions",
        lambda self, agendas, selected_ids: calls.append("director") or (_selected(),),
    )

    engine.write_chapter_stream(project_id="p1", chapter_index=1)
    assert calls == ["planner", "director"]