"""NovelDirectorAdapter — Director LLM adapter for novel mode v2.

Uses DeepSeekAdapter with thinking=high for global story optimization.
v2: McKee 框架驱动，输出 beat 细纲 + 事实锚点。
"""

from __future__ import annotations

from typing import Any

from ..contracts.novel_director_guidance import DirectorGuidance

# Director system prompt (McKee framework)
DIRECTOR_SYSTEM_PROMPT = """=== DIRECTOR CONTRACT v2 ===
你是长篇网文的大纲优化导演。你的核心职责是**编排故事**，不是编排句式。
你不是写手，你不出正文。你是"总编辑 + 导演"的结合体。
你的任务是告诉 Writer：这个场景讲什么、用什么方式讲、信息怎么分配。

=== 第一原则：事实锚定 ===
你必须在输出开头明确两组事实，Writer 必须遵守，不可修改：

character_anchor：本章出场角色的基础事实。
格式："角色名: 年龄性别, 核心身份, 关键特征 | 角色名: ..."
要求：从角色状态和章节计划中提取，包含年龄、性别、核心身份、关键特征。不可编造。

timeline_anchor：故事时间锚点。
格式："第X章, 故事内时间描述"
要求：从章节编号和已完成章节摘要中推算，明确当前是故事的第几天/什么时段。不可编造。

=== 第二原则：beat 细纲（McKee 框架）===
对 Architect 给出的每个 scene_beat，你必须展开成细纲。每个 beat 是一个最小故事单位：
角色做出一个行为，产生一个不可逆的变化。

每个 beat 包含以下字段：

1. content_outline：具体事件。谁做了什么，发生了什么。不要写笼统的方向，要写具体的动作和事件。
2. gap（McKee 差距）：角色的期望 vs 实际结果的落差。每个 beat 都应该有 gap——角色以为会发生X，结果发生了Y。
3. complication（递进复杂化）：这个 beat 比上一个 beat 复杂/危险/紧迫在哪。故事的复杂度必须逐 beat 递增。
4. pressure_point（压力点）：角色在这个 beat 面对什么压力或两难选择。McKee 说"角色在压力下的选择才暴露真面目"。
5. dialogue_keys：关键对白要点。不是写完整对话，而是标注：谁对谁说了什么类型的话，潜台词是什么。
   格式：["角色A→角色B: 表面说X（潜台词：真实意图是Y）", "..."]
6. info_release：读者在这个 beat 新知道什么信息。每个 beat 必须推进读者的认知。
7. emotion_shift：情绪翻转。从什么情绪变到什么情绪（如"压抑→怀疑"）。
8. info_type：这个 beat 主要通过什么方式传递信息。"对话" / "行为" / "叙述" / "内心推断" / "物证发现"
9. hook_execution：这个 beat 的钩子怎么落地。类型：悬念（留下未解问题）/ 情绪（制造缺口）/ 反转（颠覆预期）/ 信息差（读者知道角色不知道，或反过来）

=== 第三原则：对话驱动 ===
读者是为了看"故事内容"来的。故事内容 = 人物的行为和语言。
- 哪些信息通过对话传递（人物之间的交流、冲突、试探）
- 哪些情绪通过行为展现（动作、反应、选择）
- 哪些背景通过叙述交代（点到即止，不铺开）
- 对话占比目标：30-40%。如果某个 beat 没有对话对象，要设计自言自语、回忆别人的话、打电话等方式

=== 第四原则：钩子编排 ===
每个 beat 必须有钩子。不要等到章末才留悬念。
钩子类型：
- 悬念钩：留下未解的问题
- 情绪钩：制造情绪缺口
- 反转钩：颠覆预期
- 信息差：读者知道角色不知道，或反过来

=== OUTPUT FORMAT（必须严格遵守）===
只输出一个 JSON 对象，不要任何 markdown、不要 ``` 代码块、不要前后解释文字。
JSON 必须能直接被 json.loads 解析。

{
  "guidance_id": "guid-ch{章节编号}",
  "character_anchor": "角色名: 年龄性别, 核心身份, 关键特征 | ...",
  "timeline_anchor": "第X章, 搬入第N天, DayN 时段→时段",
  "beat_details": [
    {
      "beat_id": "b1",
      "content_outline": "具体事件描述（谁做了什么，发生了什么）",
      "gap": "期望vs结果的落差",
      "complication": "比上一个beat复杂在哪",
      "pressure_point": "角色面对的压力或两难选择",
      "dialogue_keys": ["角色A→角色B: 表面说X（潜台词：Y）"],
      "info_release": "读者新知道什么",
      "emotion_shift": "从X情绪→Y情绪",
      "info_type": "对话/行为/叙述/内心推断/物证发现",
      "hook_execution": "钩子类型+具体怎么落地"
    }
  ],
  "outline_enhancements": [],
  "foreshadowing_schedule": [],
  "subplot_status": [],
  "risk_flags": [],
  "opportunities": [],
  "reasoning": "简要推理过程"
}

若你不确定某个字段，写空字符串或空数组，但不要省略字段，不要输出 JSON 以外的内容。
"""


class NovelDirectorAdapter:
    """Director LLM adapter for novel mode v2."""

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

        # Fallback: construct minimal guidance
        return DirectorGuidance(
            guidance_id=f"guid-{chapter_plan.chapter_id}",
            character_anchor="",
            timeline_anchor="",
        )

    @staticmethod
    def _extract_json_object(text: str) -> str | None:
        """Best-effort extract the first balanced top-level JSON object from text.

        Handles: ```json fences, leading/trailing prose, nested braces,
        truncated JSON (tries to close open braces).
        """
        if not text:
            return None
        t = text.strip()

        # 1. Strip markdown code fences
        if t.startswith("```"):
            first_newline = t.find("\n")
            if first_newline != -1:
                t = t[first_newline + 1:]
            last_fence = t.rfind("```")
            if last_fence != -1:
                t = t[:last_fence]
            t = t.strip()

        # 2. Find first { and extract balanced JSON
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
                    candidate = t[start:i + 1]
                    import json
                    try:
                        json.loads(candidate)
                        return candidate
                    except (json.JSONDecodeError, ValueError):
                        repaired = candidate.replace("\n", "\\n").replace("\r", "\\r")
                        try:
                            json.loads(repaired)
                            return repaired
                        except (json.JSONDecodeError, ValueError):
                            return None

        # 3. Truncated JSON — try to close open braces
        remaining = t[start:]
        open_count = remaining.count("{")
        close_count = remaining.count("}")
        if open_count > close_count:
            suffix = "}" * (open_count - close_count)
            candidate = remaining + suffix
            import json
            try:
                json.loads(candidate)
                return candidate
            except (json.JSONDecodeError, ValueError):
                pass
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
            "6. 确定事实锚点：角色年龄/身份/时间线，这些 Writer 不可修改\n"
            "7. 逐 beat 展开细纲：content_outline → gap → complication → pressure_point → dialogue_keys → info_release → emotion_shift → info_type → hook_execution\n"
            "8. 最后：检查 beat 之间的递进关系和钩子连贯性",
        ]

        # Varying context
        parts.append(f"\n=== CURRENT TASK ===\n当前要写第 {chapter_plan.chapter_index} 章")
        parts.append(f"\n章节计划:\n{chapter_plan.to_dict()}")

        if previous_chapter_ending:
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

        if completed_chapters_summary:
            parts.append(f"\n已完成章节摘要:\n{completed_chapters_summary}")

        parts.append(
            "\n=== FINAL REMINDER ===\n"
            "按 OUTPUT FORMAT 只输出一个 JSON 对象。不要 markdown，不要解释。\n"
            "beat_details 的数量必须和章节计划里的 scene_beats 数量一致。"
        )

        return DIRECTOR_SYSTEM_PROMPT, "\n".join(parts)
