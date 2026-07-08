"""NovelDirectorAdapter — Director LLM adapter for novel mode v3.

职责单一：把 Architect 的 3 个 beat 展开成 McKee 框架细纲。
角色锚点/时间锚点从已有数据直接拼，不经过 LLM。
"""

from __future__ import annotations

from typing import Any

from ..contracts.novel_director_guidance import DirectorGuidance, BeatGuidance
from .prompt_loader import load_prompt

def _get_director_prompt() -> str:
    return load_prompt("director")


class NovelDirectorAdapter:
    """Director v3: 只输出 beat 细纲。"""

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
        """Generate beat details for a chapter."""
        # 从已有数据拼锚点，不经过 LLM
        character_anchor = self._build_character_anchor(character_states)
        timeline_anchor = f"第{chapter_plan.chapter_index}章"

        # 调 LLM 只生成 beat_details
        beat_details = self._call_llm_for_beats(
            chapter_plan, character_anchor, timeline_anchor,
            previous_chapter_ending, ledger_items,
        )

        return DirectorGuidance(
            guidance_id=f"guid-ch{chapter_plan.chapter_index}",
            character_anchor=character_anchor,
            timeline_anchor=timeline_anchor,
            beat_details=tuple(beat_details),
        )

    def _build_character_anchor(self, character_states: dict) -> str:
        """从角色状态直接拼锚点，不经过 LLM。"""
        parts = []
        for name, state in character_states.items():
            if isinstance(state, dict):
                age = state.get("age", "")
                gender = state.get("gender", "")
                identity = state.get("identity", "")
                ability = state.get("ability", "")
                desc = f"{name}: "
                if age:
                    desc += f"{age}岁"
                if gender:
                    desc += gender
                if identity:
                    desc += f", {identity}"
                if ability:
                    desc += f", {ability}"
                parts.append(desc)
            else:
                parts.append(f"{name}: {state}")
        return " | ".join(parts) if parts else ""

    def _call_llm_for_beats(
        self, chapter_plan, character_anchor, timeline_anchor,
        previous_chapter_ending, ledger_items,
    ) -> list[BeatGuidance]:
        """调 LLM 生成 beat 细纲。"""
        from .novel_llm_factory import NovelLLMFactory
        import json

        factory = NovelLLMFactory.get_instance()
        adapter = factory.get_adapter("director")
        thinking = factory.get_thinking_config("director")
        model = factory.get_model("director")
        max_tokens = factory.get_max_tokens("director")

        # 构造 user prompt
        parts = [f"=== 角色锚点 ===\n{character_anchor}"]
        parts.append(f"=== 时间锚点 ===\n{timeline_anchor}")

        if previous_chapter_ending:
            parts.append(f"=== 前一章结尾 ===\n{previous_chapter_ending[-500:]}")

        if ledger_items:
            items_text = "\n".join(f"- [{i.section}] {i.entity}: {i.content}" for i in ledger_items[:15])
            parts.append(f"=== 连续性账本 ===\n{items_text}")

        parts.append(f"=== 章节计划 ===\n{json.dumps(chapter_plan.to_dict(), ensure_ascii=False)}")

        parts.append(f"\n=== 任务 ===\n把上面章节计划里的 scene_beats 展开成细纲。每个 beat 一个。共 {len(chapter_plan.scene_beats)} 个。")

        user_prompt = "\n\n".join(parts)

        try:
            text, receipt = adapter.generate_text(
                user_prompt,
                max_tokens=max_tokens,
                provider_role="novel_director",
                model=model,
                extra_body=thinking,
                system_prompt=_get_director_prompt(),
            )
        except Exception:
            text = ""

        # 解析 JSON
        extracted = self._extract_json_object(text)
        if extracted:
            try:
                data = json.loads(extracted)
                beats = data.get("beat_details", [])
                if beats:
                    return [BeatGuidance.from_dict(b) for b in beats if isinstance(b, dict)]
            except (json.JSONDecodeError, TypeError):
                pass

        # Fallback: 用 Architect 的原始 beat 描述
        return [
            BeatGuidance(beat_id=b.beat_id, content_outline=b.description)
            for b in chapter_plan.scene_beats
        ]

    @staticmethod
    def _extract_json_object(text: str) -> str | None:
        """Best-effort JSON extraction with fence stripping and truncation repair."""
        if not text:
            return None
        t = text.strip()
        if t.startswith("```"):
            first_newline = t.find("\n")
            if first_newline != -1:
                t = t[first_newline + 1:]
            last_fence = t.rfind("```")
            if last_fence != -1:
                t = t[:last_fence]
            t = t.strip()
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
                        repaired = candidate.replace("\n", "\\n")
                        try:
                            json.loads(repaired)
                            return repaired
                        except (json.JSONDecodeError, ValueError):
                            return None
        # Truncated JSON
        remaining = t[start:]
        open_count = remaining.count("{")
        close_count = remaining.count("}")
        if open_count > close_count:
            import json
            try:
                json.loads(remaining + "}" * (open_count - close_count))
                return remaining + "}" * (open_count - close_count)
            except (json.JSONDecodeError, ValueError):
                pass
        return None
