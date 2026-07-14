"""Typed task and result contracts for Pi-backed novel role agents."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


NOVEL_PI_ROLES = frozenset({
    "architect",
    "director",
    "writer",
    "continuity_checker",
    "style_cleaner",
    "ledger_curator",
})

_SENSITIVE_KEYS = frozenset({
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
})


def _find_sensitive_key(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in _SENSITIVE_KEYS:
                return str(key)
            found = _find_sensitive_key(nested)
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found = _find_sensitive_key(nested)
            if found:
                return found
    return None


class NovelPiRoleTask(BaseModel):
    """One project-bound task executed by a Pi role session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str
    project_id: str = Field(min_length=1, max_length=128)
    chapter_index: int = Field(ge=0)
    revision: int = Field(default=1, ge=1)
    phase: str = Field(default="", max_length=128)
    session_key: str = Field(min_length=1, max_length=256)
    task_contract: str = Field(min_length=1)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    stream: bool = False

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in NOVEL_PI_ROLES:
            raise ValueError(f"unsupported Pi novel role: {value}")
        return value

    @model_validator(mode="after")
    def reject_sensitive_payload(self) -> "NovelPiRoleTask":
        sensitive_key = _find_sensitive_key(self.input_payload)
        if sensitive_key:
            raise ValueError(f"sensitive key is not allowed in Pi role payload: {sensitive_key}")
        return self


class NovelPiRoleResult(BaseModel):
    """Validated terminal output from a Pi role session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1, max_length=128)
    role: str
    session_key: str = Field(min_length=1, max_length=256)
    text: str = ""
    structured_data: dict[str, Any] | None = None
    model: str = ""
    usage: dict[str, int] = Field(default_factory=dict)
    finish_reason: str = ""
    latency_ms: int = Field(default=0, ge=0)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in NOVEL_PI_ROLES:
            raise ValueError(f"unsupported Pi novel role: {value}")
        return value

