"""Strict Pydantic v2 contracts for conversation branching, turns,
file references, work plans, mutation previews/receipts, effects,
and search results — the novel-only coding conversation system."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Enums / Literals
# ---------------------------------------------------------------------------

ConversationBranchStatus = Literal["active", "archived"]

TurnStatus = Literal[
    "queued",
    "running",
    "waiting_approval",
    "running_pipeline",
    "completed",
    "failed",
    "cancelled",
    "interrupted",
]

WorkPlanStatus = Literal["pending", "in_progress", "completed"]

MutationOperation = Literal["write", "edit", "restore"]

_POSIX_RELATIVE = re.compile(r"^(?:[^/\0\\])(?:[^/\0]*/)*[^/\0]+$")


def _is_posix_relative(path: str) -> bool:
    return bool(_POSIX_RELATIVE.match(path)) and not path.startswith("/")


# ---------------------------------------------------------------------------
# Conversation branch metadata
# ---------------------------------------------------------------------------


class ConversationBranch(BaseModel):
    """A named, versioned fork root belonging to one project room."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    branch_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    project_id: str = Field(min_length=1)
    room: str = Field(min_length=1)
    parent_branch_id: str | None = None
    fork_event_id: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=1, max_length=80)
    status: ConversationBranchStatus = "active"
    created_at: str = Field(min_length=1)
    updated_at: str = Field(min_length=1)
    head_event_id: int = Field(default=0, ge=0)
    has_side_effects: bool = False


# ---------------------------------------------------------------------------
# Editor work plan
# ---------------------------------------------------------------------------


class EditorWorkPlanItem(BaseModel):
    """One atomic step in the editor's operational investigation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=80)
    step: str = Field(min_length=1, max_length=500)
    status: WorkPlanStatus


class EditorWorkPlan(BaseModel):
    """An editor-authored *operational* task list — not an author chapter plan.

    Invariant: at most one item may be ``in_progress`` at any moment.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    explanation: str = Field(default="", max_length=2_000)
    items: list[EditorWorkPlanItem] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _check_in_progress(self) -> "EditorWorkPlan":
        in_progress = [it for it in self.items if it.status == "in_progress"]
        if len(in_progress) > 1:
            raise ValueError(
                f"at most one work-plan item may be in_progress; "
                f"got {len(in_progress)}"
            )
        return self

    @model_validator(mode="after")
    def _check_duplicate_ids(self) -> "EditorWorkPlan":
        seen: set[str] = set()
        for it in self.items:
            if it.id in seen:
                raise ValueError(f"duplicate work-plan item id: {it.id}")
            seen.add(it.id)
        return self


# ---------------------------------------------------------------------------
# Project-file reference (author-selected)
# ---------------------------------------------------------------------------


class ProjectFileReference(BaseModel):
    """A project-relative path the author explicitly attached to a turn.

    The path MUST be POSIX-relative and must not escape the project root.
    Filesystem-level enforcement lives in the runtime context service.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    size_bytes: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_path(self) -> "ProjectFileReference":
        if "\\" in self.path:
            raise ValueError(f"backslash not allowed: {self.path!r}")
        if ":" in self.path:
            raise ValueError(f"colon not allowed: {self.path!r}")
        if self.path.startswith("/") or not _is_posix_relative(self.path):
            raise ValueError(
                f"path must be a POSIX-relative project path: {self.path!r}"
            )
        if self.path.startswith("."):
            raise ValueError(
                f"path must not start with dot: {self.path!r}"
            )
        return self


# ---------------------------------------------------------------------------
# Mutation contracts (preview / receipt)
# ---------------------------------------------------------------------------


class ProjectMutationPreview(BaseModel):
    """Proposed diff and hashes computed *before* a file write/edit/restore."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    operation: MutationOperation
    before_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    after_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    diff: str = Field(max_length=60_000)


class ProjectMutationReceipt(BaseModel):
    """Immutable proof of a completed project-file mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    change_id: str = Field(min_length=1, max_length=128)
    turn_id: str = Field(min_length=1, max_length=128)
    branch_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    path: str = Field(min_length=1)
    operation: MutationOperation
    before_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    after_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    diff: str = Field(max_length=60_000)
    history_version_id: str = Field(min_length=1, max_length=128)
    created_at: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Conversation effect (side-effect disclosure)
# ---------------------------------------------------------------------------


class ConversationEffect(BaseModel):
    """A lightweight summary of one side-effect event that would be orphaned
    if the author forks after it without confirmation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: int = Field(ge=1)
    type: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Conversation search hit
# ---------------------------------------------------------------------------


class ConversationSearchHit(BaseModel):
    """One message-level search result for the conversation search endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: int = Field(ge=1)
    branch_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    role: Literal["author", "editor"]
    excerpt: str = Field(min_length=1, max_length=300)
    created_at: str = Field(min_length=1)


__all__ = [
    "ConversationBranch",
    "ConversationBranchStatus",
    "ConversationEffect",
    "ConversationSearchHit",
    "EditorWorkPlan",
    "EditorWorkPlanItem",
    "MutationOperation",
    "ProjectFileReference",
    "ProjectMutationPreview",
    "ProjectMutationReceipt",
    "TurnStatus",
    "WorkPlanStatus",
]
