"""Novel engine streaming callbacks — phase / beat / chunk events.

Follows the RP engine's _safe_on_step pattern: callbacks are lightweight
dict-based hooks with zero external dependencies. The CLI layer (which may
import Rich for TUI) is the only consumer of these callbacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

PhaseCallback = Callable[[str, str, dict[str, Any]], None]
BeatCallback = Callable[[str, int, dict[str, Any]], None]
ChunkCallback = Callable[[str], None]
ErrorCallback = Callable[[str, str], None]
DraftSavedCallback = Callable[[dict[str, Any]], None]
CancellationCallback = Callable[[], bool]


class NovelPipelineCancelled(RuntimeError):
    """Raised before formal commits when the author cancels a running pipeline."""


@dataclass
class NovelStreamCallbacks:
    on_phase: PhaseCallback = field(default=lambda e, n, p: None)
    on_beat: BeatCallback = field(default=lambda e, i, p: None)
    on_chunk: ChunkCallback = field(default=lambda t: None)
    on_error: ErrorCallback = field(default=lambda ph, msg: None)
    on_draft_saved: DraftSavedCallback = field(default=lambda payload: None)
    should_cancel: CancellationCallback = field(default=lambda: False)


def safe_on_phase(cb: PhaseCallback | None, event: str, name: str,
                  payload: dict[str, Any]) -> None:
    if cb is None:
        return
    try:
        cb(event, name, payload)
    except Exception:
        pass


def safe_on_beat(cb: BeatCallback | None, event: str, beat_index: int,
                 payload: dict[str, Any]) -> None:
    if cb is None:
        return
    try:
        cb(event, beat_index, payload)
    except Exception:
        pass


def safe_on_chunk(cb: ChunkCallback | None, text: str) -> None:
    if cb is None:
        return
    try:
        cb(text)
    except Exception:
        pass


def safe_on_error(cb: ErrorCallback | None, phase: str, message: str) -> None:
    if cb is None:
        return
    try:
        cb(phase, message)
    except Exception:
        pass


def safe_on_draft_saved(
    cb: DraftSavedCallback | None,
    payload: dict[str, Any],
) -> None:
    if cb is None:
        return
    try:
        cb(payload)
    except Exception:
        pass


__all__ = [
    "NovelPipelineCancelled",
    "NovelStreamCallbacks",
    "safe_on_beat",
    "safe_on_chunk",
    "safe_on_draft_saved",
    "safe_on_error",
    "safe_on_phase",
]
