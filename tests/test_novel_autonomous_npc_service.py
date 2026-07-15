import json

from awp_rp_runtime_v3.contracts.novel_character import NovelCharacter
from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan, ContentSummary
from awp_rp_runtime_v3.contracts.novel_ledger import LedgerItem
from awp_rp_runtime_v3.contracts.novel_npc_agenda import NpcAgenda, VisibleConsequence
from awp_rp_runtime_v3.contracts.novel_profile import default_autonomous_profile
from awp_rp_runtime_v3.runtime.novel_npc_agenda_service import NpcAgendaService
from awp_rp_runtime_v3.runtime.novel_profile_compiler import NovelProfileCompiler


def test_candidate_filter_is_related_and_bounded():
    plan = ChapterPlan(title="沈砚追查遗物", content_summary=ContentSummary(cause="陆遥留下线索"))
    characters = [NovelCharacter(name=f"路人{i}", first_appearance=1) for i in range(55)]
    characters += [
        NovelCharacter(name="沈砚", core_motivation="夺回遗物", first_appearance=1),
        NovelCharacter(name="陆遥", core_motivation="隐藏线索", first_appearance=1),
    ]
    selected = NpcAgendaService().eligible_characters(characters, plan, 1)
    assert [c.name for c in selected] == ["沈砚", "陆遥"]


def test_expired_agenda_is_marked_stale_without_returning_active():
    agenda = NpcAgenda(
        agenda_id="a1", thread_key="沈砚:遗物", npc="沈砚", private_goal="夺回遗物",
        known_fact_ids=("fact-1",), resources=(), cost="无", next_action="跟踪",
        trigger="线索", risk="暴露", visible_consequence=VisibleConsequence(
            agenda_id="a1", beat_id="b1", observable_event="有人跟踪", observable_clue="脚印", affected_characters=("沈砚",)
        ), deadline="2",
    )
    active, updates = NpcAgendaService().active([
        LedgerItem(section="npc_agenda", status="active", content=agenda.model_dump_json())
    ], 3)
    assert active == ()
    assert updates[0].status == "stale"


def test_writer_profile_context_excludes_world_history_and_scene():
    context = NovelProfileCompiler().compile_for(
        "writer", default_autonomous_profile(),
        world_rules=["秘密规则"], history="秘密历史", scene="秘密场景", character_context={},
    )
    assert "world_rules" not in context and "history" not in context and "scene" not in context


def test_compatibility_profile_contains_no_fixed_story_material():
    serialized = default_autonomous_profile().model_dump_json()
    for text in ("刑侦", "匿名威胁", "警局", "第三章", "雨夜", "废弃仓库"):
        assert text not in serialized


def test_agenda_to_ledger_item_round_trips_stable_agenda_id():
    agenda = NpcAgenda(
        agenda_id="agenda-7", thread_key="沈砚:遗物", npc="沈砚", private_goal="夺回遗物",
        known_fact_ids=("fact-1",), resources=(), cost="无", next_action="跟踪",
        trigger="线索", risk="暴露", visible_consequence=VisibleConsequence(
            agenda_id="agenda-7", beat_id="b1", observable_event="有人跟踪",
            observable_clue="脚印", affected_characters=("沈砚",),
        ), deadline="5",
    )
    plan = ChapterPlan(project_id="p1", chapter_index=4)

    item = NpcAgendaService().to_ledger_item(agenda, plan)

    restored = NpcAgenda.model_validate(json.loads(item.content))
    assert item.section == "npc_agenda"
    assert item.status == "active"
    assert restored.agenda_id == "agenda-7"
