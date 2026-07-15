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
        narrative={},
        world={},
        history={},
        scene={},
        agent_contracts={},
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
