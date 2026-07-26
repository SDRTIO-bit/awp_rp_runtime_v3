"""Contracts for immutable project document versions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NovelDocumentKind = Literal["outline", "world", "characters", "draft"]


class NovelDocumentVersion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: str = Field(min_length=1)
    kind: NovelDocumentKind
    resource_id: str = ""
    revision: int = Field(ge=0)
    content: str
    content_hash: str = Field(min_length=1)
    source: str = Field(min_length=1)
    created_at: str = Field(min_length=1)


__all__ = ["NovelDocumentKind", "NovelDocumentVersion"]
