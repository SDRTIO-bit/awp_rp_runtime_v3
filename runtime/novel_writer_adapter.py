"""NovelWriterAdapter — Chapter Writer LLM adapter for novel mode.

Uses DeepSeekAdapter with thinking=medium for creative writing.
"""

from __future__ import annotations

import re
from typing import Any

from ..contracts.novel_write_packet import NovelWritePacket
from ..contracts.novel_chapter import ChapterPlan, BeatDetail

# Thinking configuration for creative writing
_THINKING_MEDIUM = {"thinking": {"type": "enabled", "reasoning_effort": "medium"}}

# 前文衔接尾段长度：取上一个 beat 正文结尾的字数喂给下一个 beat，
# 让 Writer 知道上文写到哪、从哪里接续，避免每个 beat 重新开场。
# 只取尾部一段而非全文，控制鼓点风格被模仿放大的风险（quality 阶段
# 的 check_drumbeat_density + rewrite_drumbeat_snippets 会兜底改写短句）。
BEAT_TAIL_CHARS = 500

# Writer system prompt — loaded from prompts/writer.md
from .prompt_loader import load_prompt

def _get_writer_prompt(name: str = "writer") -> str:
    return load_prompt(name)

WRITER_SYSTEM_PROMPT = ""  # replaced at call time by _get_writer_prompt()


_STYLE_BENCHMARK_CACHE: dict[str, str] = {}

def _get_style_benchmark(project_root: str = "", project_id: str = "") -> str:
    cache_key = project_id or project_root or "__default__"
    if cache_key in _STYLE_BENCHMARK_CACHE:
        return _STYLE_BENCHMARK_CACHE[cache_key]
    import os
    paths = []
    if project_root:
        paths.append(os.path.join(project_root, "reference_benchmark.txt"))
    if project_id:
        paths.append(os.path.join(os.path.dirname(__file__), "..", "novels", project_id, "reference_benchmark.txt"))
    paths.append(os.path.join(os.path.dirname(__file__), "..", "novels", "steam_magic", "reference_benchmark.txt"))
    for p in paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                text = f.read().strip()
            # Detect project_type from path to adjust the adaptation hint
            is_romcom = "daily_high_school" in p
            adapt_hint = (
                "以下是你的写作风格参考（校园恋爱喜剧）。\n"
                "请严格模仿以下所有特征：\n"
                "- 对话节奏和吐槽时机\n"
                "- 动作承载情绪（绝不写内心说明）\n"
                "- 场景切换的流畅度\n"
                "- 零比喻、零精确数字、零否定定义句\n"
                "把你的输出和下面这段文字放在一起对比——读者不应该能分辨出哪段是AI写的。\n\n"
                if is_romcom else
                "以下是你的写作风格参考（都市背景，蒸汽魔法项目需转换为西幻背景，\n"
                "但要模仿其对话节奏、情绪表达方式、场景切换的流畅度）：\n\n"
            )
            _STYLE_BENCHMARK_CACHE[cache_key] = (
                "=== STYLE BENCHMARK ===\n" + adapt_hint + text
            )
            return _STYLE_BENCHMARK_CACHE[cache_key]
    _STYLE_BENCHMARK_CACHE[cache_key] = ""
    return ""


class NovelWriterAdapter:
    """Chapter Writer LLM adapter for novel mode."""

    def __init__(self, registry, model: str = "deepseek-v4-pro", writer_prompt_name: str = "writer"):
        self._registry = registry
        self._model = model
        self._writer_prompt_name = writer_prompt_name

    def generate_chapter(self, packet: NovelWritePacket, write_guidance: str = "") -> str:
        """Generate full chapter text from a write packet."""
        import sys, traceback
        try:
            system_prompt, user_prompt = self._build_prompt(packet, write_guidance=write_guidance)
            result = self._call_llm(user_prompt, system_prompt)
            return result
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            raise

    def generate_beat(self, packet: NovelWritePacket, write_guidance: str = "") -> str:
        """Generate a single beat's text."""
        system_prompt, user_prompt = self._build_beat_prompt(packet, write_guidance=write_guidance)
        return self._call_llm(user_prompt, system_prompt)

    def generate_chapter_stream(self, packet: NovelWritePacket, on_chunk, write_guidance: str = "") -> str:
        """Generate full chapter text with streaming callback."""
        system_prompt, user_prompt = self._build_prompt(packet, write_guidance=write_guidance)
        return self._call_llm_stream(user_prompt, system_prompt, on_chunk)

    @staticmethod
    def _crosses_next_beat_boundary(text: str, next_description: str) -> bool:
        """Return whether a beat has already written the next beat's opening action."""
        description = re.sub(r"^【[^】]+】", "", next_description or "").strip()
        anchor = re.split(r"[。！？；，]", description, maxsplit=1)[0].strip()
        return len(anchor) >= 6 and anchor in (text or "")

    def _build_prompt(self, packet: NovelWritePacket, write_guidance: str = "") -> tuple[str, str]:
        """Build the full chapter generation prompt. Returns (system_prompt, user_prompt).

        减法结构：benchmark 先行 → 情境 → 计划 → 红线 → 约束 → 开写。
        不做 beat 切分，不给结构指令。靠 benchmark + 红线约束，其余交给 Writer 自由发挥。
        """
        p = packet.chapter_plan
        parts: list[str] = []

        # ═══ 1. STYLE BENCHMARK — 最先，最强的风格参考 ═══
        benchmark = _get_style_benchmark(project_id=packet.project_id)
        if benchmark:
            parts.append(benchmark)

        # ═══ 2. 故事情境 — 故事进展 + 角色现状 ═══
        context_lines: list[str] = []
        if packet.global_summaries:
            context_lines.append(packet.global_summaries)
        if packet.character_states:
            chars_text = "\n".join(
                f"- {name}: {info.get('personality','')}, 位置={info.get('location','')}, 情绪={info.get('emotion','')}"
                for name, info in packet.character_states.items()
            )
            context_lines.append(chars_text)
        if context_lines:
            parts.append("\n=== 故事情境 ===\n" + "\n".join(context_lines))

        # ═══ 3. 本章计划 — 极简：标题 + 情绪 + 剧情一句话 ═══
        plan_parts = [f"标题: {p.title}"]
        if p.target_chars:
            plan_parts.append(f"目标字数: {p.target_chars}字")
        if p.target_emotion:
            plan_parts.append(f"情绪: {p.target_emotion}")
        if p.chapter_position:
            plan_parts.append(f"定位: {p.chapter_position}")
        if p.main_payoff:
            plan_parts.append(f"本章落点: {p.main_payoff}")
        # 剧情一句话（从 content_summary 取核心因果链）
        cs = p.content_summary
        story_line = f"{cs.cause} → {cs.development} → {cs.ending}".strip(" →")
        plan_parts.append(f"剧情: {story_line}")
        parts.append("\n=== 本章计划 ===\n" + "\n".join(plan_parts))

        # ═══ 4. 必须遵守 — 红线 + 输出规则合一 ═══
        rules = [
            "禁止'不是A而是B'否定对比句式",
            "全文比喻不超过3个。日常描写不附加比喻",
            "禁止精确秒数/分钟数/厘米/角度。用'片刻''一会儿'",
            "情绪不拆三层，一句话写完",
            "叙述者不替读者感受",
            "对话+行为占正文60%以上",
            "结尾留悬念/钩子",
            "只输出正文，无标签、无JSON、无元信息",
        ]
        parts.append("\n=== 必须遵守 ===\n" + "\n".join(f"- {r}" for r in rules))

        # ═══ 5. 连续性约束 — 账本 + 伏笔 + 前章结尾 ═══
        constraint_parts: list[str] = []
        if packet.prev_chapter_ending:
            constraint_parts.append(
                f"【上一章结尾】{packet.prev_chapter_ending}"
            )
        if packet.relevant_ledger_items:
            items_text = "\n".join(
                f"- [{i.section}] {i.entity}: {i.content}"
                for i in packet.relevant_ledger_items
            )
            constraint_parts.append(f"【已知事实】\n{items_text}")
        if packet.foreshadowing_items:
            fg_text = "\n".join(
                f"- [{i.get('status','active')}] {i.get('entity','')}: {i.get('content','')}"
                for i in packet.foreshadowing_items[:10]
            )
            constraint_parts.append(f"【伏笔】\n{fg_text}")
        if write_guidance:
            constraint_parts.append(f"【额外要求】{write_guidance}")
        if constraint_parts:
            parts.append("\n=== 连续性约束 ===\n" + "\n".join(constraint_parts))

        parts.append("\n开始写正文。")

        return _get_writer_prompt(self._writer_prompt_name), "\n".join(parts)

    def _build_beat_prompt(self, packet: NovelWritePacket, write_guidance: str = "") -> tuple[str, str]:
        """Build prompt for a single beat. Returns (system_prompt, user_prompt).

        beat 之间靠两条通道衔接：
        1. PREVIOUS BEAT TAIL — 取 accumulated_text 结尾约 BEAT_TAIL_CHARS 字，
           让 Writer 知道上文写到哪、必须从那里接续，不得重新开场。
        2. BEAT DETAIL — 从 director_guidance.beat_details 按 beat_id 匹配当前
           beat 的 BeatGuidance（McKee 细纲），注入 content_outline/complication
           等递进指令。complication（"比上一个 beat 复杂在哪"）天然防止 beat
           重复 beat1 的场景。
        首 beat（accumulated_text 为空）不注入 PREVIOUS BEAT TAIL。
        """
        beat = packet.current_scene_beat
        p = packet.chapter_plan

        # ═══ Tier 1: 稳定前缀 — DeepSeek 前缀缓存最大化命中 ═══
        # 这一层跨 beat、跨章节都几乎不变，放在 prompt 最前端让缓存复用。

        parts = [
            "=== OUTPUT RULES ===\n"
            "- 只输出本 beat 的正文\n"
            "- 不得提前写后续 beat；当前 beat 的目标完成后立即收束\n"
            "- 无标签、无 JSON、无元信息\n"
            "- 对话+行为占正文60%以上，描写不超过40%\n"
            "- 必须有对话。即使 beat 描述没提对话，也要加入：自言自语、回忆别人说过的话、对物件说话、打电话\n"
            "- 对话要有互动感和功能：要推进剧情/展示人设/制造冲突\n"
            "- 描写点到即止：一个物件一句话，不要铺开写三句\n"
            "\n"
            "=== 红线（最高优先） ===\n"
            "- 禁止'不是A而是B'否定对比句式\n"
            "- 本章比喻总数不超过三个。日常描写不附加比喻。'像''如同''仿佛'等词尽量不用\n"
            "- 禁止精确秒数/分钟数。用'片刻''一会儿''过了一阵'\n"
            "- 情绪不拆三层。'不是X。就是Y。像Z一样'这种解读全禁止。一句话写完情绪\n"
            "- 叙述者不替读者感受。不写'她全都知道''他自己都没意识到'这类上帝视角",
        ]

        # Style benchmark (稳定，读文件，缓存命中)
        benchmark = _get_style_benchmark(project_id=packet.project_id)
        if benchmark:
            parts.append(benchmark)

        # Global summaries (缓慢增长，前缀缓存大部分命中)
        if packet.global_summaries:
            parts.append(f"\n=== STORY SO FAR ===\n{packet.global_summaries}")

        # Character states (稳定)
        if packet.character_states:
            parts.append(f"\n=== CHARACTER STATES ===\n{packet.character_states}")

        # Chapter context (章节内稳定)
        parts.append(
            f"\n=== CHAPTER CONTEXT ===\n"
            f"标题: {p.title} | 情绪: {p.target_emotion} | 定位: {p.chapter_position}"
        )

        # Director anchor (章节内稳定)
        if packet.director_guidance.guidance_id:
            dg = packet.director_guidance
            if dg.character_anchor:
                parts.append(f"\n=== DIRECTOR ===\n角色: {dg.character_anchor}")

        # Prev chapter ending (章节内稳定)
        if packet.prev_chapter_ending:
            parts.append(
                f"\n=== PREV CHAPTER ENDING ===\n{packet.prev_chapter_ending}"
            )

        # ═══ Tier 2: 变体内容 — 以下随 beat / call 变化 ═══

        # TARGET (per-beat)
        parts.append(f"\n=== TARGET ===\n字数: {beat.budget_chars} | 密度: {beat.density}")

        # Previous beat tail — beat 间衔接核心通道
        # 取上一个 beat 正文结尾，强制本 beat 从那里接续，不得重新开场。
        tail = (packet.accumulated_text or "").strip()
        if tail:
            tail_snippet = tail[-BEAT_TAIL_CHARS:]
            parts.append(
                f"\n=== PREVIOUS BEAT TAIL ===\n"
                f"（这是上一个 beat 已写出的正文结尾。本 beat 必须从这段结尾处直接接续，"
                f"不得重新开场、不得重写已发生的场景、不得复述已出现的动作或对话。）\n{tail_snippet}"
            )

        # Current beat
        beat_lines = [
            f"描述: {beat.description}",
            f"功能: {beat.function_tag}",
        ]
        # 注入当前 beat 的 Director 细纲（McKee 框架），如果 Director 产出了的话。
        beat_guidance = self._match_beat_guidance(packet, beat.beat_id)
        if beat_guidance:
            detail_lines = []
            if beat_guidance.content_outline:
                detail_lines.append(f"事件: {beat_guidance.content_outline}")
            if beat_guidance.complication:
                detail_lines.append(f"比上一 beat 递进: {beat_guidance.complication}")
            if beat_guidance.emotion_shift:
                detail_lines.append(f"情绪翻转: {beat_guidance.emotion_shift}")
            if beat_guidance.dialogue_keys:
                detail_lines.append(f"对白要点: {'；'.join(beat_guidance.dialogue_keys)}")
            if beat_guidance.hook_execution:
                detail_lines.append(f"钩子落地: {beat_guidance.hook_execution}")
            if detail_lines:
                beat_lines.append("Director 细纲:")
                beat_lines.extend(f"  {ln}" for ln in detail_lines)
        beat_lines.append(
            "注意：以上描述只是骨架。你必须用对话填充血肉。没有对话的beat是失败的。"
        )
        parts.append("\n=== CURRENT BEAT ===\n" + "\n".join(beat_lines))

        # Give the writer an explicit stopping boundary. A positive word budget
        # alone is not enough when adjacent beats describe the same scene.
        for index, candidate in enumerate(p.scene_beats):
            if candidate == beat or candidate.beat_id == beat.beat_id:
                if index + 1 < len(p.scene_beats):
                    next_beat = p.scene_beats[index + 1]
                    parts.append(
                        "\n=== BEAT BOUNDARY ===\n"
                        "下一 beat 的起点如下；不得写入其中的事件，只能在它发生前收束：\n"
                        f"{next_beat.description}"
                    )
                break

        # Continuity ledger (per-beat，过滤粒度不同 → 变体)
        if packet.relevant_ledger_items:
            items_text = "\n".join(
                f"- [{i.section}] {i.entity}: {i.content}"
                for i in packet.relevant_ledger_items
            )
            parts.append(f"\n=== CONTINUITY ===\n{items_text}")

        if write_guidance:
            parts.append(f"\n=== WRITER GUIDANCE ===\n{write_guidance}\n（以上引导是硬性要求，必须执行）")

        return _get_writer_prompt(self._writer_prompt_name), "\n".join(parts)

    def _match_beat_guidance(self, packet: NovelWritePacket, beat_id: str):
        """从 director_guidance.beat_details 按 beat_id 匹配当前 beat 的细纲。

        Director 输出的 BeatGuidance 按 beat_id 对齐 Architect 的 BeatDetail。
        匹配失败（Director 未产出 / id 不一致）时返回 None，prompt 退化为只用骨架。
        """
        beat_details = getattr(packet.director_guidance, "beat_details", None) or ()
        if not beat_details or not beat_id:
            return None
        for bg in beat_details:
            if getattr(bg, "beat_id", "") == beat_id:
                return bg
        return None

    def _format_memory_items(self, items: list[dict[str, Any]]) -> str:
        lines = []
        for item in items[:10]:
            content = item.get("content") or item.get("summary") or ""
            source = item.get("source") or item.get("layer") or "memory"
            importance = item.get("importance")
            if importance is None:
                lines.append(f"- [{source}] {content}")
            else:
                lines.append(f"- [{source} {importance:.2f}] {content}")
        return "\n".join(lines)

    def _call_llm(self, prompt: str, system_prompt: str = "") -> str:
        """Call LLM with thinking=medium. Raises on failure (no placeholder)."""
        from .novel_llm_factory import NovelLLMFactory
        import traceback, sys
        try:
            factory = NovelLLMFactory.get_instance()
            adapter = factory.get_adapter("writer")
            thinking = factory.get_thinking_config("writer")
            model = factory.get_model("writer")
            max_tokens = factory.get_max_tokens("writer")

            text, receipt = adapter.generate_text(
                prompt,
                max_tokens=max_tokens,
                provider_role="novel_writer",
                model=model,
                extra_body=thinking,
                system_prompt=system_prompt or None,
            )
            if text and text.strip():
                return text
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            # Fall through to the failure raise below.
            pass
        # Previously returned a placeholder string, which got persisted as the
        # chapter text and silently counted as a "completed" chapter. Now raise
        # so the caller (NovelEngine retry loop / batch_write except) can handle it.
        raise RuntimeError("Novel writer LLM returned empty output")

    def _call_llm_stream(self, prompt: str, system_prompt: str,
                         on_chunk) -> str:
        """Call LLM with streaming. Raises on failure."""
        from .novel_llm_factory import NovelLLMFactory
        factory = NovelLLMFactory.get_instance()
        adapter = factory.get_adapter("writer")
        thinking = factory.get_thinking_config("writer")
        model = factory.get_model("writer")
        max_tokens = factory.get_max_tokens("writer")

        import traceback
        try:
            text = adapter.generate_text_stream(
                prompt,
                on_chunk=on_chunk,
                max_tokens=max_tokens,
                model=model,
                extra_body=thinking,
                system_prompt=system_prompt or None,
            )
        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"Writer streaming failed: {e}")
        if text and text.strip():
            return text
        raise RuntimeError("Novel writer LLM streaming returned empty output")
