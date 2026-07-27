"""Strict contracts for the browser author/editor event stream."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_CHAPTER_ROOM = re.compile(r"chapter:([1-9][0-9]*)")


class NovelRoomId(BaseModel):
    """A project-local collaboration room with a canonical wire identifier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["book", "chapter"]
    chapter_index: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_kind(self) -> "NovelRoomId":
        if self.kind == "book" and self.chapter_index is not None:
            raise ValueError("book room cannot have a chapter index")
        if self.kind == "chapter" and self.chapter_index is None:
            raise ValueError("chapter room requires a chapter index")
        return self

    @classmethod
    def parse(cls, value: str) -> "NovelRoomId":
        if value == "book":
            return cls(kind="book")
        match = _CHAPTER_ROOM.fullmatch(value)
        if match is not None:
            return cls(kind="chapter", chapter_index=int(match.group(1)))
        raise ValueError("invalid novel room")

    def __str__(self) -> str:
        if self.kind == "book":
            return "book"
        return f"chapter:{self.chapter_index}"


class NovelWebEvent(BaseModel):
    """One durable event delivered to a Novel Coding browser client."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: int = Field(ge=1)
    project_id: str = Field(min_length=1)
    room: str = Field(min_length=1)
    branch_id: str = Field(
        default="main",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
    )
    turn_id: str | None = Field(default=None, max_length=128)
    type: str = Field(min_length=1)
    payload: dict[str, Any]
    created_at: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_room(self) -> "NovelWebEvent":
        NovelRoomId.parse(self.room)
        return self


__all__ = ["NovelRoomId", "NovelWebEvent"]
