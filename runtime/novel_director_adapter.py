"""NovelDirectorAdapter — Director LLM adapter for novel mode v3.

职责单一：把 Architect 的 3 个 beat 展开成 McKee 框架细纲。
角色锚点/时间锚点从已有数据直接拼，不经过 LLM。
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from ..contracts.novel_director_guidance import (
    DirectorGuidance, BeatGuidance, ForeshadowingAction, SubplotStatus, OutlineEnhancement,
)
from ..contracts.novel_npc_agenda import NpcAgenda, SelectedNpcAction
from ..contracts.novel_pi_role_protocol import NovelPiRoleTask
from .prompt_loader import load_prompt
from .novel_role_context import get_novel_role_context
from .novel_role_runtime import get_novel_role_runtime

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
        *,
        candidate_agendas: tuple[NpcAgenda, ...] = (),
    ) -> DirectorGuidance:
        """Generate beat details for a chapter and select NPC actions.

        ``candidate_agendas`` are the private agendas the Pi planner proposed
        for this chapter. Only the Writer-safe ``visible_consequence`` of each
        agenda is surfaced to the LLM; the Director returns
        ``selected_agenda_ids`` which are validated through
        ``select_npc_actions`` before any action reaches the Writer packet.
        """
        # 从已有数据拼锚点，不经过 LLM
        character_anchor = self._build_character_anchor(character_states)
        timeline_anchor = f"第{chapter_plan.chapter_index}章"

        # 调 LLM 只生成 beat_details + 全局优化
        result = self._call_llm_for_beats(
            chapter_plan, character_anchor, timeline_anchor,
            previous_chapter_ending, ledger_items,
            completed_chapters_summary, foreshadowing_list, subplot_status,
            candidate_agendas=candidate_agendas,
        )
        beat_details = result.get("beat_details", [])
        foreshadowing_schedule = result.get("foreshadowing_schedule", [])
        subplot_status = result.get("subplot_status", [])
        outline_enhancements = result.get("outline_enhancements", [])
        risk_flags = result.get("risk_flags", [])
        opportunities = result.get("opportunities", [])

        # Validate the Director's chosen agenda IDs through the deterministic
        # selection rules (at most 2, no same-NPC/thread conflicts). Only the
        # visible consequences of the survivors ever cross to the Writer.
        selected_ids = tuple(result.get("selected_agenda_ids", []) or [])
        selected_actions = self.select_npc_actions(candidate_agendas, selected_ids)

        return DirectorGuidance(
            guidance_id=f"guid-ch{chapter_plan.chapter_index}",
            character_anchor=character_anchor,
            timeline_anchor=timeline_anchor,
            beat_details=tuple(beat_details),
            foreshadowing_schedule=tuple(foreshadowing_schedule),
            subplot_status=tuple(subplot_status),
            outline_enhancements=tuple(outline_enhancements),
            risk_flags=tuple(risk_flags) if isinstance(risk_flags, (list, tuple)) else (),
            opportunities=tuple(opportunities) if isinstance(opportunities, (list, tuple)) else (),
            selected_npc_actions=selected_actions,
            visible_consequences=tuple(
                a.visible_consequence for a in selected_actions
            ),
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
        completed_chapters_summary="",
        foreshadowing_list=None,
        subplot_status=None,
        *,
        candidate_agendas: tuple[NpcAgenda, ...] = (),
    ) -> dict[str, Any]:
        """调 LLM 生成 beat 细纲 + 全局优化。返回完整 JSON 解析结果。

        Autonomous NPC agendas are injected only by their Writer-safe
        ``visible_consequence`` (agenda_id + observable event/clue). Private
        goals, fact ids, resources and risk never cross into the Director LLM.
        """
        # 构造 user prompt
        parts = [f"=== 角色锚点 ===\n{character_anchor}"]
        parts.append(f"=== 时间锚点 ===\n{timeline_anchor}")

        if completed_chapters_summary:
            parts.append(f"=== 已完成章节摘要 ===\n{completed_chapters_summary}")

        if previous_chapter_ending:
            parts.append(f"=== 前一章结尾 ===\n{previous_chapter_ending[-500:]}")

        if ledger_items:
            items_text = "\n".join(f"- [{i.section}] {i.entity}: {i.content}" for i in ledger_items[:15])
            parts.append(f"=== 连续性账本 ===\n{items_text}")

        fl = foreshadowing_list or []
        if fl:
            fl_text = "\n".join(f"- {f.entity}: {f.content}" for f in fl[:10])
            parts.append(f"=== 当前伏笔 ===\n{fl_text}")

        ss = subplot_status or []
        if ss:
            ss_text = "\n".join(f"- {s.entity}: {s.content}" for s in ss[:10])
            parts.append(f"=== 支线状态 ===\n{ss_text}")

        parts.append(f"=== 章节计划 ===\n{json.dumps(chapter_plan.to_dict(), ensure_ascii=False)}")

        # Writer-safe NPC consequence candidates (no private agenda fields).
        if candidate_agendas:
            safe_cands = []
            for agenda in candidate_agendas:
                c = agenda.visible_consequence
                safe_cands.append(
                    f"- agenda_id={agenda.agenda_id}; beat_id={c.beat_id}; "
                    f"observable_event={c.observable_event}; "
                    f"observable_clue={c.observable_clue}; "
                    f"affected={list(c.affected_characters)}"
                )
            parts.append(
                "=== 候选 NPC 可见后果（仅这些可见后果可写入正文）===\n"
                + "\n".join(safe_cands)
            )
            parts.append(
                "在 JSON 中增加 selected_agenda_ids（至多 2 个），其余字段保持不变。"
            )

        parts.append(f"\n=== 任务 ===\n把上面章节计划里的 scene_beats 展开成细纲。每个 beat 一个。共 {len(chapter_plan.scene_beats)} 个。")

        user_prompt = "\n\n".join(parts)

        context = get_novel_role_context()
        role_result = get_novel_role_runtime().run(
            NovelPiRoleTask(
                role="director",
                project_id=context.project_id,
                chapter_index=chapter_plan.chapter_index,
                revision=context.revision,
                phase="director_guidance",
                session_key=f"task:{uuid.uuid4().hex}",
                task_contract=_get_director_prompt(),
                input_payload={
                    "prompt": user_prompt,
                    "response_format": "director_guidance_json",
                },
            ),
            context=context,
        )
        text = role_result.text

        # 解析 JSON
        extracted = self._extract_json_object(text)
        if extracted:
            try:
                data = json.loads(extracted)
                beats = data.get("beat_details", [])
                result: dict[str, Any] = {
                    "beat_details": [],
                    "foreshadowing_schedule": [],
                    "subplot_status": [],
                    "outline_enhancements": [],
                    "risk_flags": data.get("risk_flags", []),
                    "opportunities": data.get("opportunities", []),
                    "selected_agenda_ids": tuple(
                        sid for sid in data.get("selected_agenda_ids", []) if sid
                    ),
                }
                if beats:
                    result["beat_details"] = [
                        BeatGuidance.from_dict(b) for b in beats if isinstance(b, dict)
                    ]
                for fa in data.get("foreshadowing_schedule", []):
                    if isinstance(fa, dict):
                        result["foreshadowing_schedule"].append(ForeshadowingAction.from_dict(fa))
                for ss in data.get("subplot_status", []):
                    if isinstance(ss, dict):
                        result["subplot_status"].append(SubplotStatus.from_dict(ss))
                for oe in data.get("outline_enhancements", []):
                    if isinstance(oe, dict):
                        result["outline_enhancements"].append(OutlineEnhancement.from_dict(oe))
                return result
            except (json.JSONDecodeError, TypeError):
                pass

        # Fallback: 用 Architect 的原始 beat 描述
        return {
            "beat_details": [
                BeatGuidance(beat_id=b.beat_id, content_outline=b.description)
                for b in chapter_plan.scene_beats
            ],
        }

    def select_npc_actions(
        self,
        agendas: tuple[NpcAgenda, ...],
        selected_ids: tuple[str, ...],
    ) -> tuple[SelectedNpcAction, ...]:
        """Return at most two validated, non-conflicting selected NPC actions.

        Rejects unknown agenda IDs, selections over the budget, or actions that
        share the same NPC or thread key (would compete for the same screen
        real estate in a single chapter).
        """
        by_id = {a.agenda_id: a for a in agendas}
        selected: list[SelectedNpcAction] = []
        seen_npcs: set[str] = set()
        seen_threads: set[str] = set()
        for agenda_id in selected_ids[:2]:
            agenda = by_id.get(agenda_id)
            if agenda is None:
                continue
            if agenda.npc in seen_npcs or agenda.thread_key in seen_threads:
                continue
            selected.append(SelectedNpcAction(
                agenda_id=agenda.agenda_id,
                character_name=agenda.npc,
                reasoning=f"推进 {agenda.thread_key} 线",
                visible_consequence=agenda.visible_consequence,
            ))
            seen_npcs.add(agenda.npc)
            seen_threads.add(agenda.thread_key)
        return tuple(selected)

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
