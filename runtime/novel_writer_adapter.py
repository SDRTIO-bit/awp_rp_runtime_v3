"""NovelWriterAdapter — Chapter Writer LLM adapter for novel mode.

Uses DeepSeekAdapter with thinking=medium for creative writing.
"""

from __future__ import annotations

from typing import Any

from ..contracts.novel_write_packet import NovelWritePacket
from ..contracts.novel_chapter import ChapterPlan, BeatDetail

# Thinking configuration for creative writing
_THINKING_MEDIUM = {"thinking": {"type": "enabled", "reasoning_effort": "medium"}}

# Writer system prompt (core rules from oh-story)
WRITER_SYSTEM_PROMPT = """=== STABLE WRITING CONTRACT ===
你是长篇网文的章节写手。你只输出正文，不出标签、无JSON、无元信息。

=== 叙述姿态：深度限知 ===
锁死主视角角色的"此刻感知"——只写他此刻看到、听到、闻到、身体感到、脑中闪过的东西。
- 镜头不拉远、不俯瞰、不切他人内心。
- 读者与角色同步获知：角色不知道的不写；不提前剧透，不补全背景。
- 念头是动作的一部分：心理用"闪念+身体"呈现——半句的、被打断的、带情绪偏见的主观判断。
- 主观偏差代替客观叙述：场景被角色情绪染色。

=== 身体细节替代情绪词 ===
禁止直接写出情绪词。用身体状态、物理损伤、日常动作替代。
| 禁止 | 替换为 |
|------|--------|
| 心痛/心碎 | 手指掐进肉里自己不知道疼 |
| 悲伤/难过 | 他把外套叠了三叠，放回衣柜最里面那一层 |
| 愤怒/气得发抖 | 她手背上的青筋一根根暴起来 |
| 害怕/恐惧 | 他的手指碰到门把手又缩回来，碰了三次才握住 |

=== 三维度揉进 ===
每个子事件包含三个维度：发生了什么、主角注意到什么、身体怎么回应。
三个维度同时揉进同一段连续正文，不按维度分段写。

=== 疏密分配 ===
- 爽点/打脸/反转/情绪高潮 → 密（详写，≥250字）
- 过场/赶路/信息交代 → 疏（略写，≈40字）
- 铺垫/日常/关系升温 → 中（120-150字）

=== 开头事件密度 ===
前 100 字必须包含 ≥ 3 个事件。不做背景铺垫，直接上事件链。

=== 一动一静节奏 ===
每个小节内部交替动作和安静。动后必静，静后可动。

=== 对话规则 ===
- 每句话至少满足一项：推进剧情 / 展示人设 / 制造冲突
- 用语气、动作、省略来暗示潜台词
- 日常用语，不要书面腔
- 对话标签 < 50%，用动作代替"XX说"

=== 标点谱系 ===
正文和对话都禁用省略号和破折号，改用句号、逗号、短句或动作断句。

=== 贯穿道具（三次出现规则）===
每个叙事单元设计 1-2 个贯穿道具。每个物件必须出现 3 次，每次意义不同。

=== 数字叙事 ===
用具体数字替代模糊描述。数字承载情感重量。

=== 主语与名字节奏 ===
段首、场景切换用主角名；同一动作链内优先用"他/她"；关键转折时再点名强化。

=== 画面分段 ===
断段按镜头/信息变化，不按维度变化。不要连续多段同长度。

=== 章尾钩子 13 式 ===
突然揭示/紧急危机/未完成动作/身份反转/两难抉择/神秘物品/倒计时/承诺威胁/离奇消失/隐藏含义/意象钩子/回声钩子/留白钩子

=== 反注水规则 ===
禁止：为凑字数加环境描写、重复情绪、加内心独白总结、做无意义动作、用情绪词代替身体细节。

=== 字数硬约束 ===
默认最低字数：3000 字/章。细纲另有标注时以细纲为准。
"""


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
            "- 严格遵循 Director 的情绪弧线和节奏策略",
        ]

        # Varying context — changes per chapter
        parts.append(f"\n=== TARGET ===\n目标字数: {packet.chapter_plan.target_chars}")

        if packet.director_guidance.guidance_id:
            parts.append(f"\n=== DIRECTOR GUIDANCE ===\n"
                        f"方向: {packet.director_guidance.chapter_direction}\n"
                        f"情绪弧线: {packet.director_guidance.emotional_arc}\n"
                        f"节奏策略: {packet.director_guidance.pacing_strategy}\n"
                        f"对话基调: {packet.director_guidance.dialogue_tone}")

        if packet.writing_intent:
            parts.append(f"\n=== WRITING INTENT ===\n{packet.writing_intent}")

        parts.append(f"\n=== CHAPTER PLAN ===\n{packet.chapter_plan.to_dict()}")

        if packet.previous_chapter_summary:
            parts.append(f"\n=== PREVIOUS CHAPTER ===\n{packet.previous_chapter_summary}")

        if packet.character_states:
            parts.append(f"\n=== CHARACTER STATES ===\n{packet.character_states}")

        if packet.relevant_ledger_items:
            items_text = "\n".join(f"- [{i.section}] {i.entity}: {i.content}" for i in packet.relevant_ledger_items)
            parts.append(f"\n=== CONTINUITY CONTEXT ===\n{items_text}")

        return WRITER_SYSTEM_PROMPT, "\n".join(parts)

    def _build_beat_prompt(self, packet: NovelWritePacket) -> tuple[str, str]:
        """Build prompt for a single beat. Returns (system_prompt, user_prompt)."""
        beat = packet.current_scene_beat

        # Stable prefix
        parts = [
            "=== OUTPUT RULES ===\n"
            "- 只输出本 beat 的正文\n"
            "- 无标签、无 JSON、无元信息\n"
            "- 严格遵循风格设定",
            f"\n=== TARGET ===\n字数: {beat.budget_chars} | 密度: {beat.density}",
        ]

        # Varying context
        parts.append(f"\n=== CURRENT BEAT ===\n"
                    f"描述: {beat.description}\n"
                    f"功能: {beat.function_tag}")

        if packet.accumulated_text:
            # Show last 500 chars for style continuity
            tail = packet.accumulated_text[-500:]
            parts.append(f"\n=== ACCUMULATED TEXT (tail) ===\n{tail}")

        parts.append(f"\n=== CHAPTER PLAN (summary) ===\n"
                    f"标题: {packet.chapter_plan.title}\n"
                    f"情绪: {packet.chapter_plan.target_emotion}\n"
                    f"位置: {packet.chapter_plan.chapter_position}")

        if packet.director_guidance.guidance_id:
            parts.append(f"\n=== DIRECTOR GUIDANCE ===\n"
                        f"方向: {packet.director_guidance.chapter_direction}\n"
                        f"情绪弧线: {packet.director_guidance.emotional_arc}")

        parts.append(f"\n=== OUTPUT RULES ===\n"
                    f"- 只输出本 beat 的正文\n"
                    f"- 目标 {beat.budget_chars} 字\n"
                    f"- 密度: {beat.density}\n"
                    f"- 无标签、无 JSON、无元信息")

        return WRITER_SYSTEM_PROMPT, "\n".join(parts)

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
