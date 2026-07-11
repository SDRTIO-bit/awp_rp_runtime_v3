"""NovelWriterAdapter — Chapter Writer LLM adapter for novel mode.

Uses DeepSeekAdapter with thinking=medium for creative writing.
"""

from __future__ import annotations

from typing import Any

from ..contracts.novel_write_packet import NovelWritePacket
from ..contracts.novel_chapter import ChapterPlan, BeatDetail

# Thinking configuration for creative writing
_THINKING_MEDIUM = {"thinking": {"type": "enabled", "reasoning_effort": "medium"}}

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
                "以下是你的写作风格参考（校园恋爱喜剧背景，严格模仿其对话节奏、吐槽时机、情绪表达方式和场景切换的流畅度）：\n\n"
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
        system_prompt, user_prompt = self._build_prompt(packet, write_guidance=write_guidance)
        return self._call_llm(user_prompt, system_prompt)

    def generate_beat(self, packet: NovelWritePacket, write_guidance: str = "") -> str:
        """Generate a single beat's text."""
        system_prompt, user_prompt = self._build_beat_prompt(packet, write_guidance=write_guidance)
        return self._call_llm(user_prompt, system_prompt)

    def generate_beat_stream(self, packet: NovelWritePacket, on_chunk, write_guidance: str = "") -> str:
        """Generate a single beat's text with streaming callback."""
        system_prompt, user_prompt = self._build_beat_prompt(packet, write_guidance=write_guidance)
        return self._call_llm_stream(user_prompt, system_prompt, on_chunk)

    def _build_prompt(self, packet: NovelWritePacket, write_guidance: str = "") -> tuple[str, str]:
        """Build the full chapter generation prompt. Returns (system_prompt, user_prompt).

        Cache-optimized order (DeepSeek prefix caching):
        1. OUTPUT RULES (always same → full cache hit)
        2. GLOBAL SUMMARIES (grows 1 line/ch → mostly cached)
        3. CHARACTER STATES (stable)
        4. Continuity / ledger (varies)
        5. Chapter-specific: plan + ending (changes every call)
        """
        p = packet.chapter_plan

        # ---- Tier 1: Stable prefix (cache hits) ----

        parts = [
            "=== OUTPUT RULES ===\n"
            "- 只输出正文，无标签、无 JSON、无元信息\n"
            "- 结尾必须留悬念/钩子\n"
            "- 不复述上一章结尾即可\n"
            "- 对话+行为占正文60%以上，描写不超过40%\n"
            "- 每个场景必须有对话（独处场景用自言自语/回忆/打电话）"
        ]

        # Style benchmark (stable, cache hit)
        benchmark = _get_style_benchmark(project_id=packet.project_id)
        if benchmark:
            parts.append(benchmark)

        # Global summaries: all completed chapters, 1 line each
        if packet.global_summaries:
            parts.append(f"\n=== STORY SO FAR ===\n{packet.global_summaries}")

        # Character states (stable)
        if packet.character_states:
            parts.append(f"\n=== CHARACTER STATES ===\n{packet.character_states}")

        # ---- Tier 2: Varying but compact ----

        # Continuity: ledger items (trimmed)
        if packet.relevant_ledger_items:
            items_text = "\n".join(
                f"- [{i.section}] {i.entity}: {i.content[:200]}"
                for i in packet.relevant_ledger_items[:6]
            )
            parts.append(f"\n=== CONTINUITY ===\n{items_text}")

        # Foreshadowing
        if packet.foreshadowing_items:
            parts.append(
                "\n=== FORESHADOWING ===\n"
                + "\n".join(
                    f"- [{i.get('status','active')}] {i.get('entity','')}: {i.get('content','')}"
                    for i in packet.foreshadowing_items[:5]
                )
            )

        # World constraints (hard rules: setting, era, tone limits)
        if packet.world_constraints:
            parts.append(
                "\n=== WORLD CONSTRAINTS ===\n"
                + "\n".join(f"- {c}" for c in packet.world_constraints)
            )

        # ---- Tier 3: Chapter-specific (changes every call) ----

        # Chapter plan — lightweight: only title + emotion + position + beat outlines
        plan_lines = [f"标题: {p.title} | 情绪: {p.target_emotion} | 定位: {p.chapter_position}"]
        for b in p.scene_beats:
            plan_lines.append(f"  [{b.beat_id}] {b.description} ({b.density}, {b.budget_chars}字)")
        if p.main_payoff:
            plan_lines.append(f"主要回报: {p.main_payoff}")
        parts.append(f"\n=== CHAPTER PLAN ===\n" + "\n".join(plan_lines))

        # Previous chapter ending — hook continuity only
        if packet.prev_chapter_ending:
            parts.append(
                f"\n=== PREV CHAPTER ENDING ===\n"
                f"(上一章结尾，本章从这里接续)\n{packet.prev_chapter_ending}"
            )

        # Director: character + timeline anchor only (not full beat detail)
        if packet.director_guidance.guidance_id:
            dg = packet.director_guidance
            dg_lines = []
            if dg.character_anchor:
                dg_lines.append(f"角色: {dg.character_anchor}")
            if dg.timeline_anchor:
                dg_lines.append(f"时间: {dg.timeline_anchor}")
            if dg_lines:
                parts.append(f"\n=== DIRECTOR ===\n" + "\n".join(dg_lines))

        if packet.writing_intent:
            parts.append(f"\n=== WRITING INTENT ===\n{packet.writing_intent}")

        if write_guidance:
            parts.append(f"\n=== WRITER GUIDANCE ===\n{write_guidance}\n（以上引导是硬性要求，必须执行）")

        return _get_writer_prompt(self._writer_prompt_name), "\n".join(parts)

    def _build_beat_prompt(self, packet: NovelWritePacket, write_guidance: str = "") -> tuple[str, str]:
        """Build prompt for a single beat. Returns (system_prompt, user_prompt).
        No accumulated_text — beats are independent to avoid drumbeat amplification."""
        beat = packet.current_scene_beat
        p = packet.chapter_plan

        # Stable prefix
        parts = [
            "=== OUTPUT RULES ===\n"
            "- 只输出本 beat 的正文\n"
            "- 无标签、无 JSON、无元信息\n"
            "- 对话+行为占正文60%以上，描写不超过40%\n"
            "- 必须有对话。即使 beat 描述没提对话，也要加入：自言自语、回忆别人说过的话、对物件说话、打电话\n"
            "- 对话要有互动感和功能：要推进剧情/展示人设/制造冲突\n"
            "- 描写点到即止：一个物件一句话，不要铺开写三句",
            f"\n=== TARGET ===\n字数: {beat.budget_chars} | 密度: {beat.density}",
        ]

        # Style benchmark (stable, cache hit)
        benchmark = _get_style_benchmark(project_id=packet.project_id)
        if benchmark:
            parts.append(benchmark)

        # Global summaries
        if packet.global_summaries:
            parts.append(f"\n=== STORY SO FAR ===\n{packet.global_summaries}")

        # Character states
        if packet.character_states:
            parts.append(f"\n=== CHARACTER STATES ===\n{packet.character_states}")

        # Current beat
        parts.append(
            f"\n=== CURRENT BEAT ===\n"
            f"描述: {beat.description}\n"
            f"功能: {beat.function_tag}\n"
            f"注意：以上描述只是骨架。你必须用对话填充血肉。没有对话的beat是失败的。"
        )

        # Chapter context (lightweight)
        parts.append(
            f"\n=== CHAPTER CONTEXT ===\n"
            f"标题: {p.title} | 情绪: {p.target_emotion} | 定位: {p.chapter_position}"
        )

        # Director anchor only
        if packet.director_guidance.guidance_id:
            dg = packet.director_guidance
            if dg.character_anchor:
                parts.append(f"\n=== DIRECTOR ===\n角色: {dg.character_anchor}")

        # Prev chapter ending (hook)
        if packet.prev_chapter_ending:
            parts.append(
                f"\n=== PREV CHAPTER ENDING ===\n{packet.prev_chapter_ending}"
            )

        # Continuity ledger
        if packet.relevant_ledger_items:
            items_text = "\n".join(
                f"- [{i.section}] {i.entity}: {i.content[:150]}"
                for i in packet.relevant_ledger_items[:5]
            )
            parts.append(f"\n=== CONTINUITY ===\n{items_text}")

        if write_guidance:
            parts.append(f"\n=== WRITER GUIDANCE ===\n{write_guidance}\n（以上引导是硬性要求，必须执行）")

        return _get_writer_prompt(self._writer_prompt_name), "\n".join(parts)

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
        factory = NovelLLMFactory.get_instance()
        adapter = factory.get_adapter("writer")
        thinking = factory.get_thinking_config("writer")
        model = factory.get_model("writer")
        max_tokens = factory.get_max_tokens("writer")

        try:
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
        except Exception:
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

        text = adapter.generate_text_stream(
            prompt,
            on_chunk=on_chunk,
            max_tokens=max_tokens,
            model=model,
            extra_body=thinking,
            system_prompt=system_prompt or None,
        )
        if text and text.strip():
            return text
        raise RuntimeError("Novel writer LLM streaming returned empty output")
