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
        world: list[str] | None = None,
        history: str = "",
        scene: str = "",
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "profile_name": profile.name,
            "narrative": profile.narrative,
            "agent_contract": profile.agent_contracts.get(role, {}),
        }
        if role != "writer":
            result["world"] = list(world or [])
            result["history"] = history
            result["scene"] = scene
        return result
