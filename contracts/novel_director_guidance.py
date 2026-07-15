"""DirectorGuidance, BeatGuidance, OutlineEnhancement, ForeshadowingAction, SubplotStatus.

schemaId: awp.novel.director-guidance.v2

v2: 融合 McKee 框架，将旧字段（chapter_direction/emotional_arc/pacing_strategy/
key_scenes/dialogue_tone/reader_expectation_plan/character_arc_beats）拆入 beat_details。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .novel_npc_agenda import SelectedNpcAction, VisibleConsequence

SCHEMA_ID = "awp.novel.director-guidance.v2"
SCHEMA_VERSION = 2


@dataclass(frozen=True)
class BeatGuidance:
    """单个 beat 的细纲（McKee 框架驱动）。"""
    beat_id: str = ""
    content_outline: str = ""      # 具体事件：谁做了什么，发生了什么
    gap: str = ""                  # McKee gap：期望 vs 结果的落差
    complication: str = ""         # 比上一个 beat 复杂在哪（递进复杂化）
    pressure_point: str = ""       # 角色面对的压力/两难选择
    dialogue_keys: tuple[str, ...] = ()  # 关键对白要点（含潜台词标注）
    info_release: str = ""         # 读者在这个 beat 新知道什么
    emotion_shift: str = ""        # 情绪翻转（如"压抑→怀疑"）
    info_type: str = ""            # 信息传递方式：对话/行为/叙述/内心推断
    hook_execution: str = ""       # 钩子怎么落地（悬念/情绪/反转/信息差）

    def to_dict(self) -> dict[str, Any]:
        return {
            "beat_id": self.beat_id,
            "content_outline": self.content_outline,
            "gap": self.gap,
            "complication": self.complication,
            "pressure_point": self.pressure_point,
            "dialogue_keys": list(self.dialogue_keys),
            "info_release": self.info_release,
            "emotion_shift": self.emotion_shift,
            "info_type": self.info_type,
            "hook_execution": self.hook_execution,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeatGuidance:
        data = data if isinstance(data, dict) else {}
        dk = data.get("dialogue_keys", [])
        dk = tuple(dk) if isinstance(dk, (list, tuple)) else ()
        return cls(
            beat_id=str(data.get("beat_id", "") or ""),
            content_outline=str(data.get("content_outline", "") or ""),
            gap=str(data.get("gap", "") or ""),
            complication=str(data.get("complication", "") or ""),
            pressure_point=str(data.get("pressure_point", "") or ""),
            dialogue_keys=dk,
            info_release=str(data.get("info_release", "") or ""),
            emotion_shift=str(data.get("emotion_shift", "") or ""),
            info_type=str(data.get("info_type", "") or ""),
            hook_execution=str(data.get("hook_execution", "") or ""),
        )


@dataclass(frozen=True)
class OutlineEnhancement:
    """大纲优化建议。"""
    target: str = ""             # "volume" / "chapter" / "scene_beat"
    target_id: str = ""
    enhancement_type: str = ""   # "add_beat" / "modify_beat" / "add_subplot" / "adjust_pacing" / "add_foreshadowing"
    description: str = ""
    reasoning: str = ""
    priority: str = "optional"   # "must_have" / "nice_to_have" / "optional"

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "target_id": self.target_id,
            "enhancement_type": self.enhancement_type,
            "description": self.description,
            "reasoning": self.reasoning,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutlineEnhancement:
        return cls(
            target=data.get("target", ""),
            target_id=data.get("target_id", ""),
            enhancement_type=data.get("enhancement_type", ""),
            description=data.get("description", ""),
            reasoning=data.get("reasoning", ""),
            priority=data.get("priority", "optional"),
        )


@dataclass(frozen=True)
class ForeshadowingAction:
    """伏笔调度动作。"""
    foreshadowing_id: str = ""
    action: str = ""             # "plant" / "advance" / "payoff" / "red_herring"
    scene_context: str = ""
    subtlety: str = "implicit"   # "explicit" / "implicit" / "background"

    def to_dict(self) -> dict[str, Any]:
        return {
            "foreshadowing_id": self.foreshadowing_id,
            "action": self.action,
            "scene_context": self.scene_context,
            "subtlety": self.subtlety,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ForeshadowingAction:
        return cls(
            foreshadowing_id=data.get("foreshadowing_id", ""),
            action=data.get("action", ""),
            scene_context=data.get("scene_context", ""),
            subtlety=data.get("subtlety", "implicit"),
        )


@dataclass(frozen=True)
class SubplotStatus:
    """支线进度。"""
    subplot_name: str = ""
    status: str = "dormant"      # "dormant" / "advancing" / "climaxing" / "resolving" / "resolved"
    chapters_since_last_update: int = 0
    urgency: str = "can_wait"    # "needs_attention" / "on_track" / "can_wait"

    def to_dict(self) -> dict[str, Any]:
        return {
            "subplot_name": self.subplot_name,
            "status": self.status,
            "chapters_since_last_update": self.chapters_since_last_update,
            "urgency": self.urgency,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubplotStatus:
        return cls(
            subplot_name=data.get("subplot_name", ""),
            status=data.get("status", "dormant"),
            chapters_since_last_update=data.get("chapters_since_last_update", 0),
            urgency=data.get("urgency", "can_wait"),
        )


@dataclass(frozen=True)
class DirectorGuidance:
    """Director 的输出 v2：事实锚点 + beat 细纲 + 全局辅助。

    旧字段（chapter_direction/emotional_arc/pacing_strategy/key_scenes/
    dialogue_tone/reader_expectation_plan/character_arc_beats）已融合入 beat_details。
    """
    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION

    guidance_id: str = ""

    # 事实锚点（Writer 必须遵守，不可修改）
    character_anchor: str = ""    # "林知夏: 28岁女, 自由插画师, 失眠三年 | 袁护士: ~50岁, 护士"
    timeline_anchor: str = ""     # "第3章, 搬入第2天, Day2 凌晨→清晨"

    # beat 细纲（替代旧的 chapter_direction/emotional_arc/pacing_strategy/key_scenes/dialogue_tone/reader_expectation_plan/character_arc_beats）
    beat_details: tuple[BeatGuidance, ...] = ()

    # 全局辅助
    outline_enhancements: tuple[OutlineEnhancement, ...] = ()
    foreshadowing_schedule: tuple[ForeshadowingAction, ...] = ()
    subplot_status: tuple[SubplotStatus, ...] = ()
    visible_consequences: tuple[VisibleConsequence, ...] = ()
    selected_npc_actions: tuple[SelectedNpcAction, ...] = ()
    risk_flags: tuple[str, ...] = ()
    opportunities: tuple[str, ...] = ()
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        # ``selected_npc_actions`` and ``reasoning`` are Director-internal:
        # they never belong on a Writer-bound packet. Omit them when empty so
        # the serialized guidance never carries a private-selection key.
        result: dict[str, Any] = {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "guidance_id": self.guidance_id,
            "character_anchor": self.character_anchor,
            "timeline_anchor": self.timeline_anchor,
            "beat_details": [b.to_dict() for b in self.beat_details],
            "outline_enhancements": [e.to_dict() for e in self.outline_enhancements],
            "foreshadowing_schedule": [f.to_dict() for f in self.foreshadowing_schedule],
            "subplot_status": [s.to_dict() for s in self.subplot_status],
            "visible_consequences": [c.model_dump(mode="json") for c in self.visible_consequences],
        }
        if self.selected_npc_actions:
            result["selected_npc_actions"] = [
                a.model_dump(mode="json") for a in self.selected_npc_actions
            ]
        result["risk_flags"] = list(self.risk_flags)
        result["opportunities"] = list(self.opportunities)
        if self.reasoning:
            result["reasoning"] = self.reasoning
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DirectorGuidance:
        data = data if isinstance(data, dict) else {}
        return cls(
            schema_id=data.get("schema_id", SCHEMA_ID),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            guidance_id=data.get("guidance_id", ""),
            character_anchor=str(data.get("character_anchor", "") or ""),
            timeline_anchor=str(data.get("timeline_anchor", "") or ""),
            beat_details=tuple(BeatGuidance.from_dict(b) for b in data.get("beat_details", []) if isinstance(b, dict)),
            outline_enhancements=tuple(OutlineEnhancement.from_dict(e) for e in data.get("outline_enhancements", []) if isinstance(e, dict)),
            foreshadowing_schedule=tuple(ForeshadowingAction.from_dict(f) for f in data.get("foreshadowing_schedule", []) if isinstance(f, dict)),
            subplot_status=tuple(SubplotStatus.from_dict(s) for s in data.get("subplot_status", []) if isinstance(s, dict)),
            visible_consequences=tuple(
                VisibleConsequence.model_validate(c)
                for c in data.get("visible_consequences", [])
                if isinstance(c, dict)
            ),
            selected_npc_actions=tuple(
                SelectedNpcAction.model_validate(a)
                for a in data.get("selected_npc_actions", [])
                if isinstance(a, dict)
            ),
            risk_flags=tuple(data.get("risk_flags", [])),
            opportunities=tuple(data.get("opportunities", [])),
            reasoning=data.get("reasoning", ""),
        )
