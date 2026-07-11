"""Tests for beat 间衔接修复：前文尾段注入 + BeatGuidance 注入 + scene_repeat 检测。

注意：本仓库既有的 tests/test_novel_agents.py 使用 awp_rp_runtime_v2 包名，
但该包不存在（仓库实际为 v3）。这里直接用 v3 import（与 novel_cli.py 一致），
避免依赖断裂的 v2 测试基础设施。
"""

import sys
from pathlib import Path

# 复刻 novel_cli.py 的 path 设置：把仓库父目录加进 path，
# 使 awp_rp_runtime_v3 作为包可被 import。
_REPO_PARENT = str(Path(__file__).resolve().parent.parent.parent)
if _REPO_PARENT not in sys.path:
    sys.path.insert(0, _REPO_PARENT)

import pytest
from awp_rp_runtime_v3.runtime.novel_writer_adapter import NovelWriterAdapter
from awp_rp_runtime_v3.runtime.novel_style_cleaner import NovelStyleCleaner
from awp_rp_runtime_v3.runtime.novel_quality_pipeline import NovelQualityPipeline
from awp_rp_runtime_v3.contracts.novel_write_packet import NovelWritePacket
from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan, BeatDetail
from awp_rp_runtime_v3.contracts.novel_director_guidance import (
    DirectorGuidance, BeatGuidance,
)


@pytest.fixture
def writer():
    # _build_beat_prompt 不调 LLM，registry 可为 None
    return NovelWriterAdapter(registry=None, writer_prompt_name="writer")


@pytest.fixture
def cleaner():
    return NovelStyleCleaner(registry=None)


@pytest.fixture
def pipeline():
    return NovelQualityPipeline(registry=None)


def _make_plan():
    return ChapterPlan(
        chapter_id="ch1", project_id="p1",
        title="扣子错位的新学期", target_emotion="轻松搞笑",
        chapter_position="opening", target_chars=6000,
        scene_beats=(
            BeatDetail(beat_id="b1", description="迟到闯进教室",
                       function_tag="opening", density="normal", budget_chars=2000),
            BeatDetail(beat_id="b2", description="搬教材发现看标签",
                       function_tag="progression", density="normal", budget_chars=2000),
            BeatDetail(beat_id="b3", description="发书抚平折痕",
                       function_tag="payoff", density="normal", budget_chars=2000),
        ),
    )


# ── 第 1 层：PREVIOUS BEAT TAIL 注入 ────────────────────────────────

class TestPreviousBeatTail:
    def test_non_first_beat_includes_tail(self, writer):
        """非首 beat 的 prompt 必须含 PREVIOUS BEAT TAIL 段与强制接续指令。"""
        beat = BeatDetail(beat_id="b2", description="搬教材",
                          function_tag="progression", density="normal", budget_chars=2000)
        packet = NovelWritePacket(
            packet_id="pkt1", project_id="p1", chapter_id="ch1",
            chapter_plan=_make_plan(),
            current_scene_beat=beat,
            accumulated_text="陈默终于把扣子扣对了。王磊还在旁边偷笑。沈溪走下讲台。" * 20,
        )
        _, user_prompt = writer._build_beat_prompt(packet)
        assert "PREVIOUS BEAT TAIL" in user_prompt
        assert "不得重新开场" in user_prompt
        # 尾段取的是 accumulated_text 结尾，应能在 prompt 里找到那段文本的尾部
        assert "沈溪走下讲台" in user_prompt

    def test_first_beat_has_no_tail(self, writer):
        """首 beat（accumulated_text 为空）不应注入 PREVIOUS BEAT TAIL。"""
        beat = BeatDetail(beat_id="b1", description="迟到闯进教室",
                          function_tag="opening", density="normal", budget_chars=2000)
        packet = NovelWritePacket(
            packet_id="pkt0", project_id="p1", chapter_id="ch1",
            chapter_plan=_make_plan(),
            current_scene_beat=beat,
            accumulated_text="",
        )
        _, user_prompt = writer._build_beat_prompt(packet)
        assert "PREVIOUS BEAT TAIL" not in user_prompt

    def test_tail_truncated_to_budget(self, writer):
        """前文尾段只取最后 BEAT_TAIL_CHARS 字，不喂全文。"""
        from awp_rp_runtime_v3.runtime.novel_writer_adapter import BEAT_TAIL_CHARS
        beat = BeatDetail(beat_id="b2", description="搬教材",
                          function_tag="progression", density="normal", budget_chars=2000)
        # 构造远超 BEAT_TAIL_CHARS 的前文，头部放一个唯一标记
        head_marker = "这是应当被截掉的前文头部标记XYZ"
        tail_marker = "这是必须保留的前文尾部标记ABC"
        long_text = head_marker + "中间填充内容。" * 200 + tail_marker
        packet = NovelWritePacket(
            packet_id="pkt1", project_id="p1", chapter_id="ch1",
            chapter_plan=_make_plan(),
            current_scene_beat=beat,
            accumulated_text=long_text,
        )
        _, user_prompt = writer._build_beat_prompt(packet)
        assert tail_marker in user_prompt
        assert head_marker not in user_prompt
        # 注入的尾段本身（段头指令之后到下一个 === 段之前）不应远超 BEAT_TAIL_CHARS
        idx = user_prompt.find("PREVIOUS BEAT TAIL")
        next_section = user_prompt.find("=== CURRENT BEAT ===", idx)
        tail_section = user_prompt[idx:next_section]
        # 尾段 = 段头指令(~90字) + 尾部文本(<=BEAT_TAIL_CHARS) + 换行
        assert len(tail_section) < BEAT_TAIL_CHARS + 200


# ── 第 2 层：BeatGuidance 注入 ─────────────────────────────────────

class TestBeatGuidanceInjection:
    def test_matched_beat_guidance_injected(self, writer):
        """beat_id 匹配的 BeatGuidance 字段应进 CURRENT BEAT 段。"""
        beat = BeatDetail(beat_id="b2", description="搬教材",
                          function_tag="progression", density="normal", budget_chars=2000)
        bg = BeatGuidance(
            beat_id="b2",
            content_outline="陈默和沈溪去教务处搬教材",
            complication="沈溪发现陈默看包装标签一眼数对",
            emotion_shift="轻视→意外",
            dialogue_keys=("你数什么数", "你看这个标签"),
            hook_execution="沈溪笔下留情只记一次提醒",
        )
        guidance = DirectorGuidance(guidance_id="g1", character_anchor="陈默/沈溪",
                                     beat_details=(bg,))
        packet = NovelWritePacket(
            packet_id="pkt1", project_id="p1", chapter_id="ch1",
            chapter_plan=_make_plan(),
            director_guidance=guidance,
            current_scene_beat=beat,
            accumulated_text="",
        )
        _, user_prompt = writer._build_beat_prompt(packet)
        assert "陈默和沈溪去教务处搬教材" in user_prompt
        assert "比上一 beat 递进" in user_prompt
        assert "沈溪发现陈默看包装标签一眼数对" in user_prompt
        assert "你数什么数" in user_prompt
        assert "情绪翻转" in user_prompt

    def test_no_beat_guidance_falls_back_gracefully(self, writer):
        """Director 未产出 beat_details 时，prompt 退化为只用骨架，不报错。"""
        beat = BeatDetail(beat_id="b1", description="迟到闯进教室",
                          function_tag="opening", density="normal", budget_chars=2000)
        guidance = DirectorGuidance(guidance_id="g1")  # 无 beat_details
        packet = NovelWritePacket(
            packet_id="pkt0", project_id="p1", chapter_id="ch1",
            chapter_plan=_make_plan(),
            director_guidance=guidance,
            current_scene_beat=beat,
            accumulated_text="",
        )
        _, user_prompt = writer._build_beat_prompt(packet)
        # 仍含骨架描述
        assert "迟到闯进教室" in user_prompt
        # 不含细纲段
        assert "Director 细纲" not in user_prompt

    def test_beat_id_mismatch_skips_guidance(self, writer):
        """beat_id 不匹配时不注入错的细纲。"""
        beat = BeatDetail(beat_id="b2", description="搬教材",
                          function_tag="progression", density="normal", budget_chars=2000)
        bg = BeatGuidance(beat_id="b9", content_outline="这是别的 beat 的细纲")
        guidance = DirectorGuidance(guidance_id="g1", beat_details=(bg,))
        packet = NovelWritePacket(
            packet_id="pkt1", project_id="p1", chapter_id="ch1",
            chapter_plan=_make_plan(),
            director_guidance=guidance,
            current_scene_beat=beat,
            accumulated_text="",
        )
        _, user_prompt = writer._build_beat_prompt(packet)
        assert "这是别的 beat 的细纲" not in user_prompt


# ── 第 3 层：check_scene_repeat 检测 ───────────────────────────────

class TestSceneRepeatDetection:
    def test_repeated_opening_detected(self, cleaner):
        """beat2 开场与 beat1 高度相似时应报 blocking。"""
        beat_a = ("陈默迟到、衬衫扣错，在沈溪维持秩序时闯进教室。"
                  "他靠玩笑逗笑全班，也被她列为重点管教对象。班主任让他协助分发教材。" * 15)
        beat_b = ("陈默迟到、衬衫扣错，在沈溪维持秩序时闯进教室。"
                  "他靠玩笑逗笑全班，也被她列为重点管教对象。班主任让他协助分发教材。沈溪皱眉看他。" * 15)
        beat_c = ("教务处走廊光线暗，陈默跟在沈溪身后搬教材。"
                  "包装标签的门道让沈溪第一次重新看他。" * 15)
        text = beat_a + beat_b + beat_c
        plan = _make_plan()
        issues = cleaner.check_scene_repeat(text, plan)
        assert len(issues) > 0
        assert all(i["severity"] == "blocking" for i in issues)
        assert all(i["type"] == "scene_repeat" for i in issues)

    def test_clean_progression_not_flagged(self, cleaner):
        """三段开场各不相同时不应误报。"""
        clean_a = "开学第一天，沈溪站在讲台上宣布班规，暗红发绳在晨光里反光。" * 15
        clean_b = "教务处堆着几十捆教材，牛皮纸包得方方正正。陈默看一眼标签就报出数量。" * 15
        clean_c = "回到教室发书，陈默发现一本练习册压皱了，反复推平才递给女生。" * 15
        text = clean_a + clean_b + clean_c
        plan = _make_plan()
        issues = cleaner.check_scene_repeat(text, plan)
        assert issues == []

    def test_missing_plan_safe(self, cleaner):
        """plan 缺失时不报错。"""
        text = "内容" * 500
        issues = cleaner.check_scene_repeat(text, None)
        assert issues == []

    def test_short_text_safe(self, cleaner):
        """正文过短时跳过检测。"""
        plan = _make_plan()
        issues = cleaner.check_scene_repeat("太短了", plan)
        assert issues == []

    def test_pipeline_surfaces_scene_repeat_as_blocking(self, pipeline):
        """quality pipeline 应把 scene_repeat 转成 ERROR blocking。"""
        beat_a = ("陈默迟到、衬衫扣错，在沈溪维持秩序时闯进教室。"
                  "他靠玩笑逗笑全班，也被她列为重点管教对象。班主任让他协助分发教材。" * 15)
        beat_b = ("陈默迟到、衬衫扣错，在沈溪维持秩序时闯进教室。"
                  "他靠玩笑逗笑全班，也被她列为重点管教对象。班主任让他协助分发教材。沈溪皱眉看他。" * 15)
        beat_c = ("教务处走廊光线暗，陈默跟在沈溪身后搬教材。"
                  "包装标签的门道让沈溪第一次重新看他。" * 15)
        text = beat_a + beat_b + beat_c
        plan = _make_plan()
        decision = pipeline.check_chapter(text, plan)
        assert decision.verdict.value == "revise"
        assert any("重新开场" in r for r in decision.blocking_reasons)
