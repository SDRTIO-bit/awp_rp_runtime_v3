from __future__ import annotations

from awp_rp_runtime_v3.contracts.novel_chapter import BeatDetail, ChapterPlan
from awp_rp_runtime_v3.contracts.novel_write_packet import NovelWritePacket
from awp_rp_runtime_v3.runtime.novel_writer_adapter import NovelWriterAdapter


def _packet(author_led: bool) -> NovelWritePacket:
    beat = BeatDetail(
        beat_id="s1",
        description="两人不说话，在站台分别",
        budget_chars=500,
    )
    return NovelWritePacket(
        project_id="p1",
        chapter_id="ch1",
        chapter_plan=ChapterPlan(
            chapter_id="ch1",
            project_id="p1",
            chapter_index=1,
            target_chars=500,
            scene_beats=(beat,),
        ),
        current_scene_beat=beat,
        chapter_contract=(
            "[AUTHOR-APPROVED]\n本章以无言分别收束"
            if author_led
            else "普通章节契约"
        ),
    )


def test_author_mode_does_not_force_hook_dialogue_or_ratio():
    system, prompt = NovelWriterAdapter(None)._build_beat_prompt(_packet(True))
    combined = system + "\n" + prompt

    assert "结尾必须留悬念" not in combined
    assert "必须有对话" not in combined
    assert "60%以上" not in combined
    assert "本章以无言分别收束" in combined


def test_legacy_mode_preserves_existing_prompt_behavior():
    _system, prompt = NovelWriterAdapter(None)._build_beat_prompt(_packet(False))

    assert "只输出本 beat 的正文" in prompt
