"""Protocol contracts for the embedded Pi novel-agent host."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


FRAME_KINDS = frozenset({
    "init",
    "prompt",
    "cancel",
    "tool_call",
    "tool_result",
    "event",
    "turn_end",
    "error",
    "shutdown",
})


class NovelPiProtocolError(ValueError):
    """Raised when a Pi host frame is malformed or outside the allowlist."""


class NovelPiFrame(BaseModel):
    """One JSON Lines frame exchanged between Python and the Pi host."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    kind: str
    request_id: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if self.kind not in FRAME_KINDS:
            raise NovelPiProtocolError(f"unsupported frame kind: {self.kind}")


def encode_frame(frame: NovelPiFrame) -> str:
    """Serialize a validated frame as one JSON Lines payload."""

    return frame.model_dump_json(exclude_none=True)


def decode_frame(raw: str) -> NovelPiFrame:
    """Parse one JSON Lines payload without accepting unknown fields."""

    try:
        return NovelPiFrame.model_validate_json(raw)
    except ValidationError as exc:
        message = str(exc)
        if "unsupported frame kind" in message:
            raise NovelPiProtocolError(message) from exc
        raise NovelPiProtocolError(f"invalid protocol frame: {message}") from exc
