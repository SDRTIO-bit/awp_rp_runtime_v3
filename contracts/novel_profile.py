"""Configuration contract for autonomous novel writing."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

SCHEMA_ID = "awp.novel.writing-profile.v1"
SCHEMA_VERSION = 1
PROFILE_CONFIG_KEY = "autonomous_profile"


class NovelProfileError(ValueError):
    """Raised when a project is not explicitly configured for novel autonomy."""


class NovelWritingProfile(BaseModel):
    """Explicit, immutable configuration for the autonomous novel pipeline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_id: str = SCHEMA_ID
    schema_version: int = SCHEMA_VERSION
    mode: Literal["novel"]
    name: str
    narrative: dict[str, Any]
    world: dict[str, Any]
    history: dict[str, Any]
    scene: dict[str, Any]
    agent_contracts: dict[str, Any]


def default_autonomous_profile() -> NovelWritingProfile:
    """Return the explicit profile written for newly initialized projects."""

    return NovelWritingProfile(
        mode="novel",
        name="default-novel-autonomy",
        narrative={
            "language": "zh-CN",
            "tone": "克制、有留白",
            "style": "第三人称有限视角，聚焦主角的感官与情绪",
            "objective": "200字以内的小说目标：写一段主角在压力下做出选择、并承担可见后果的现代都市悬疑场景。",
        },
        world={
            "rules": [
                "案件调查必须遵守现实刑侦逻辑",
                "关键物证在本章必须被角色实际触碰或观察",
                "NPC 动机独立于主角意志",
            ],
            "budget": "世界观约束不超过 5 条",
        },
        history={
            "facts": [
                "主角在上一章收到匿名威胁短信",
                "警局内部有人泄露案卷照片",
                "关键证人已经在第三章失踪",
            ],
            "constraints": "历史事实必须被本章角色行为或对话提及，不能只作为旁白",
        },
        scene={
            "budget": "场景约束不超过 5 条",
            "must_include": ["一个只出现一次但有象征意义的环境细节", "一段不解释动机的 NPC 动作"],
            "constraints": [
                "本章必须在雨夜进行",
                "主要冲突发生在废弃仓库二楼",
            ],
        },
        agent_contracts={
            "architect": {
                "role": "architect",
                "instruction": "基于 Profile 的叙事目标与世界规则，生成可执行的章节计划。",
            },
            "npc_planner": {
                "role": "npc_planner",
                "response_format": "npc_agenda_json",
                "instruction": "为每个候选 NPC 生成严格 NpcAgenda，只返回合法 JSON 数组。",
            },
            "director": {
                "role": "director",
                "instruction": "从候选议程中至多选择 2 项并转成 VisibleConsequence，不泄露私密目标。",
            },
            "writer": {
                "role": "writer",
                "instruction": "只使用可见后果与节拍指令生成正文；禁止引入私密目标、事实 ID、资源或成本。",
            },
        },
    )


def load_autonomous_profile(config: dict[str, Any]) -> NovelWritingProfile:
    """Load the dedicated autonomy profile from a project's runtime config."""

    if not isinstance(config, dict):
        raise NovelProfileError("autonomous profile config must be a mapping")
    profile_data = config.get(PROFILE_CONFIG_KEY)
    if profile_data is None:
        raise NovelProfileError("autonomous profile is missing; run profile-init explicitly")
    try:
        return NovelWritingProfile.model_validate(profile_data)
    except ValidationError as exc:
        if isinstance(profile_data, dict) and profile_data.get("mode") != "novel":
            raise NovelProfileError("autonomous profile mode must be 'novel'") from exc
        raise NovelProfileError(f"invalid autonomous profile: {exc}") from exc
