"""Fake end-to-end tests for autonomous NPC continuity across chapters."""

from __future__ import annotations

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
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.runtime.novel_writer_adapter import NovelWriterAdapter


def _selected_action() -> SelectedNpcAction:
    return SelectedNpcAction(
        agenda_id="agenda-1",
        character_name="配角甲",
        reasoning="test",
        visible_consequence=VisibleConsequence(
            agenda_id="agenda-1",
            beat_id="b1",
            observable_event="配角甲在暗处观察主角",
            observable_clue="墙角有半片衣角",
            affected_characters=("主角",),
        ),
    )


def _guidance_for_chapter_1() -> DirectorGuidance:
    return DirectorGuidance(
        guidance_id="g1",
        selected_npc_actions=(_selected_action(),),
    )


def _follow_up_action(prev_event: str) -> SelectedNpcAction:
    return SelectedNpcAction(
        agenda_id="agenda-2",
        character_name="配角甲",
        reasoning="continue observing from previous chapter",
        visible_consequence=VisibleConsequence(
            agenda_id="agenda-2",
            beat_id="b2",
            observable_event=f"在上一章“{prev_event}”之后，配角甲再次出现在主角必经之路上",
            observable_clue="同样的衣角碎片",
            affected_characters=("主角",),
        ),
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
    reg.novel_chapter_plan_store.save(ChapterPlan(
        chapter_id="ch2", project_id="p1", chapter_index=2, target_chars=100
    ))
    reg.novel_character_store.save(NovelCharacter(
        character_id="c1",
        project_id="p1",
        name="陈默",
        role="主角",
        first_appearance=1,
    ))


def test_two_chapter_npc_action_continuity(
    reg, engine, monkeypatch, fake_novel_role_runtime,
):
    """A selected NPC action from chapter 1 should be available to shape chapter 2."""
    _setup_project(reg)

    # Chapter 1: director selects an action; quality accepts it by default.
    monkeypatch.setattr(engine, "_call_director", lambda *args, **kwargs: _guidance_for_chapter_1())
    engine.write_chapter(project_id="p1", chapter_index=1)

    prev_actions = reg.novel_ledger_store.list_by_project("p1", NpcAction.LEDGER_SECTION)
    assert len(prev_actions) == 1
    prev_event = prev_actions[0].content
    assert "配角甲" in prev_event

    # Chapter 2: director callback reads the previous npc_action from the ledger
    # and produces a follow-up selected action.
    def director_for_ch2(*args, **kwargs):
        actions = reg.novel_ledger_store.list_by_project("p1", NpcAction.LEDGER_SECTION)
        assert len(actions) == 1
        return DirectorGuidance(
            guidance_id="g2",
            selected_npc_actions=(_follow_up_action(actions[0].content),),
        )

    monkeypatch.setattr(engine, "_call_director", director_for_ch2)

    captured: dict = {}
    original_generate_chapter = NovelWriterAdapter.generate_chapter

    def capture_generate_chapter(self, packet, write_guidance=""):
        captured["packet"] = packet
        return original_generate_chapter(self, packet, write_guidance)

    monkeypatch.setattr(NovelWriterAdapter, "generate_chapter", capture_generate_chapter)

    engine.write_chapter(project_id="p1", chapter_index=2)

    packet = captured["packet"]
    assert packet is not None
    assert len(packet.visible_consequences) == 1

    consequence = packet.visible_consequences[0]
    assert "配角甲" in consequence.observable_event
    assert prev_event in consequence.observable_event

    # Both chapters should now have persisted npc_action ledger items.
    all_actions = reg.novel_ledger_store.list_by_project("p1", NpcAction.LEDGER_SECTION)
    assert len(all_actions) == 2
    assert {1, 2} == {item.source_chapter for item in all_actions}
