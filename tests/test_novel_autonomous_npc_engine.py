"""Tests for autonomous NPC integration in NovelEngine."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from awp_rp_runtime_v3.contracts.novel_character import NovelCharacter
from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan
from awp_rp_runtime_v3.contracts.novel_director_guidance import DirectorGuidance
from awp_rp_runtime_v3.contracts.novel_npc_agenda import (
    NpcAction,
    SelectedNpcAction,
    VisibleConsequence,
)
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.contracts.quality_decision import QualityDecision, QualityVerdict
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.novel_npc_agenda_adapter import NovelNpcAgendaAdapter


def _rejected_decision() -> QualityDecision:
    return QualityDecision(
        trace_id="qd-rejected",
        source_turn_id="ch-1",
        verdict=QualityVerdict.REVISE,
        blocking_reasons=["forced rejection"],
        warnings=[],
        checks=[],
    )


def _accepted_decision() -> QualityDecision:
    return QualityDecision(
        trace_id="qd-accepted",
        source_turn_id="ch-1",
        verdict=QualityVerdict.ACCEPTED,
        blocking_reasons=[],
        warnings=[],
        checks=[],
    )


def _selected_action() -> SelectedNpcAction:
    return SelectedNpcAction(
        agenda_id="agenda-1",
        character_name="配角甲",
        reasoning="test",
        visible_consequence=VisibleConsequence(
            agenda_id="agenda-1",
            beat_id="b1",
            observable_event=" observable event",
            observable_clue=" observable clue",
            affected_characters=("主角",),
        ),
    )


def _guidance_with_npc() -> DirectorGuidance:
    return DirectorGuidance(
        guidance_id="g1",
        selected_npc_actions=(_selected_action(),),
    )


def _proposed_agenda():
    from awp_rp_runtime_v3.contracts.novel_npc_agenda import NpcAgenda

    return NpcAgenda(
        agenda_id="agenda-1",
        thread_key="配角甲:观察",
        npc="配角甲",
        private_goal="私密目标",
        known_fact_ids=("fact-1",),
        resources=(),
        cost="无",
        next_action="观察主角",
        trigger="主角出现",
        risk="暴露",
        visible_consequence=_selected_action().visible_consequence,
        deadline="3",
    )


@pytest.fixture
def reg(tmp_path):
    from awp_rp_runtime_v3.storage.sqlite.database import Database
    from awp_rp_runtime_v3.runtime.session_runtime_registry import SessionRuntimeStoreRegistry

    db = Database(str(tmp_path / "test.db"))
    db.initialize()
    return SessionRuntimeStoreRegistry(db)


@pytest.fixture
def engine(reg):
    return NovelEngine(reg)


def _setup_project(reg):
    reg.novel_project_store.create(NovelProject(project_id="p1", title="测试"))
    reg.novel_chapter_plan_store.save(ChapterPlan(
        chapter_id="ch1", project_id="p1", chapter_index=1, target_chars=100
    ))
    reg.novel_character_store.save(NovelCharacter(
        character_id="c1",
        project_id="p1",
        name="陈默",
        role="主角",
        first_appearance=1,
    ))


def test_rejection_has_zero_autonomy_side_effects(
    reg, engine, monkeypatch, fake_novel_role_runtime,
):
    _setup_project(reg)
    monkeypatch.setattr(engine, "_call_director", lambda *args, **kwargs: _guidance_with_npc())

    calls = []
    original_update_ledger = engine._update_ledger

    def recording_update_ledger(*args, **kwargs):
        calls.append((args, kwargs))
        return original_update_ledger(*args, **kwargs)

    monkeypatch.setattr(engine, "_update_ledger", recording_update_ledger)
    monkeypatch.setattr(engine._quality_pipeline, "run_chapter", lambda *args, **kwargs: (_rejected_decision(), args[0]))

    engine.write_chapter(project_id="p1", chapter_index=1)

    # Rejected chapters must not propagate selected NPC actions into the ledger.
    assert all(
        kwargs.get("selected_npc_actions") == ()
        for _, kwargs in calls
    )
    assert reg.novel_ledger_store.list_by_project("p1", NpcAction.LEDGER_SECTION) == []
    assert reg.novel_ledger_store.list_by_project("p1", "npc_agenda") == []


def test_accepted_chapter_persists_npc_action(
    reg, engine, monkeypatch, fake_novel_role_runtime,
):
    _setup_project(reg)
    monkeypatch.setattr(engine, "_call_director", lambda *args, **kwargs: _guidance_with_npc())

    engine.write_chapter(project_id="p1", chapter_index=1)

    actions = reg.novel_ledger_store.list_by_project("p1", NpcAction.LEDGER_SECTION)
    assert len(actions) == 1
    assert actions[0].entity == _selected_action().character_name
    assert "observable event" in actions[0].content


def test_accepted_chapter_persists_proposed_npc_agenda(
    reg, engine, monkeypatch, fake_novel_role_runtime,
):
    _setup_project(reg)
    monkeypatch.setattr(
        NovelNpcAgendaAdapter,
        "propose",
        lambda *args, **kwargs: (_proposed_agenda(),),
    )
    monkeypatch.setattr(
        engine._agenda_service,
        "eligible_characters",
        lambda characters, *_args: tuple(characters),
    )
    monkeypatch.setattr(engine, "_call_director", lambda *args, **kwargs: _guidance_with_npc())

    engine.write_chapter(project_id="p1", chapter_index=1)

    agendas = reg.novel_ledger_store.list_by_project("p1", "npc_agenda")
    assert len(agendas) == 1
    assert agendas[0].status == "active"


def test_rejected_chapter_discards_staged_npc_agenda(
    reg, engine, monkeypatch, fake_novel_role_runtime,
):
    _setup_project(reg)
    monkeypatch.setattr(
        NovelNpcAgendaAdapter,
        "propose",
        lambda *args, **kwargs: (_proposed_agenda(),),
    )
    monkeypatch.setattr(
        engine._agenda_service,
        "eligible_characters",
        lambda characters, *_args: tuple(characters),
    )
    monkeypatch.setattr(engine, "_call_director", lambda *args, **kwargs: _guidance_with_npc())
    monkeypatch.setattr(
        engine._quality_pipeline,
        "run_chapter",
        lambda *args, **kwargs: (_rejected_decision(), args[0]),
    )

    engine.write_chapter(project_id="p1", chapter_index=1)

    assert reg.novel_ledger_store.list_by_project("p1", "npc_agenda") == []
    assert reg.novel_ledger_store.list_by_project("p1", NpcAction.LEDGER_SECTION) == []


def test_streaming_accepted_chapter_persists_npc_action(
    reg, engine, monkeypatch, fake_novel_role_runtime,
):
    _setup_project(reg)
    monkeypatch.setattr(engine, "_call_director", lambda *args, **kwargs: _guidance_with_npc())

    engine.write_chapter_stream(project_id="p1", chapter_index=1)

    actions = reg.novel_ledger_store.list_by_project("p1", NpcAction.LEDGER_SECTION)
    assert len(actions) == 1


def test_writer_packet_exposes_visible_consequence_not_private_plan(
    reg, engine, monkeypatch, fake_novel_role_runtime,
):
    _setup_project(reg)
    monkeypatch.setattr(engine, "_call_director", lambda *args, **kwargs: _guidance_with_npc())

    captured: dict[str, Any] = {}

    original_call_writer = engine._call_writer

    def capture_call_writer(packet, **kwargs):
        captured["packet"] = packet
        return original_call_writer(packet, **kwargs)

    monkeypatch.setattr(engine, "_call_writer", capture_call_writer)

    engine.write_chapter(project_id="p1", chapter_index=1)

    packet = captured["packet"]
    assert packet is not None
    assert len(packet.visible_consequences) == 1
    consequence = packet.visible_consequences[0]
    assert consequence.observable_event == " observable event"

    packet_json = json.dumps(packet.to_dict(), ensure_ascii=False)
    assert "private_goal" not in packet_json
    assert "observable clue" in packet_json
