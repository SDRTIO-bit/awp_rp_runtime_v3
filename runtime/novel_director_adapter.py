"""NovelDirectorAdapter — Director LLM adapter for novel mode.

Uses DeepSeekAdapter with thinking=high for global story optimization.
"""

from __future__ import annotations

from typing import Any

from ..contracts.novel_director_guidance import DirectorGuidance

# Thinking configuration for deep reasoning
_THINKING_HIGH = {"thinking": {"type": "enabled", "reasoning_effort": "high"}}

# Director system prompt (core rules from oh-story)
DIRECTOR_SYSTEM_PROMPT = """=== STABLE DIRECTOR CONTRACT ===
你是长篇网文的大纲优化导演。你有两个核心职责：
1. 为当前章节提供精确的叙事方向
2. 审视全书结构，持续优化故事线

你不是写手，你不出正文。你是"总编辑 + 导演"的结合体。
你需要用深度思考来审视故事的全局结构，发现读者会注意到但作者可能忽略的问题。

=== 爽点设计体系 ===
爽点不只是装逼打脸，而是包含各种各样的情绪满足。
六种爽点类型：能力碾压、目标达成、收获盘点、态度转变、隐藏身份/掉马甲、情感圆满度。
设计爽点的倒推法：先确定爽点类型 → 再设计期待点 → 最后设计铺垫。

=== 情绪升级与对比 ===
- 爽点需要层层铺垫和递进
- 负面情绪要逐步升级到饱和，再转化为正面情绪
- 对比是爽文的底层逻辑：配角失败 vs 主角成功

=== 递进对抗写法 ===
主角与反派的对抗不是一路碾压。让主角在每次小角力中稍占上风，最后迎来大胜利。
斗地主比喻：主角对三，反派对四，主角对A，反派对2，最后主角王炸一锤定音。

=== 节奏控制 ===
| 要素 | 规则 |
|------|------|
| 大高潮周期 | 7-10章，超过10章读者易反感 |
| 小高潮周期 | 3章左右 |
| 高潮后过渡 | 加1-2章日常过渡 |
| 公众期5章循环 | 1章人设+2章铺垫+1章打脸+1章反响 |

=== 驱动读者欲望四步公式 ===
生产诉求 → 给予希望 → 努力解决 → 得偿所愿

=== 思维链受限 ===
深度思考用于审视结构，但思考过程不写入最终输出。最终输出只允许是一个 JSON 对象。

=== 结构设计 ===
五幕式因果链：开局(种子) → 发展(生长) → 转折(转折) → 行动(冲刺) → 结局(完成)

=== 情绪模块与戏剧单元 ===
四级提炼：具体故事 → 经典情节 → 故事构型 → 戏剧单元 → 情绪模块
故事构型+素材=具体故事。用法：①重构（保留素材改构型）②微调（保留走向加新模块）

=== OUTPUT FORMAT（必须严格遵守）===
只输出一个 JSON 对象，不要任何 markdown、不要 ``` 代码块、不要前后解释文字。
JSON 必须能直接被 json.loads 解析。字段如下（除标注外都是 string，缺失字段用空字符串）：

{
  "guidance_id": "string",
  "chapter_direction": "string — 本章叙事方向与重点",
  "emotional_arc": "string — 本章情绪弧线 开头→中间→结尾",
  "pacing_strategy": "string — 节奏策略",
  "key_scenes": ["string", "..."],
  "dialogue_tone": "string — 对话基调",
  "reader_expectation_plan": "string — 读者预期操控",
  "reasoning": "string — 推理过程（供审查）"
}

若你不确定某个字段，写空字符串或空数组，但不要省略字段，不要输出 JSON 以外的内容。
"""


class NovelDirectorAdapter:
    """Director LLM adapter for novel mode."""

    def __init__(self, registry, model: str = "deepseek-v4-pro"):
        self._registry = registry
        self._model = model

    def generate_guidance(
        self,
        project_id: str,
        chapter_plan: Any,
        completed_chapters_summary: str,
        ledger_items: list,
        character_states: dict,
        foreshadowing_list: list,
        subplot_status: list,
        previous_chapter_ending: str,
    ) -> DirectorGuidance:
        """Generate Director guidance for a chapter."""
        system_prompt, user_prompt = self._build_prompt(
            project_id, chapter_plan, completed_chapters_summary,
            ledger_items, character_states, foreshadowing_list,
            subplot_status, previous_chapter_ending,
        )
        # Call LLM and parse JSON response
        from .novel_llm_factory import NovelLLMFactory
        factory = NovelLLMFactory.get_instance()
        adapter = factory.get_adapter("director")
        thinking = factory.get_thinking_config("director")
        model = factory.get_model("director")
        max_tokens = factory.get_max_tokens("director")

        try:
            text, receipt = adapter.generate_text(
                user_prompt,
                max_tokens=max_tokens,
                provider_role="novel_director",
                model=model,
                extra_body=thinking,
                system_prompt=system_prompt,
            )
        except Exception:
            text = ""

        # Parse JSON response robustly: tolerate ```json fences and leading prose.
        import json
        extracted = self._extract_json_object(text)
        if extracted is not None:
            try:
                data = json.loads(extracted)
                return DirectorGuidance.from_dict(data)
            except (json.JSONDecodeError, TypeError):
                pass

        # Last resort: keep only a short chapter_direction, drop the long reasoning
        # (previously we leaked the full reasoning text into the packet, wasting
        #  tens of thousands of tokens downstream for no value).
        cleaned = text.strip()
        if len(cleaned) > 400:
            cleaned = cleaned[:400]
        return DirectorGuidance(
            guidance_id=f"guid-{chapter_plan.chapter_id}",
            chapter_direction=cleaned or "推进主线",
        )

    @staticmethod
    def _extract_json_object(text: str) -> str | None:
        """Best-effort extract the first balanced top-level JSON object from text.

        Strips ```json fences, then scans for the outermost {...}. Returns the
        substring or None if no brace pair is found.
        """
        if not text:
            return None
        t = text.strip()
        # Strip markdown code fences
        if t.startswith("```"):
            # remove opening fence (with optional language tag)
            first_newline = t.find("\n")
            if first_newline != -1:
                t = t[first_newline + 1:]
            # remove closing fence if present
            if t.endswith("```"):
                t = t[:-3]
            t = t.strip()
        # Find outermost brace pair
        start = t.find("{")
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(t)):
            ch = t[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return t[start:i + 1]
        return None

    def _build_prompt(
        self, project_id, chapter_plan, completed_chapters_summary,
        ledger_items, character_states, foreshadowing_list,
        subplot_status, previous_chapter_ending,
    ) -> tuple[str, str]:
        """Returns (system_prompt, user_prompt).

        Optimized for DeepSeek prefix caching: stable rules first.
        """
        # Stable prefix — cacheable
        parts = [
            "=== THINKING WORKFLOW ===\n"
            "1. 先审视全书结构：当前处于什么阶段？节奏是否合理？\n"
            "2. 检查伏笔：有哪些需要推进？有哪些需要埋设？\n"
            "3. 检查角色弧光：主要角色在本章应该有什么成长？\n"
            "4. 检查支线：哪些支线需要推进？哪些可以暂缓？\n"
            "5. 设计读者预期：本章应该给读者什么期待？如何误导或满足？\n"
            "6. 最后：为 Writer 提供精确的本章方向",
        ]

        # Varying context
        parts.append(f"\n=== CURRENT TASK ===\n当前要写第 {chapter_plan.chapter_index} 章")
        parts.append(f"\n章节计划:\n{chapter_plan.to_dict()}")
        parts.append(f"\n前一章结尾:\n{previous_chapter_ending}")

        if character_states:
            parts.append(f"\n角色状态:\n{character_states}")

        if foreshadowing_list:
            parts.append(f"\n伏笔清单:\n{foreshadowing_list}")

        if subplot_status:
            parts.append(f"\n支线进度:\n{subplot_status}")

        if ledger_items:
            items_text = "\n".join(f"- [{i.section}] {i.entity}: {i.content}" for i in ledger_items[:20])
            parts.append(f"\n连续性账本:\n{items_text}")

        parts.append(f"\n已完成章节摘要:\n{completed_chapters_summary}")

        parts.append(
            "\n=== FINAL REMINDER ===\n"
            "按 OUTPUT FORMAT 只输出一个 JSON 对象。不要 markdown，不要解释。"
        )

        return DIRECTOR_SYSTEM_PROMPT, "\n".join(parts)
