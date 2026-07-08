"""NovelArchitectAdapter — Architect LLM adapter for novel mode.

Uses DeepSeekAdapter with thinking=high for chapter planning.
"""

from __future__ import annotations

from typing import Any

from ..contracts.novel_chapter import ChapterPlan, BeatDetail

# Thinking configuration for structural planning
_THINKING_HIGH = {"thinking": {"type": "enabled", "reasoning_effort": "high"}}

# Architect system prompt — loaded from prompts/architect.md
from .prompt_loader import load_prompt

def _get_architect_prompt() -> str:
    return load_prompt("architect")


class NovelArchitectAdapter:
    """Architect LLM adapter for novel mode."""

    def __init__(self, registry, model: str = "deepseek-v4-pro"):
        self._registry = registry
        self._model = model

    def plan_chapter(
        self,
        project_id: str,
        chapter_index: int,
        volume_plan: Any,
        completed_chapters: list,
        ledger_items: list,
        character_states: dict,
        task_description: str = "",
    ) -> ChapterPlan:
        """Generate a chapter plan."""
        system_prompt, user_prompt = self._build_prompt(
            project_id, chapter_index, volume_plan,
            completed_chapters, ledger_items, character_states,
            task_description,
        )
        # Call LLM and parse JSON response
        from .novel_llm_factory import NovelLLMFactory
        import json
        factory = NovelLLMFactory.get_instance()
        adapter = factory.get_adapter("architect")
        thinking = factory.get_thinking_config("architect")
        model = factory.get_model("architect")
        max_tokens = factory.get_max_tokens("architect")

        try:
            text, receipt = adapter.generate_text(
                user_prompt,
                max_tokens=max_tokens,
                provider_role="novel_architect",
                model=model,
                extra_body=thinking,
                system_prompt=system_prompt,
            )
        except Exception:
            text = ""

        # Parse JSON response robustly (tolerate ```json fences, leading prose).
        import json
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
            target_chars=plan.target_chars or 3000,
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
        return plan

    @staticmethod
    def _extract_json_object(text: str) -> str | None:
        """Best-effort extract the first balanced top-level JSON object from text.

        Handles: ```json fences, leading/trailing prose, nested braces.
        """
        if not text:
            return None
        t = text.strip()

        # 1. Strip markdown code fences (```json ... ``` or ``` ... ```)
        if t.startswith("```"):
            first_newline = t.find("\n")
            if first_newline != -1:
                t = t[first_newline + 1:]
            # Remove trailing fence (may have whitespace/newline before ```)
            last_fence = t.rfind("```")
            if last_fence != -1:
                t = t[:last_fence]
            t = t.strip()

        # 2. Find the first { and extract balanced JSON object
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
                    # 3. Validate it's actually parseable JSON
                    import json
                    try:
                        json.loads(candidate)
                        return candidate
                    except (json.JSONDecodeError, ValueError):
                        # Malformed JSON (e.g. unescaped newlines in strings).
                        # Try to salvage by escaping bare newlines inside strings.
                        repaired = candidate.replace("\n", "\\n").replace("\r", "\\r")
                        try:
                            json.loads(repaired)
                            return repaired
                        except (json.JSONDecodeError, ValueError):
                            return None
        # 4. No closing brace found — JSON truncated. Try to close it.
        # Find the last } after start and attempt to close open braces.
        remaining = t[start:]
        # Count open vs close braces
        open_count = remaining.count("{")
        close_count = remaining.count("}")
        if open_count > close_count:
            # Try appending missing closing braces
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
        self, project_id, chapter_index, volume_plan,
        completed_chapters, ledger_items, character_states,
        task_description,
    ) -> tuple[str, str]:
        """Returns (system_prompt, user_prompt).

        Optimized for DeepSeek prefix caching: stable rules first.
        """
        # Stable prefix — cacheable
        parts = [
            "=== OUTPUT FORMAT ===\n"
            "严格的 JSON 输出，符合 ChapterPlan schema。\n"
            "包含：chapter_id, project_id, chapter_index, title, target_chars, "
            "chapter_position, target_emotion, opening_hook, main_payoff, "
            "content_summary(五段式), plot_arrangement(多线), "
            "character_appearance(出场顺序), scene_beats(beat预算), "
            "ending_design(钩子), cost_and_reward。\n"
            "所有字段必须有实质内容，不允许空字符串或空数组。",
        ]

        # Varying context
        parts.append(f"\n=== TASK ===\n规划第 {chapter_index} 章\n项目ID: {project_id}")

        if task_description:
            parts.append(f"\n任务描述: {task_description}")

        if character_states:
            parts.append(f"\n角色状态:\n{character_states}")

        if volume_plan:
            parts.append(f"\n卷计划:\n{volume_plan.to_dict() if hasattr(volume_plan, 'to_dict') else volume_plan}")

        if completed_chapters:
            summary = []
            for p in completed_chapters[-2:]:
                d = p if isinstance(p, dict) else p.to_dict()
                summary.append(f"- ch{d.get('chapter_index','?')}: {d.get('title','')} ({d.get('target_emotion','')})")
            parts.append(f"\n已完成章节:\n" + "\n".join(summary))

        if ledger_items:
            recent = sorted(ledger_items, key=lambda i: i.updated_at or "", reverse=True)[:8]
            items_text = "\n".join(f"- [{i.section}] {i.entity}: {i.content[:150]}" for i in recent)
            parts.append(f"\n连续性账本(最近):\n{items_text}")

        return _get_architect_prompt(), "\n".join(parts)
