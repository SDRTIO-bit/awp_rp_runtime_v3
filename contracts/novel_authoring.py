"""Strict contracts for author-led chapter development."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuthorPlanStatus(str, Enum):
    DRAFT = "draft"
    PENDING_CONFIRMATION = "pending_confirmation"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    EXECUTED = "executed"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthorApproval(_StrictModel):
    message_id: str = Field(min_length=1)
    confirmation_quote: str = Field(min_length=1)
    turn: int = Field(ge=1)
    approved_at: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)


class AuthorMaterial(_StrictModel):
    material_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    category: str = "idea"
    source_message_ids: list[str] = Field(default_factory=list)
    status: str = "pending"
    captured_at: str = ""


class AuthorScene(_StrictModel):
    scene_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    change: str = Field(min_length=1)
    opening_state: str = ""
    ending_state: str = ""
    purpose: str = ""
    characters: list[str] = Field(default_factory=list)


class AuthorCharacterIntent(_StrictModel):
    character: str = Field(min_length=1)
    goal: str = ""
    motivation: str = ""
    choice: str = ""
    subtext: str = ""
    boundaries: list[str] = Field(default_factory=list)
    new_character: bool = False


class AuthorChapterPlan(_StrictModel):
    plan_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    chapter_index: int = Field(ge=1)
    revision: int = Field(default=1, ge=1)
    status: AuthorPlanStatus = AuthorPlanStatus.DRAFT
    title: str = ""
    target_chars: int = Field(default=3000, ge=1)
    purpose: str = Field(min_length=1)
    target_reader_effect: str = ""
    confirmed_events: list[str] = Field(min_length=1)
    causal_chain: list[str] = Field(default_factory=list)
    scenes: list[AuthorScene] = Field(min_length=1)
    character_intents: list[AuthorCharacterIntent] = Field(default_factory=list)
    world_constraints: list[str] = Field(default_factory=list)
    information_distribution: list[str] = Field(default_factory=list)
    must_keep: list[str] = Field(default_factory=list)
    must_not: list[str] = Field(default_factory=list)
    deliberate_ambiguities: list[str] = Field(default_factory=list)
    writer_freedom: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    source_material_ids: list[str] = Field(default_factory=list)
    proposal_turn: int = Field(default=0, ge=0)
    approval: AuthorApproval | None = None
    executed_at: str = ""
    execution_message_id: str = ""
    authoring_mode: str = "author_led"

    @model_validator(mode="after")
    def validate_ready_state(self) -> "AuthorChapterPlan":
        if self.status in {AuthorPlanStatus.APPROVED, AuthorPlanStatus.EXECUTED}:
            if self.unresolved_questions:
                raise ValueError("approved plan cannot contain unresolved questions")
            if not self.scenes:
                raise ValueError("approved plan requires at least one scene")
            if self.approval is None:
                raise ValueError("approved plan requires an approval record")
        return self


__all__ = [
    "AuthorApproval",
    "AuthorChapterPlan",
    "AuthorCharacterIntent",
    "AuthorMaterial",
    "AuthorPlanStatus",
    "AuthorScene",
]
