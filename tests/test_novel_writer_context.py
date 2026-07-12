from __future__ import annotations

from pathlib import Path

from awp_rp_runtime_v3.contracts.novel_chapter import (
    BeatDetail,
    ChapterPlan,
    CharacterAppearance,
    ContentSummary,
    EndingDesign,
    PlotArrangement,
)
from awp_rp_runtime_v3.contracts.novel_director_guidance import DirectorGuidance
from awp_rp_runtime_v3.contracts.novel_ledger import LedgerItem
from awp_rp_runtime_v3.runtime.novel_writer_adapter import NovelWriterAdapter
from awp_rp_runtime_v3.runtime.novel_writer_adapter import (
    _STYLE_BENCHMARK_CACHE,
    _get_style_benchmark,
)
from awp_rp_runtime_v3.runtime.novel_writer_context import NovelWriterContextCompiler
from awp_rp_runtime_v3.runtime.novel_write_packet_builder import NovelWritePacketBuilder
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.contracts.novel_character import NovelCharacter
from awp_rp_runtime_v3.scripts.novel_cli import _load_plan_guidance, _load_writer_guidance


def _plan() -> ChapterPlan:
    return ChapterPlan(
        chapter_id="ch-demo-1",
        project_id="demo",
        chapter_index=1,
        title="扣子错位的新学期",
        target_chars=2400,
        chapter_position="开幕章",
        target_emotion="轻松中建立信任",
        opening_hook="陈默扣错扣子闯进教室。",
        main_payoff="沈溪发现陈默会悄悄替别人解决麻烦。",
        content_summary=ContentSummary(
            cause="陈默迟到并扣错扣子。",
            development="他用玩笑化解全班的注意。",
            turning_point="班主任让陈默协助沈溪分发教材。",
            climax="陈默用自己的好书换走破损教材。",
            ending="沈溪在陈默名字旁留下一个问号。",
        ),
        plot_arrangement=PlotArrangement(
            main_line="陈默进入新班级。",
            emotion_line="沈溪从恼怒转为重新观察。",
            logic_line="迟到→合作→发现可靠。",
        ),
        character_appearance=CharacterAppearance(
            appearance_order=("陈默", "沈溪", "王磊"),
            relationship_changes=("沈溪不再只把陈默当麻烦人物。",),
            information_gap="陈默不知道沈溪已经改观。",
        ),
        scene_beats=(
            BeatDetail(beat_id="b1", description="陈默迟到，用玩笑化解尴尬。"),
            BeatDetail(beat_id="b2", description="两人被安排一起分发教材。"),
            BeatDetail(beat_id="b3", description="陈默换走破损教材，沈溪重新观察他。"),
        ),
        ending_design=EndingDesign(
            closing_state="沈溪对陈默产生新的判断。",
            next_chapter_push="教材数量出现问题。",
            hook_type="关系暗示",
            hook_detail="名字旁的问号。",
        ),
    )


def _characters() -> dict[str, dict[str, str]]:
    return {
        "陈默": {"personality": "嘴快但可靠", "voice_style": "自然吐槽"},
        "沈溪": {"personality": "严谨克制", "voice_style": "条理清楚"},
        "王磊": {"personality": "爱接梗", "voice_style": "大嗓门"},
        "赵小麦": {"personality": "行动直接", "voice_style": "短句"},
    }


def _ledger() -> list[LedgerItem]:
    return [
        LedgerItem(section="world_rules", entity="world_rules", content="现实校园，不存在超能力。"),
        LedgerItem(section="world_rules", entity="outline", content="全书四十一章的大纲不应交给 Writer。"),
        LedgerItem(section="relationship", entity="沈溪", content="沈溪目前只把陈默当普通同学。"),
        LedgerItem(section="character_state", entity="赵小麦", content="赵小麦正在操场训练。"),
        LedgerItem(section="character_state", entity="苏念", content="苏念将在第四十章登场。"),
    ]


def test_compiler_filters_cast_ledger_world_and_history() -> None:
    compiler = NovelWriterContextCompiler()

    packet = compiler.compile(
        chapter_plan=_plan(),
        ledger_items=_ledger(),
        prev_chapter_ending="上一章最后一段",
        global_summaries="\n".join(f"- 第{i}章摘要" for i in range(1, 8)),
        character_states=_characters(),
        director_guidance=DirectorGuidance(guidance_id="skip"),
    )

    assert packet.allowed_cast == ("陈默", "沈溪", "王磊")
    assert set(packet.character_states) == {"陈默", "沈溪", "王磊"}
    assert packet.world_constraints == ["现实校园，不存在超能力。"]
    assert [item.entity for item in packet.relevant_ledger_items] == ["沈溪"]
    assert "第5章摘要" in packet.history_context
    assert "第1章摘要" not in packet.history_context


def test_writer_prompt_contains_medium_granularity_contract() -> None:
    packet = NovelWriterContextCompiler().compile(
        chapter_plan=_plan(),
        ledger_items=_ledger(),
        prev_chapter_ending="上一章最后一段",
        global_summaries="- 第1章摘要",
        character_states=_characters(),
        director_guidance=DirectorGuidance(guidance_id="skip"),
    )

    _system, prompt = NovelWriterAdapter(None, writer_prompt_name="writer_romcom")._build_prompt(packet)

    assert "允许出场角色: 陈默、沈溪、王磊" in prompt
    assert "陈默迟到，用玩笑化解尴尬" in prompt
    assert "两人被安排一起分发教材" in prompt
    assert "陈默换走破损教材" in prompt
    assert "班主任让陈默协助沈溪分发教材" in prompt
    assert "陈默用自己的好书换走破损教材" in prompt
    assert "名字旁的问号" in prompt
    assert "现实校园，不存在超能力" in prompt
    assert "赵小麦" not in prompt


def test_writer_guidance_does_not_duplicate_story_bible(tmp_path: Path) -> None:
    (tmp_path / "story_bible.md").write_text("全书故事圣经", encoding="utf-8")
    guidance_dir = tmp_path / "guidance"
    guidance_dir.mkdir()
    (guidance_dir / "chapter_01.md").write_text("本章只写教室", encoding="utf-8")

    assert "全书故事圣经" in _load_plan_guidance(tmp_path, 1)
    writer_guidance = _load_writer_guidance(tmp_path, 1)
    assert "全书故事圣经" not in writer_guidance
    assert writer_guidance == "本章只写教室"


def test_existing_packet_builder_uses_compiled_context() -> None:
    packet = NovelWritePacketBuilder(None).build(
        chapter_plan=_plan(),
        ledger_items=_ledger(),
        prev_chapter_ending="上一章最后一段",
        global_summaries="- 第1章摘要",
        character_states=_characters(),
        director_guidance=DirectorGuidance(guidance_id="skip"),
    )

    assert packet.allowed_cast == ("陈默", "沈溪", "王磊")
    assert set(packet.character_states) == {"陈默", "沈溪", "王磊"}
    assert "必须兑现的核心行动" in packet.chapter_contract


def test_unscheduled_first_appearance_zero_is_not_available() -> None:
    characters = [
        NovelCharacter(name="陈默", first_appearance=1),
        NovelCharacter(name="沈溪", first_appearance=1),
        NovelCharacter(name="姜晚", first_appearance=0),
        NovelCharacter(name="赵小麦", first_appearance=2),
    ]

    selected = NovelEngine._characters_available_for_chapter(characters, 1)

    assert [character.name for character in selected] == ["陈默", "沈溪"]


def test_style_benchmark_resolves_normalized_project_directory() -> None:
    _STYLE_BENCHMARK_CACHE.clear()

    benchmark = _get_style_benchmark(project_id="daily-high-school")

    assert "扣子" in benchmark
    assert "蒸汽魔法项目需转换为西幻背景" not in benchmark
