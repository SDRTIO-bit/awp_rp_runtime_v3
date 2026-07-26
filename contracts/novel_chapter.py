"""ChapterPlan, SceneBeat, ContentSummary, PlotArrangement, CharacterAppearance, BeatDetail, EndingDesign.

schemaId: awp.novel.chapter-plan.v1
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

SCHEMA_ID = "awp.novel.chapter-plan.v1"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ContentSummary:
    """内容概括五段式。"""
    cause: str = ""          # 起因
    development: str = ""    # 发展
    turning_point: str = ""  # 转折
    climax: str = ""         # 高潮
    ending: str = ""         # 结尾

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause": self.cause,
            "development": self.development,
            "turning_point": self.turning_point,
            "climax": self.climax,
            "ending": self.ending,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContentSummary:
        data = data if isinstance(data, dict) else {}
        return cls(
            cause=str(data.get("cause", "") or ""),
            development=str(data.get("development", "") or ""),
            turning_point=str(data.get("turning_point", "") or ""),
            climax=str(data.get("climax", "") or ""),
            ending=str(data.get("ending", "") or ""),
        )


@dataclass(frozen=True)
class PlotArrangement:
    """情节安排（多线）。"""
    main_line: str = ""       # 主线推进
    sub_line: str = ""        # 辅线推进
    event_line: str = ""      # 事件线/任务线
    emotion_line: str = ""    # 感情线/关系线
    logic_line: str = ""      # 逻辑线：原因→行动→结果→后果

    def to_dict(self) -> dict[str, Any]:
        return {
            "main_line": self.main_line,
            "sub_line": self.sub_line,
            "event_line": self.event_line,
            "emotion_line": self.emotion_line,
            "logic_line": self.logic_line,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlotArrangement:
        data = data if isinstance(data, dict) else {}
        return cls(
            main_line=str(data.get("main_line", "") or ""),
            sub_line=str(data.get("sub_line", "") or ""),
            event_line=str(data.get("event_line", "") or ""),
            emotion_line=str(data.get("emotion_line", "") or ""),
            logic_line=str(data.get("logic_line", "") or ""),
        )


@dataclass(frozen=True)
class CharacterAppearance:
    """人物关系和出场顺序。"""
    appearance_order: tuple[str, ...] = ()
    relationship_changes: tuple[str, ...] = ()
    information_gap: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "appearance_order": list(self.appearance_order),
            "relationship_changes": list(self.relationship_changes),
            "information_gap": self.information_gap,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CharacterAppearance:
        data = data if isinstance(data, dict) else {}
        ao = data.get("appearance_order", [])
        rc = data.get("relationship_changes", [])
        # 容错 list/str
        ao = tuple(ao) if isinstance(ao, (list, tuple)) else ()
        rc = tuple(rc) if isinstance(rc, (list, tuple)) else ()
        return cls(
            appearance_order=ao,
            relationship_changes=rc,
            information_gap=str(data.get("information_gap", "") or ""),
        )


@dataclass(frozen=True)
class BeatDetail:
    """情节点细化（对齐 oh-story 的 beat 预算）。"""
    beat_id: str = ""
    description: str = ""        # 谁做了什么
    function_tag: str = ""       # 功能标签：铺垫/高潮/爽点/打脸/人物塑造/设定
    density: str = "normal"      # dense / normal / sparse
    budget_chars: int = 0        # 字数预算

    def to_dict(self) -> dict[str, Any]:
        return {
            "beat_id": self.beat_id,
            "description": self.description,
            "function_tag": self.function_tag,
            "density": self.density,
            "budget_chars": self.budget_chars,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeatDetail:
        if not isinstance(data, dict):
            # LLM 偶尔把单个 beat 回成纯字符串描述
            if isinstance(data, str):
                return cls(description=data, density="normal", budget_chars=300)
            return cls()
        try:
            budget = int(data.get("budget_chars", 0) or 0)
        except (TypeError, ValueError):
            budget = 0
        return cls(
            beat_id=str(data.get("beat_id", "") or ""),
            description=str(data.get("description", "") or ""),
            function_tag=str(data.get("function_tag", "") or ""),
            density=str(data.get("density", "normal") or "normal"),
            budget_chars=budget,
        )


def normalize_scene_beats(
    beats: tuple[BeatDetail, ...] | list[BeatDetail],
    *,
    chapter_index: int,
    target_chars: int,
) -> tuple[BeatDetail, ...]:
    """Fill metadata required by the beat-by-beat writer for legacy/LLM plans."""
    items = tuple(beats)
    if not items:
        return items

    fallback_budget = max(1, target_chars // len(items))
    remainder = max(0, target_chars - fallback_budget * len(items))
    seen_ids: set[str] = set()
    normalized: list[BeatDetail] = []
    for index, beat in enumerate(items, start=1):
        beat_id = beat.beat_id.strip()
        if not beat_id or beat_id in seen_ids:
            beat_id = f"ch{chapter_index}-b{index}"
        seen_ids.add(beat_id)

        budget = beat.budget_chars
        if budget <= 0:
            budget = fallback_budget + (remainder if index == len(items) else 0)

        normalized.append(
            BeatDetail(
                beat_id=beat_id,
                description=beat.description,
                function_tag=beat.function_tag,
                density=beat.density,
                budget_chars=budget,
            )
        )
    return tuple(normalized)


@dataclass(frozen=True)
class EndingDesign:
    """结尾设定和钩子。"""
    closing_state: str = ""
    open_questions: tuple[str, ...] = ()
    next_chapter_push: str = ""
    hook_type: str = ""
    hook_detail: str = ""
    hook_strength: str = "medium"  # strong / medium / weak

    def to_dict(self) -> dict[str, Any]:
        return {
            "closing_state": self.closing_state,
            "open_questions": list(self.open_questions),
            "next_chapter_push": self.next_chapter_push,
            "hook_type": self.hook_type,
            "hook_detail": self.hook_detail,
            "hook_strength": self.hook_strength,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EndingDesign:
        data = data if isinstance(data, dict) else {}
        oq = data.get("open_questions", [])
        oq = tuple(oq) if isinstance(oq, (list, tuple)) else ()
        return cls(
            closing_state=str(data.get("closing_state", "") or ""),
            open_questions=oq,
            next_chapter_push=str(data.get("next_chapter_push", "") or ""),
            hook_type=str(data.get("hook_type", "") or ""),
            hook_detail=str(data.get("hook_detail", "") or ""),
            hook_strength=str(data.get("hook_strength", "medium") or "medium"),
        )


@dataclass(frozen=True)
class ChapterPlan:
    """A chapter plan with full detail."""
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    chapter_id: str = ""
    project_id: str = ""
    volume_id: str = ""
    chapter_index: int = 0
    title: str = ""
    target_chars: int = 3000
    chapter_position: str = ""   # high_pressure / progression / relationship / setup / cooldown / information
    target_emotion: str = ""
    opening_hook: str = ""
    main_payoff: str = ""

    # 扩展字段（从 oh-story 吸收）
    content_summary: ContentSummary = field(default_factory=ContentSummary)
    plot_arrangement: PlotArrangement = field(default_factory=PlotArrangement)
    character_appearance: CharacterAppearance = field(default_factory=CharacterAppearance)
    scene_beats: tuple[BeatDetail, ...] = ()
    ending_design: EndingDesign = field(default_factory=EndingDesign)
    cost_and_reward: str = ""
    author_plan_id: str = ""
    author_plan_revision: int = 0
    author_plan_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "chapter_id": self.chapter_id,
            "project_id": self.project_id,
            "volume_id": self.volume_id,
            "chapter_index": self.chapter_index,
            "title": self.title,
            "target_chars": self.target_chars,
            "chapter_position": self.chapter_position,
            "target_emotion": self.target_emotion,
            "opening_hook": self.opening_hook,
            "main_payoff": self.main_payoff,
            "content_summary": self.content_summary.to_dict(),
            "plot_arrangement": self.plot_arrangement.to_dict(),
            "character_appearance": self.character_appearance.to_dict(),
            "scene_beats": [b.to_dict() for b in self.scene_beats],
            "ending_design": self.ending_design.to_dict(),
            "cost_and_reward": self.cost_and_reward,
            "author_plan_id": self.author_plan_id,
            "author_plan_revision": self.author_plan_revision,
            "author_plan_hash": self.author_plan_hash,
        }

    @staticmethod
    def _stringify_chapter_position(v: Any) -> str:
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            parts = []
            for key in ("type", "function", "has_strong_hook", "has_payoff"):
                val = v.get(key, None)
                if val is True:
                    parts.append(key)
                elif val is False:
                    pass
                elif val and isinstance(val, str):
                    parts.append(val)
            return " | ".join(parts) if parts else json.dumps(v, ensure_ascii=False)
        return str(v) if v else ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChapterPlan:
        import json as _json
        import re

        data = data if isinstance(data, dict) else {}

        def _as_dict(v) -> dict:
            """容错：LLM 偶尔把嵌套对象回成 list/str/None。统一安全转 dict."""
            if isinstance(v, dict):
                return v
            if v is None:
                return {}
            # list of [k,v] pairs or list of strings → 尽量拼成 dict
            if isinstance(v, list):
                out: dict[str, Any] = {}
                for item in v:
                    if isinstance(item, dict):
                        out.update(item)
                    elif isinstance(item, (list, tuple)) and len(item) >= 2:
                        out[str(item[0])] = item[1]
                    else:
                        # 单字符串列表：折回一个 appearance_order/relationship_changes
                        pass
                # 若 list 全是字符串，按"出场顺序"语义塞进对应键
                if v and all(isinstance(x, str) for x in v) and not out:
                    out = {"appearance_order": v}
                return out
            if isinstance(v, str):
                return {}
            return {}

        def _as_target_chars(value: Any) -> int:
            """Accept common LLM forms such as ``2200-2500`` for a target."""
            try:
                return int(value or 3000)
            except (TypeError, ValueError):
                numbers = [int(item) for item in re.findall(r"\d+", str(value or ""))]
                if len(numbers) >= 2:
                    return sum(numbers[:2]) // 2
                if numbers:
                    return numbers[0]
                return 3000

        content_summary_raw = _as_dict(data.get("content_summary"))
        plot_arrangement_raw = _as_dict(data.get("plot_arrangement"))
        # character_appearance 经常被 LLM 误回成 list（如 ["林舟","白晚晚"]）
        character_appearance_raw = _as_dict(data.get("character_appearance"))
        ending_design_raw = _as_dict(data.get("ending_design"))

        from collections.abc import Iterable as _Iterable
        sb_raw = data.get("scene_beats", [])
        if not isinstance(sb_raw, (list, tuple)):
            sb_raw = []

        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            chapter_id=data.get("chapter_id", ""),
            project_id=data.get("project_id", ""),
            volume_id=data.get("volume_id", ""),
            chapter_index=int(data.get("chapter_index", 0) or 0),
            title=data.get("title", ""),
            target_chars=_as_target_chars(data.get("target_chars", 3000)),
            chapter_position=cls._stringify_chapter_position(data.get("chapter_position", "")),
            target_emotion=data.get("target_emotion", ""),
            opening_hook=data.get("opening_hook", ""),
            main_payoff=data.get("main_payoff", ""),
            content_summary=ContentSummary.from_dict(content_summary_raw),
            plot_arrangement=PlotArrangement.from_dict(plot_arrangement_raw),
            character_appearance=CharacterAppearance.from_dict(character_appearance_raw),
            scene_beats=tuple(BeatDetail.from_dict(b) for b in sb_raw),
            ending_design=EndingDesign.from_dict(ending_design_raw),
            cost_and_reward=data.get("cost_and_reward", "") or "",
            author_plan_id=str(data.get("author_plan_id", "") or ""),
            author_plan_revision=int(data.get("author_plan_revision", 0) or 0),
            author_plan_hash=str(data.get("author_plan_hash", "") or ""),
        )
