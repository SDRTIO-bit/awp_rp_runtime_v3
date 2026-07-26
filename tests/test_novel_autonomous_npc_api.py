from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import pytest

from awp_rp_runtime_v3.contracts.novel_character import NovelCharacter
from awp_rp_runtime_v3.contracts.novel_ledger import LedgerItem
from awp_rp_runtime_v3.contracts.novel_npc_agenda import NpcAgenda, VisibleConsequence
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_api import NovelApiHandlers
from awp_rp_runtime_v3.runtime.session_runtime_registry import SessionRuntimeStoreRegistry
from awp_rp_runtime_v3.storage.sqlite.database import Database


class _Request:
    def __init__(self, match_info=None, body=None, query=None) -> None:
        self.match_info = match_info or {}
        self._body = body or {}
        self.query = query or {}

    async def json(self):
        return self._body


def _registry(tmp_path):
    db = Database(tmp_path / "api.db")
    db.initialize()
    return SessionRuntimeStoreRegistry(db)


def _data(response):
    return json.loads(response.text)["data"]


def _project_id():
    return "novel-autonomy-test"


def _make_project(registry, project_id: str):
    registry.novel_project_store.create(
        NovelProject(
            project_id=project_id,
            title="Autonomy Test",
            genre="test",
            target_platform="test",
            target_reader="test",
            core_emotion="test",
            one_sentence_pitch="test",
        )
    )


def _make_character(registry, project_id: str, character_id: str, name: str):
    char = NovelCharacter(
        character_id=character_id,
        project_id=project_id,
        name=name,
        current_state={"mood": "neutral"},
    )
    registry.novel_character_store.save(char)
    return char


def _make_agenda(
    agenda_id: str,
    npc: str,
    private_goal: str,
    deadline: str = "5",
) -> NpcAgenda:
    return NpcAgenda(
        agenda_id=agenda_id,
        thread_key=f"thread-{agenda_id}",
        npc=npc,
        private_goal=private_goal,
        known_fact_ids=("fact-1",),
        resources=("resource-1",),
        cost="low",
        next_action="investigate",
        trigger="opportunity",
        risk="low",
        visible_consequence=VisibleConsequence(
            agenda_id=agenda_id,
            beat_id="b1",
            observable_event=f"{npc} acts",
            observable_clue="a subtle clue",
            affected_characters=(npc,),
        ),
        deadline=deadline,
    )


def _make_agenda_item(project_id: str, chapter: int, agenda: NpcAgenda, status: str = "active"):
    return LedgerItem(
        item_id=f"ledger-{project_id}-ch{chapter}-agenda-{agenda.agenda_id}",
        project_id=project_id,
        section="npc_agenda",
        entity=agenda.npc,
        content=agenda.model_dump_json(),
        source_chapter=chapter,
        status=status,
    )


def _make_action_item(project_id: str, chapter: int, npc: str, consequence: VisibleConsequence):
    content = f"{consequence.observable_event} | consequence: {consequence.observable_clue}"
    return LedgerItem(
        item_id=f"ledger-{project_id}-ch{chapter}-action-{_hash(content)}",
        project_id=project_id,
        section="npc_action",
        entity=npc,
        content=content,
        source_chapter=chapter,
        status="active",
    )


def _hash(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


@pytest.fixture
def autonomy_setup(tmp_path):
    reg = _registry(tmp_path)
    pid = _project_id()
    _make_project(reg, pid)
    char = _make_character(reg, pid, "char-1", "沈砚")
    api = NovelApiHandlers(lambda: reg)
    routes = type(
        "Routes",
        (),
        {
            "handlers": {
                (
                    "GET",
                    "/awp/api/v1/novels/{project_id}/autonomy-summary",
                ): api.autonomy_summary,
                (
                    "POST",
                    "/awp/api/v1/novels/{project_id}/characters/"
                    "{character_id}/state-promotions",
                ): api.promote_character_state,
            }
        },
    )()
    return api, routes, reg, pid, char


def test_autonomy_summary_counts_active_and_stale(autonomy_setup):
    _module, routes, reg, pid, _char = autonomy_setup
    reg.novel_ledger_store.upsert(
        _make_agenda_item(pid, 1, _make_agenda("a1", "沈砚", "find the map", deadline="5"))
    )
    reg.novel_ledger_store.upsert(
        _make_agenda_item(
            pid,
            1,
            _make_agenda("a2", "陆遥", "hide the truth", deadline="1"),
            status="stale",
        )
    )
    reg.novel_ledger_store.upsert(
        _make_action_item(
            pid,
            1,
            "沈砚",
            VisibleConsequence(
                agenda_id="a1",
                beat_id="b1",
                observable_event="沈砚离开客栈",
                observable_clue="他的佩剑遗落在桌上",
                affected_characters=("沈砚",),
            ),
        )
    )
    reg.novel_ledger_store.upsert(
        _make_action_item(
            pid,
            2,
            "陆遥",
            VisibleConsequence(
                agenda_id="a2",
                beat_id="b2",
                observable_event="陆遥出现在码头",
                observable_clue="他手中握着一封密信",
                affected_characters=("陆遥",),
            ),
        )
    )

    handler = routes.handlers[("GET", "/awp/api/v1/novels/{project_id}/autonomy-summary")]
    response = asyncio.run(handler(_Request(match_info={"project_id": pid})))

    assert response.status == 200
    data = _data(response)
    assert data["active_count"] == 1
    assert data["stale_count"] == 1
    assert data["chapter_action_counts"] == {"1": 1, "2": 1}


def test_autonomy_summary_does_not_leak_private_plan(autonomy_setup):
    _module, routes, reg, pid, _char = autonomy_setup
    reg.novel_ledger_store.upsert(
        _make_agenda_item(
            pid,
            1,
            _make_agenda("a1", "沈砚", "find the secret map under the bed", deadline="5"),
        )
    )

    handler = routes.handlers[("GET", "/awp/api/v1/novels/{project_id}/autonomy-summary")]
    response = asyncio.run(handler(_Request(match_info={"project_id": pid})))

    assert response.status == 200
    data = _data(response)
    raw = json.dumps(data, ensure_ascii=False)
    assert data["active_count"] == 1
    assert "private_goal" not in raw
    assert "secret map" not in raw


def test_autonomy_summary_returns_404_for_unknown_project(autonomy_setup):
    _module, routes, _reg, _pid, _char = autonomy_setup
    handler = routes.handlers[("GET", "/awp/api/v1/novels/{project_id}/autonomy-summary")]
    response = asyncio.run(handler(_Request(match_info={"project_id": "missing"})))
    assert response.status == 404


def test_state_promotion_updates_character_current_state(autonomy_setup):
    _module, routes, reg, pid, char = autonomy_setup
    source = _make_action_item(
        pid,
        1,
        "沈砚",
        VisibleConsequence(
            agenda_id="a1",
            beat_id="b1",
            observable_event="沈砚受伤",
            observable_clue="他的手臂缠着绷带",
            affected_characters=("沈砚",),
        ),
    )
    reg.novel_ledger_store.upsert(source)

    handler = routes.handlers[
        ("POST", "/awp/api/v1/novels/{project_id}/characters/{character_id}/state-promotions")
    ]
    response = asyncio.run(
        handler(
            _Request(
                match_info={"project_id": pid, "character_id": char.character_id},
                body={"source_item_id": source.item_id, "patch": {"injured": True, "location": "inn"}},
            )
        )
    )

    assert response.status == 200
    data = _data(response)
    assert data["character_id"] == char.character_id
    assert data["promoted_from_item_id"] == source.item_id
    updated = reg.novel_character_store.load(char.character_id)
    assert updated.current_state["injured"] is True
    assert updated.current_state["location"] == "inn"
    assert updated.current_state["mood"] == "neutral"
    assert updated.current_state["promoted_from_item_id"] == source.item_id
    assert "promoted_at" in updated.current_state


def test_state_promotion_rejects_non_npc_action_source(autonomy_setup):
    _module, routes, reg, pid, char = autonomy_setup
    agenda = _make_agenda_item(
        pid,
        1,
        _make_agenda("a1", "沈砚", "find the map", deadline="5"),
    )
    reg.novel_ledger_store.upsert(agenda)

    handler = routes.handlers[
        ("POST", "/awp/api/v1/novels/{project_id}/characters/{character_id}/state-promotions")
    ]
    response = asyncio.run(
        handler(
            _Request(
                match_info={"project_id": pid, "character_id": char.character_id},
                body={"source_item_id": agenda.item_id, "patch": {"injured": True}},
            )
        )
    )

    assert response.status == 400
    assert "npc_action" in _data(response)["error"]


def test_state_promotion_rejects_forbidden_keys(autonomy_setup):
    _module, routes, reg, pid, char = autonomy_setup
    source = _make_action_item(
        pid,
        1,
        "沈砚",
        VisibleConsequence(
            agenda_id="a1",
            beat_id="b1",
            observable_event="沈砚受伤",
            observable_clue="他的手臂缠着绷带",
            affected_characters=("沈砚",),
        ),
    )
    reg.novel_ledger_store.upsert(source)

    handler = routes.handlers[
        ("POST", "/awp/api/v1/novels/{project_id}/characters/{character_id}/state-promotions")
    ]
    for forbidden in ("identity", "motivation", "known_fact_ids"):
        response = asyncio.run(
            handler(
                _Request(
                    match_info={"project_id": pid, "character_id": char.character_id},
                    body={"source_item_id": source.item_id, "patch": {forbidden: "x"}},
                )
            )
        )
        assert response.status == 400, forbidden
        assert forbidden in _data(response)["error"]


def test_state_promotion_rejects_character_from_other_project(autonomy_setup):
    _module, routes, reg, pid, char = autonomy_setup
    other_pid = "other-project"
    _make_project(reg, other_pid)
    other_char = _make_character(reg, other_pid, "char-2", "陆遥")
    source = _make_action_item(pid, 1, "沈砚", VisibleConsequence(
        agenda_id="a1", beat_id="b1",
        observable_event="事件", observable_clue="线索", affected_characters=("沈砚",)
    ))
    reg.novel_ledger_store.upsert(source)

    handler = routes.handlers[
        ("POST", "/awp/api/v1/novels/{project_id}/characters/{character_id}/state-promotions")
    ]
    response = asyncio.run(
        handler(
            _Request(
                match_info={"project_id": pid, "character_id": other_char.character_id},
                body={"source_item_id": source.item_id, "patch": {"injured": True}},
            )
        )
    )

    assert response.status == 400
    assert "project" in _data(response)["error"].lower()


def test_state_promotion_rejects_non_object_patch(autonomy_setup):
    _module, routes, reg, pid, char = autonomy_setup
    source = _make_action_item(pid, 1, "沈砚", VisibleConsequence(
        agenda_id="a1", beat_id="b1",
        observable_event="事件", observable_clue="线索", affected_characters=("沈砚",)
    ))
    reg.novel_ledger_store.upsert(source)

    handler = routes.handlers[
        ("POST", "/awp/api/v1/novels/{project_id}/characters/{character_id}/state-promotions")
    ]
    response = asyncio.run(
        handler(
            _Request(
                match_info={"project_id": pid, "character_id": char.character_id},
                body={"source_item_id": source.item_id, "patch": "not-an-object"},
            )
        )
    )

    assert response.status == 400
    assert "object" in _data(response)["error"].lower()
