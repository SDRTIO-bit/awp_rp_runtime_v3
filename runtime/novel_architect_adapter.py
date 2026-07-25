"""NovelArchitectAdapter — Architect LLM adapter for novel mode.

Uses DeepSeekAdapter with thinking=high for chapter planning.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from ..contracts.novel_chapter import (
    BeatDetail,
    ChapterPlan,
    CharacterAppearance,
    ContentSummary,
    EndingDesign,
    PlotArrangement,
)
from ..contracts.novel_pi_role_protocol import NovelPiRoleTask
from .novel_role_context import get_novel_role_context
from .novel_role_runtime import get_novel_role_runtime

# Thinking configuration for structural planning
_THINKING_HIGH = {"thinking": {"type": "enabled", "reasoning_effort": "high"}}

# Architect system prompt — loaded from prompts/architect.md
from .prompt_loader import load_prompt

def _get_architect_prompt(name: str = "architect") -> str:
    return load_prompt(name)


class NovelArchitectAdapter:
    """Architect LLM adapter for novel mode."""

    def __init__(self, registry, model: str = "deepseek-v4-pro", architect_prompt_name: str = "architect"):
        self._registry = registry
        self._model = model
        self._architect_prompt_name = architect_prompt_name

    def plan_chapter(
        self,
        project_id: str,
        chapter_index: int,
        volume_plan: Any,
        completed_chapters: list,
        ledger_items: list,
        character_states: dict,
        task_description: str = "",
        prev_chapter_ending: str = "",
        prev_ending_design: Any = None,
        completed_text_context: str = "",
    ) -> ChapterPlan:
        """Generate a chapter plan."""
        system_prompt, user_prompt = self._build_prompt(
            project_id, chapter_index, volume_plan,
            completed_chapters, ledger_items, character_states,
            task_description, prev_chapter_ending, prev_ending_design,
            completed_text_context=completed_text_context,
        )
        # Architect is a real Pi Agent Session. Python keeps final schema parsing.
        context = get_novel_role_context()
        result = get_novel_role_runtime().run(
            NovelPiRoleTask(
                role="architect",
                project_id=project_id,
                chapter_index=chapter_index,
                revision=context.revision,
                phase="chapter_plan",
                session_key=f"task:{uuid.uuid4().hex}",
                task_contract=system_prompt,
                input_payload={
                    "prompt": user_prompt,
                    "response_format": "chapter_plan_json",
                },
            ),
            context=context,
        )
        text = result.text

        # Parse JSON response robustly (tolerate ```json fences, leading prose).
        extracted = self._extract_json_object(text)
        if extracted is None:
            # Parsing failed. Previously we silently returned an empty ChapterPlan
            # (no scene_beats), which made NovelEngine fall back to whole-chapter
            # naked generation — the opposite of the beat-by-beat design and a
            # token black hole. Now raise so batch_write can mark this chapter
            # failed and skip it instead of writing a meaningless draft.
            raise ValueError(
                f"Architect did not return JSON for chapter {chapter_index}. "
                f"Head of response: {text[:200]!r}"
            )

        try:
            data = json.loads(extracted)
            plan = ChapterPlan.from_dict(data)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            raise ValueError(
                f"Architect JSON parse failed for chapter {chapter_index}: {e}. "
                f"Head: {extracted[:200]!r}"
            )

        # Ensure scene_beats is non-empty (the whole point of the architect step).
        scene_beats = tuple(
            BeatDetail.from_dict(b) for b in data.get("scene_beats", [])
        )
        if not scene_beats:
            raise ValueError(
                f"Architect plan for chapter {chapter_index} has no scene_beats. "
                f"Beat-by-beat generation requires at least one beat."
            )

        # Override metadata to ensure consistency
        plan = ChapterPlan(
            schema_id=plan.schema_id,
            schema_version=plan.schema_version,
            chapter_id=plan.chapter_id or f"ch-{project_id}-{chapter_index}",
            project_id=project_id,
            volume_id=plan.volume_id,
            chapter_index=chapter_index,
            title=plan.title or f"第{chapter_index}章",
            # Novel mode now uses a single continuous scene per chapter.
            # Keep the target stable so Architect/Writer/quality checks do not
            # reintroduce the previous multi-beat 3k–6k tug of war.
            target_chars=2000,
            chapter_position=plan.chapter_position,
            target_emotion=plan.target_emotion,
            opening_hook=plan.opening_hook,
            main_payoff=plan.main_payoff,
            content_summary=plan.content_summary,
            plot_arrangement=plan.plot_arrangement,
            character_appearance=plan.character_appearance,
            scene_beats=scene_beats,
            ending_design=plan.ending_design,
            cost_and_reward=plan.cost_and_reward,
        )
        return self._compact_plan(plan)

    @staticmethod
    def _compact_text(value: Any, limit: int) -> str:
        """Remove screenplay-level detail and cap one planning field."""
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        # Remove spoken lines, but preserve quoted state labels such as
        # “从‘戒备’到‘信任’”; those labels carry structural meaning.
        dialogue_replacements = {
            "说": "简短说明",
            "问": "追问",
            "喊": "喊了一声",
            "宣布": "说明了处理结果",
            "自嘲": "自嘲了一句",
            "回应": "简短回应",
        }
        text = re.sub(
            r"(说|问|喊|宣布|自嘲|回应)(?:道)?[：，]?\s*[‘“\"][^’”\"]+[’”\"]",
            lambda match: dialogue_replacements[match.group(1)] + "，",
            text,
        )
        text = re.sub(r"：\s*[‘“\"][^’”\"]+[’”\"]", "", text)
        text = re.sub(r"[，；：]+([。！？])", r"\1", text)
        text = re.sub(r"\s+([，。；：！？])", r"\1", text).strip(" ，；：")
        text = re.sub(r"([，。；：！？])\s+", r"\1", text)
        text = text.replace("，同时，", "。同时，")
        if len(text) <= limit:
            return text
        candidate = text[:limit]
        boundaries = sorted(
            (index for index, char in enumerate(candidate) if char in "。！？；，"),
            reverse=True,
        )
        dependent_endings = ("时", "后", "却", "但", "并", "而", "因为", "如果", "虽然", "同时")
        for boundary in boundaries:
            clause = candidate[:boundary].rstrip()
            if boundary >= limit // 2 and not clause.endswith(dependent_endings):
                ending = candidate[boundary]
                return clause + (ending if ending in "。！？" else "。")
        return candidate.rstrip("，；：") + "。"

    @classmethod
    def _compact_plan(cls, plan: ChapterPlan) -> ChapterPlan:
        """Keep the persisted Plan meaningfully shorter than its chapter."""
        cs = plan.content_summary
        plot = plan.plot_arrangement
        appearance = plan.character_appearance
        ending = plan.ending_design
        return ChapterPlan(
            schema_id=plan.schema_id,
            schema_version=plan.schema_version,
            chapter_id=plan.chapter_id,
            project_id=plan.project_id,
            volume_id=plan.volume_id,
            chapter_index=plan.chapter_index,
            title=cls._compact_text(plan.title, 30),
            target_chars=plan.target_chars,
            chapter_position=cls._compact_text(plan.chapter_position, 24),
            target_emotion=cls._compact_text(plan.target_emotion, 40),
            opening_hook=cls._compact_text(plan.opening_hook, 50),
            main_payoff=cls._compact_text(plan.main_payoff, 50),
            content_summary=ContentSummary(
                cause=cls._compact_text(cs.cause, 50),
                development=cls._compact_text(cs.development, 50),
                turning_point=cls._compact_text(cs.turning_point, 50),
                climax=cls._compact_text(cs.climax, 50),
                ending=cls._compact_text(cs.ending, 50),
            ),
            plot_arrangement=PlotArrangement(
                main_line=cls._compact_text(plot.main_line, 40),
                sub_line=cls._compact_text(plot.sub_line, 30),
                event_line=cls._compact_text(plot.event_line, 30),
                emotion_line=cls._compact_text(plot.emotion_line, 40),
                logic_line=cls._compact_text(plot.logic_line, 40),
            ),
            character_appearance=CharacterAppearance(
                appearance_order=appearance.appearance_order,
                relationship_changes=tuple(
                    cls._compact_text(change, 40)
                    for change in appearance.relationship_changes[:2]
                ),
                information_gap=cls._compact_text(appearance.information_gap, 30),
            ),
            scene_beats=tuple(
                BeatDetail(
                    beat_id=beat.beat_id,
                    description=cls._compact_text(beat.description, 45),
                    function_tag=cls._compact_text(beat.function_tag, 12),
                    density=beat.density,
                    budget_chars=beat.budget_chars,
                )
                for beat in plan.scene_beats[:4]
            ),
            ending_design=EndingDesign(
                closing_state=cls._compact_text(ending.closing_state, 40),
                open_questions=tuple(
                    cls._compact_text(question, 30)
                    for question in ending.open_questions[:1]
                ),
                next_chapter_push=cls._compact_text(ending.next_chapter_push, 30),
                hook_type=cls._compact_text(ending.hook_type, 12),
                hook_detail=cls._compact_text(ending.hook_detail, 40),
                hook_strength=ending.hook_strength,
            ),
            cost_and_reward=cls._compact_text(plan.cost_and_reward, 60),
        )

    @staticmethod
    def _extract_json_object(text: str) -> str | None:
        """Best-effort extract the first balanced top-level JSON object from text.

        Handles: ```json fences, leading/trailing prose, nested braces.
        """
        if not text:
            return None
        t = text.strip()

        import re
        import json

        def valid_object(candidate: str) -> str | None:
            try:
                json.loads(candidate)
                return candidate
            except (json.JSONDecodeError, ValueError):
                repaired: list[str] = []
                in_string = False
                escape = False
                for index, char in enumerate(candidate):
                    if not in_string:
                        repaired.append(char)
                        if char == '"':
                            in_string = True
                        continue
                    if escape:
                        repaired.append(char)
                        escape = False
                        continue
                    if char == "\\":
                        repaired.append(char)
                        escape = True
                        continue
                    if char != '"':
                        repaired.append(char)
                        continue

                    # A model sometimes writes Chinese quotation marks with
                    # ASCII double quotes inside an already quoted JSON value.
                    # A closing JSON quote is followed by a structural token;
                    # otherwise retain it as escaped prose punctuation.
                    suffix = candidate[index + 1:].lstrip()
                    if suffix and suffix[0] not in ",}]:":
                        repaired.append("\\\"")
                    else:
                        repaired.append(char)
                        in_string = False
                repaired_text = "".join(repaired)
                try:
                    json.loads(repaired_text)
                    return repaired_text
                except (json.JSONDecodeError, ValueError):
                    return None

        # OpenCode models often emit reasoning before a fenced final response.
        # Prefer every fenced JSON payload before considering braces in prose.
        for fenced in re.findall(r"```(?:json)?\s*(.*?)\s*```", t, re.DOTALL):
            candidate = valid_object(fenced.strip())
            if candidate is not None:
                return candidate

        # Fall back to each balanced object, rather than stopping at the first
        # brace in prose such as "{constraint}".
        for start, char in enumerate(t):
            if char != "{":
                continue
            depth = 0
            in_string = False
            escape = False
            for index in range(start, len(t)):
                ch = t[index]
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
                        candidate = valid_object(t[start:index + 1])
                        if candidate is not None:
                            return candidate
                        break
        return None

    def _build_prompt(
        self, project_id, chapter_index, volume_plan,
        completed_chapters, ledger_items, character_states,
        task_description, prev_chapter_ending="", prev_ending_design=None,
        completed_text_context="",
    ) -> tuple[str, str]:
        """Returns (system_prompt, user_prompt).

        Optimized for DeepSeek prefix caching: stable rules first.
        """
        # Stable prefix — cacheable
        parts = [
            "=== OUTPUT FORMAT ===\n"
            "输出 JSON，符合 ChapterPlan schema。\n"
            "核心字段：title, target_emotion, opening_hook, main_payoff, "
            "content_summary, scene_beats。\n"
            "content_summary 写清楚本章做什么（起因→发展→高潮→收尾）。\n"
            "scene_beats 按场景切分，每个 beat 写 description + function_tag。\n"
            "字数、beat 数量自由，不设硬性限制。",
        ]

        # Varying context
        parts.append(f"\n=== TASK ===\n规划第 {chapter_index} 章\n项目ID: {project_id}")

        if task_description:
            parts.append(f"\n任务描述: {task_description}")

        if character_states:
            parts.append(f"\n=== CHARACTERS (only plan for those listed; others have NOT appeared yet and MUST NOT be included) ===\n{character_states}")

        if volume_plan:
            parts.append(f"\n卷计划:\n{volume_plan.to_dict() if hasattr(volume_plan, 'to_dict') else volume_plan}")

        # ═══ 上文：上一章结尾，供规划参考 ═══
        hook_parts = []
        if prev_chapter_ending:
            hook_parts.append(f"【上一章结尾】\n{prev_chapter_ending}")
        if prev_ending_design:
            ed = prev_ending_design
            if hasattr(ed, 'to_dict'):
                ed = ed.to_dict()
            hook_parts.append(f"【上一章钩子】\n{json.dumps(ed, ensure_ascii=False, default=str)}")
        if hook_parts:
            parts.append(f"\n=== 上文参考 ===\n" + "\n\n".join(hook_parts))

        # ═══ 正文上文 — 已写章节的实际内容，非大纲 ═══
        if completed_text_context:
            parts.append(f"\n=== 已完成章节正文摘要（由此判断情节走向和角色状态） ===\n{completed_text_context}")

        chapter_summaries = []
        if ledger_items:
            for item in ledger_items:
                if item.section == "chapter_summary" and item.content:
                    chapter_summaries.append(f"- {item.entity}: {item.content}")
        if chapter_summaries:
            parts.append(f"\n=== PREVIOUS CHAPTERS (narrative summaries) ===\n" + "\n".join(chapter_summaries))
        elif completed_chapters:
            summary = []
            for p in completed_chapters[-2:]:
                d = p if isinstance(p, dict) else p.to_dict()
                summary.append(f"- ch{d.get('chapter_index','?')}: {d.get('title','')} ({d.get('target_emotion','')})")
            parts.append(f"\n已完成章节:\n" + "\n".join(summary))

        if ledger_items:
            recent = sorted(
                [i for i in ledger_items if i.section != "chapter_summary"],
                key=lambda i: i.updated_at or "", reverse=True
            )[:10]
            if recent:
                items_text = "\n".join(f"- [{i.section}] {i.entity}: {i.content[:150]}" for i in recent)
                parts.append(f"\n=== CONTINUITY FACTS ===\n{items_text}")

        return _get_architect_prompt(self._architect_prompt_name), "\n".join(parts)
