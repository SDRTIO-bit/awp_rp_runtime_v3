"""Strict contracts for author-controlled, project-local Pi skills."""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


_SKILL_ID = re.compile(r"[a-z0-9-]{1,64}\Z")
_PROHIBITED = re.compile(
    r"(?:^|\n)\s*(?:tools?|extensions?)\s*:|\b(?:bash|powershell|curl|wget)\b|"
    r"https?://|\b(?:bypass|ignore)\s+(?:author\s+)?approval\b",
    re.IGNORECASE,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectSkillStatus(str, Enum):
    PROPOSED = "proposed"
    SAVED = "saved"
    ENABLED = "enabled"
    DISABLED = "disabled"


def _frontmatter_value(content: str, key: str) -> str:
    if not content.startswith("---\n"):
        return ""
    end = content.find("\n---\n", 4)
    if end < 0:
        return ""
    for line in content[4:end].splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return ""


class ProjectSkillVersion(_StrictModel):
    skill_id: str
    version: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=32 * 1024)
    status: ProjectSkillStatus = ProjectSkillStatus.SAVED
    created_at: str = ""
    source: str = "author"

    @model_validator(mode="after")
    def validate_skill(self) -> "ProjectSkillVersion":
        if not _SKILL_ID.fullmatch(self.skill_id):
            raise ValueError("skill_id must contain only lowercase letters, digits, and hyphens")
        if _frontmatter_value(self.content, "name") != self.skill_id:
            raise ValueError("frontmatter name must exactly match skill_id")
        if not _frontmatter_value(self.content, "description"):
            raise ValueError("frontmatter description is required")
        if _PROHIBITED.search(self.content):
            raise ValueError("project skill requests a prohibited capability")
        return self


class ProjectSkillProposal(_StrictModel):
    proposal_id: str = Field(pattern=r"skill-proposal-[a-z0-9-]{1,64}")
    project_id: str = Field(min_length=1)
    skill: ProjectSkillVersion
    purpose: str = Field(min_length=1, max_length=2_000)
    behavior_impact: str = Field(min_length=1, max_length=2_000)
    proposal_turn: int = Field(default=0, ge=0)
    status: ProjectSkillStatus = ProjectSkillStatus.PROPOSED
    approval_turn: int = Field(default=0, ge=0)


__all__ = ["ProjectSkillProposal", "ProjectSkillStatus", "ProjectSkillVersion"]
