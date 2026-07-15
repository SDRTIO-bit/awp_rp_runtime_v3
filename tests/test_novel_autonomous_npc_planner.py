"""Tests for the Pi-backed NPC agenda planner adapter."""

from __future__ import annotations

import json

import pytest

from awp_rp_runtime_v3.contracts.novel_chapter import BeatDetail, ChapterPlan, ContentSummary
from awp_rp_runtime_v3.contracts.novel_character import NovelCharacter
from awp_rp_runtime_v3.contracts.novel_npc_agenda import NpcAgenda, SelectedNpcAction, VisibleConsequence
from awp_rp_runtime_v3.contracts.novel_pi_role_protocol import NovelPiRoleResult
from awp_rp_runtime_v3.runtime.novel_director_adapter import NovelDirectorAdapter
from awp_rp_runtime_v3.runtime.novel_npc_agenda_adapter import NovelNpcAgendaAdapter
from awp_rp_runtime_v3.runtime.novel_role_context import novel_role_scope


@pytest.fixture
def reg(tmp_path):
    from awp_rp_runtime_v3.runtime.session_runtime_registry import (
        SessionRuntimeStoreRegistry,
    )
    from awp_rp_runtime_v3.storage.sqlite.database import Database

    db = Database(str(tmp_path / "novel.db"))
    db.initialize()
    return SessionRuntimeStoreRegistry(db)


class RecordingRoleRuntime:
    def __init__(self, text: str):
        self.text = text
        self.tasks = []
        self.contexts = []

    def run(self, task, *, context, on_chunk=None):
        del on_chunk
        self.tasks.append(task)
        self.contexts.append(context)
        return NovelPiRoleResult(
            request_id=f"req-{len(self.tasks)}",
            role=task.role,
            session_key=task.session_key,
            text=self.text,
            model="kimi-k2.6",
        )


def _plan() -> ChapterPlan:
    return ChapterPlan(
        chapter_id="ch-p1-1",
        project_id="p1",
        chapter_index=1,
        title="暗流涌动",
        target_chars=3000,
        content_summary=ContentSummary(
            cause="沈砚发现旧案卷宗被调换",
            development="陆遥暗中跟踪嫌疑人",
        ),
        scene_beats=(
            BeatDetail(
                beat_id="b1",
                description="沈砚在档案室发现卷宗缺失",
                function_tag="铺垫",
                budget_chars=900,
            ),
        ),
    )


def _candidates() -> tuple[NovelCharacter, ...]:
    return (
        NovelCharacter(
            character_id="c1",
            project_id="p1",
            name="沈砚",
            first_appearance=1,
            core_motivation="追查真相",
        ),
        NovelCharacter(
            character_id="c2",
            project_id="p1",
            name="陆遥",
            first_appearance=1,
            core_motivation="保护同伴",
        ),
    )


def _profile() -> dict:
    return {
        "profile_name": "悬疑短篇",
        "narrative": "都市悬疑",
        "agent_contract": {"npc_planner": {"tone": "克制"}},
        "world": ["江城", "旧档案馆"],
        "history": "三年前旧案",
        "scene": "深夜档案室",
    }


def _valid_agenda_json() -> str:
    return json.dumps({
        "agendas": [
            {
                "agenda_id": "agenda-1",
                "thread_key": "archive-tampering",
                "npc": "陆遥",
                "private_goal": "在沈砚之前拿到真卷宗",
                "known_fact_ids": ("ledger-p1-7",),
                "resources": ("摩托车", "暗线人脉"),
                "cost": "暴露跟踪习惯",
                "next_action": "提前到达交接点",
                "trigger": "沈砚离开档案室",
                "risk": "被反跟踪",
                "visible_consequence": {
                    "agenda_id": "agenda-1",
                    "beat_id": "b1",
                    "observable_event": "档案室外传来摩托车引擎声",
                    "observable_clue": "陆遥的皮手套落在窗台",
                    "affected_characters": ("沈砚",),
                },
                "deadline": "3",
            },
        ],
    }, ensure_ascii=False)


def test_planner_is_a_dedicated_pi_role(monkeypatch, reg):
    runtime = RecordingRoleRuntime(_valid_agenda_json())
    monkeypatch.setattr(
        "awp_rp_runtime_v3.runtime.novel_npc_agenda_adapter.get_novel_role_runtime",
        lambda: runtime,
        raising=False,
    )

    with novel_role_scope(registry=reg, project_id="p1", chapter_index=1):
        result = NovelNpcAgendaAdapter().propose(
            "p1", _plan(), _candidates(), (), _profile()
        )

    assert len(result) == 1
    assert result[0].agenda_id == "agenda-1"
    assert runtime.tasks[0].role == "npc_planner"
    assert runtime.tasks[0].session_key.startswith("task:")
    assert runtime.tasks[0].input_payload["response_format"] == "npc_agenda_json"


def test_planner_drops_invalid_agendas(monkeypatch, reg):
    payload = json.dumps({
        "agendas": [
            {
                "agenda_id": "agenda-1",
                "thread_key": "archive-tampering",
                "npc": "陆遥",
                "private_goal": "在沈砚之前拿到真卷宗",
                "known_fact_ids": ("ledger-p1-7",),
                "resources": ("摩托车",),
                "cost": "暴露",
                "next_action": "提前到达",
                "trigger": "离开",
                "risk": "被反跟踪",
                "visible_consequence": {
                    "agenda_id": "agenda-1",
                    "beat_id": "b1",
                    "observable_event": "引擎声",
                    "observable_clue": "手套",
                    "affected_characters": ("沈砚",),
                },
                "deadline": "3",
            },
            {
                "agenda_id": "agenda-2",
                "thread_key": "bad",
                "npc": "沈砚",
                "private_goal": "追查",
                "known_fact_ids": ("摘要",),  # invalid fact id
                "resources": (),
                "cost": "",
                "next_action": "",
                "trigger": "",
                "risk": "",
                "visible_consequence": {
                    "agenda_id": "agenda-2",
                    "beat_id": "b1",
                    "observable_event": "",
                    "observable_clue": "",
                    "affected_characters": (),
                },
                "deadline": "",
            },
        ],
    }, ensure_ascii=False)
    runtime = RecordingRoleRuntime(payload)
    monkeypatch.setattr(
        "awp_rp_runtime_v3.runtime.novel_npc_agenda_adapter.get_novel_role_runtime",
        lambda: runtime,
        raising=False,
    )

    with novel_role_scope(registry=reg, project_id="p1", chapter_index=1):
        result = NovelNpcAgendaAdapter().propose(
            "p1", _plan(), _candidates(), (), _profile()
        )

    assert len(result) == 1
    assert result[0].agenda_id == "agenda-1"


def test_planner_returns_empty_on_bad_json(monkeypatch, reg):
    runtime = RecordingRoleRuntime("not-json")
    monkeypatch.setattr(
        "awp_rp_runtime_v3.runtime.novel_npc_agenda_adapter.get_novel_role_runtime",
        lambda: runtime,
        raising=False,
    )

    with novel_role_scope(registry=reg, project_id="p1", chapter_index=1):
        result = NovelNpcAgendaAdapter().propose(
            "p1", _plan(), _candidates(), (), _profile()
        )

    assert result == ()


def _make_agenda(agenda_id: str, npc: str, thread_key: str) -> NpcAgenda:
    return NpcAgenda(
        agenda_id=agenda_id,
        thread_key=thread_key,
        npc=npc,
        private_goal="goal",
        known_fact_ids=("ledger-p1-1",),
        resources=(),
        cost="",
        next_action="",
        trigger="",
        risk="",
        visible_consequence=VisibleConsequence(
            agenda_id=agenda_id,
            beat_id="b1",
            observable_event=f"{npc} acts",
            observable_clue="clue",
            affected_characters=(" protagonist",),
        ),
        deadline="3",
    )


def test_director_selects_at_most_two_non_conflicting_actions(reg):
    agendas = (
        _make_agenda("a1", "沈砚", "thread-a"),
        _make_agenda("a2", "陆遥", "thread-b"),
        _make_agenda("a3", "沈砚", "thread-c"),  # same npc as a1 -> conflict
    )
    selected = NovelDirectorAdapter(reg).select_npc_actions(agendas, ("a1", "a2", "a3"))

    assert len(selected) == 2
    assert selected[0].agenda_id == "a1"
    assert selected[1].agenda_id == "a2"
    assert all(isinstance(a, SelectedNpcAction) for a in selected)
    assert "private_goal" not in json.dumps([a.model_dump(mode="json") for a in selected], ensure_ascii=False)


def test_director_rejects_unknown_agenda_id(reg):
    agendas = (_make_agenda("a1", "沈砚", "thread-a"),)
    selected = NovelDirectorAdapter(reg).select_npc_actions(agendas, ("a1", "unknown"))

    assert len(selected) == 1
    assert selected[0].agenda_id == "a1"
