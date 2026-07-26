"""Version and snapshot contracts for project prompt overrides."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PromptRole = Literal[
    "editor",
    "architect",
    "director",
    "writer",
    "npc_planner",
    "continuity_checker",
    "style_cleaner",
    "ledger_curator",
]


class ResolvedPrompt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    role: PromptRole
    content: str = Field(min_length=1)
    source: Literal["system", "project"]
    revision: int = Field(ge=0)
    content_hash: str = Field(min_length=1)


class NovelPromptVersion(ResolvedPrompt):
    created_at: str = Field(min_length=1)


class NovelPromptSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    snapshot_id: str = Field(min_length=1)
    versions: dict[str, str]
    hashes: dict[str, str]
    contents: dict[str, str]
    created_at: str = Field(min_length=1)


__all__ = [
    "NovelPromptSnapshot",
    "NovelPromptVersion",
    "PromptRole",
    "ResolvedPrompt",
]
