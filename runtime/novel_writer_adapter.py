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

def _get_writer_prompt() -> str:
    return load_prompt("writer")

WRITER_SYSTEM_PROMPT = ""  # replaced at call time by _get_writer_prompt()


class NovelWriterAdapter:
    """Chapter Writer LLM adapter for novel mode."""

    def __init__(self, registry, model: str = "deepseek-v4-pro"):
        self._registry = registry
        self._model = model

    def generate_chapter(self, packet: NovelWritePacket) -> str:
        """Generate full chapter text from a write packet."""
        system_prompt, user_prompt = self._build_prompt(packet)
        return self._call_llm(user_prompt, system_prompt)

    def generate_beat(self, packet: NovelWritePacket) -> str:
        """Generate a single beat's text."""
        system_prompt, user_prompt = self._build_beat_prompt(packet)
        return self._call_llm(user_prompt, system_prompt)

    def _build_prompt(self, packet: NovelWritePacket) -> tuple[str, str]:
        """Build the full chapter generation prompt. Returns (system_prompt, user_prompt).

        Prompt structure optimized for DeepSeek prefix caching:
        - Stable rules first (cacheable prefix)
        - Varying context after
        """
        # Stable prefix — same every call, maximizes cache hits
        parts = [
            "=== OUTPUT RULES ===\n"
            "- 只输出正文，无标签、无 JSON、无元信息\n"
            "- 结尾必须留悬念/钩子\n"
            "- 不复述上一章结尾\n"
            "- 对话+行为占正文60%以上，描写不超过40%\n"
            "- 每个场景必须有对话（独处场景用自言自语/回忆/打电话）\n"
            "- 严格遵循 Director 的情绪弧线和节奏策略",
        ]

        # Varying context — changes per chapter
        parts.append(f"\n=== TARGET ===\n目标字数: {packet.chapter_plan.target_chars}")

        if packet.director_guidance.guidance_id:
            dg = packet.director_guidance
            guidance_parts = []
            if dg.character_anchor:
                guidance_parts.append(f"角色锚点: {dg.character_anchor}")
            if dg.timeline_anchor:
                guidance_parts.append(f"时间锚点: {dg.timeline_anchor}")
            if dg.beat_details:
                for bd in dg.beat_details:
                    guidance_parts.append(f"  [{bd.beat_id}] {bd.content_outline}")
                    if bd.emotion_shift:
                        guidance_parts.append(f"    情绪: {bd.emotion_shift}")
                    if bd.hook_execution:
                        guidance_parts.append(f"    钩子: {bd.hook_execution}")
            parts.append(f"\n=== DIRECTOR GUIDANCE ===\n" + "\n".join(guidance_parts))

        if packet.writing_intent:
            parts.append(f"\n=== WRITING INTENT ===\n{packet.writing_intent}")

        parts.append(f"\n=== CHAPTER PLAN ===\n{packet.chapter_plan.to_dict()}")

        if packet.previous_chapter_summary:
            parts.append(f"\n=== PREVIOUS CHAPTER ===\n{packet.previous_chapter_summary}")

        if packet.character_states:
            parts.append(f"\n=== CHARACTER STATES ===\n{packet.character_states}")

        if packet.active_memory_context:
            parts.append(
                "\n=== ACTIVE MEMORY ===\n"
                + self._format_memory_items(packet.active_memory_context)
            )

        if packet.memory_recall:
            parts.append(
                "\n=== MEMORY RECALL ===\n"
                + self._format_memory_items(packet.memory_recall)
            )

        if packet.foreshadowing_items:
            parts.append(
                "\n=== FORESHADOWING ===\n"
                + "\n".join(
                    f"- [{i.get('status', 'active')}] {i.get('entity', '')}: {i.get('content', '')}"
                    for i in packet.foreshadowing_items
                )
            )

        if packet.relevant_ledger_items:
            items_text = "\n".join(f"- [{i.section}] {i.entity}: {i.content}" for i in packet.relevant_ledger_items)
            parts.append(f"\n=== CONTINUITY CONTEXT ===\n{items_text}")

        return _get_writer_prompt(), "\n".join(parts)

    def _build_beat_prompt(self, packet: NovelWritePacket) -> tuple[str, str]:
        """Build prompt for a single beat. Returns (system_prompt, user_prompt)."""
        beat = packet.current_scene_beat

        # Stable prefix
        parts = [
            "=== OUTPUT RULES ===\n"
            "- 只输出本 beat 的正文\n"
            "- 无标签、无 JSON、无元信息\n"
            "- 对话+行为占正文60%以上，描写不超过40%\n"
            "- 必须有对话。即使 beat 描述没提对话，也要加入：自言自语、回忆别人说过的话、对物件说话、打电话\n"
            "- 对话要有互动感和功能：不是轮流发言，要推进剧情/展示人设/制造冲突\n"
            "- 描写点到即止：一个物件一句话，不要铺开写三句",
            f"\n=== TARGET ===\n字数: {beat.budget_chars} | 密度: {beat.density}",
        ]

        # Varying context
        parts.append(f"\n=== CURRENT BEAT ===\n"
                    f"描述: {beat.description}\n"
                    f"功能: {beat.function_tag}\n"
                    f"注意：以上描述只是骨架。你必须用对话填充血肉。没有对话的beat是失败的。")

        if packet.accumulated_text:
            # Show last 500 chars for style continuity
            tail = packet.accumulated_text[-500:]
            parts.append(f"\n=== ACCUMULATED TEXT (tail) ===\n{tail}")

        parts.append(f"\n=== CHAPTER PLAN (summary) ===\n"
                    f"标题: {packet.chapter_plan.title}\n"
                    f"情绪: {packet.chapter_plan.target_emotion}\n"
                    f"位置: {packet.chapter_plan.chapter_position}")

        if packet.director_guidance.guidance_id:
            dg = packet.director_guidance
            if dg.character_anchor:
                parts.append(f"\n=== DIRECTOR GUIDANCE ===\n"
                            f"角色锚点: {dg.character_anchor}\n"
                            f"时间锚点: {dg.timeline_anchor}")

        if packet.active_memory_context:
            parts.append(
                "\n=== ACTIVE MEMORY ===\n"
                + self._format_memory_items(packet.active_memory_context)
            )

        if packet.memory_recall:
            parts.append(
                "\n=== MEMORY RECALL ===\n"
                + self._format_memory_items(packet.memory_recall)
            )

        if packet.foreshadowing_items:
            parts.append(
                "\n=== FORESHADOWING ===\n"
                + "\n".join(
                    f"- [{i.get('status', 'active')}] {i.get('entity', '')}: {i.get('content', '')}"
                    for i in packet.foreshadowing_items
                )
            )

        parts.append(f"\n=== OUTPUT RULES ===\n"
                    f"- 只输出本 beat 的正文\n"
                    f"- 目标 {beat.budget_chars} 字\n"
                    f"- 密度: {beat.density}\n"
                    f"- 无标签、无 JSON、无元信息")

        return _get_writer_prompt(), "\n".join(parts)

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
