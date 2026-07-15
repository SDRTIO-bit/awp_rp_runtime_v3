"""Compile validated Novel-only profiles into bounded role context."""

from __future__ import annotations

from typing import Any

from ..contracts.novel_profile import NovelWritingProfile


class NovelProfileCompiler:
    """Provides only the profile layers consumed by the requested novel role."""

    def compile_for(
        self,
        role: str,
        profile: NovelWritingProfile,
        *,
        world_rules: list[str],
        history: str,
        scene: str,
        character_context: dict[str, object],
    ) -> dict[str, object]:
        result: dict[str, object] = {
            "profile_name": profile.name,
            "narrative": profile.narrative,
            "agent_contract": profile.agent_contracts.get(role, {}),
        }
        if role != "writer":
            result["world_rules"] = list(world_rules)
            result["history"] = history
            result["scene"] = scene
            result["character_context"] = character_context
        return result
