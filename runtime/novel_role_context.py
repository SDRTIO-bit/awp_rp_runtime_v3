"""Synchronous project binding for Pi novel role calls and read tools."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator


class NovelRoleContextError(RuntimeError):
    """Raised when a role call occurs outside a NovelEngine scope."""


@dataclass(frozen=True)
class NovelRoleContext:
    registry: Any
    project_id: str
    chapter_index: int
    revision: int = 1
    phase: str = ""


_CURRENT_CONTEXT: ContextVar[NovelRoleContext | None] = ContextVar(
    "novel_role_context",
    default=None,
)


@contextmanager
def novel_role_scope(
    *,
    registry: Any,
    project_id: str,
    chapter_index: int,
    revision: int = 1,
    phase: str = "",
) -> Iterator[NovelRoleContext]:
    """Bind one engine task to role agents and restore any outer scope."""

    context = NovelRoleContext(
        registry=registry,
        project_id=project_id,
        chapter_index=chapter_index,
        revision=revision,
        phase=phase,
    )
    token = _CURRENT_CONTEXT.set(context)
    try:
        yield context
    finally:
        _CURRENT_CONTEXT.reset(token)


def get_novel_role_context() -> NovelRoleContext:
    """Return the active project binding or fail closed."""

    context = _CURRENT_CONTEXT.get()
    if context is None:
        raise NovelRoleContextError("Pi novel role context is not active")
    return context

