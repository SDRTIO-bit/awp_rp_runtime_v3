"""Append-only room event storage for the Novel Coding workspace."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts.novel_web_event import NovelRoomId, NovelWebEvent
from .novel_authoring_service import NovelAuthoringService


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NovelConversationStore:
    """Persists replayable browser events without accepting filesystem paths."""

    def __init__(self, project_root: str | Path, project_id: str):
        if not project_id.strip():
            raise ValueError("project id cannot be empty")
        self.project_id = project_id
        self._authoring = NovelAuthoringService(project_root, project_id)
        self.root = self._authoring.root / "conversations"
        self.root.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        room: str,
        type: str,
        payload: dict[str, Any],
    ) -> NovelWebEvent:
        room_id = NovelRoomId.parse(room)
        if not type.strip():
            raise ValueError("event type cannot be empty")
        if not isinstance(payload, dict):
            raise TypeError("event payload must be a dictionary")
        event = NovelWebEvent(
            event_id=self._authoring.next_event_id(),
            project_id=self.project_id,
            room=str(room_id),
            type=type,
            payload=payload,
            created_at=_now(),
        )
        line = event.model_dump_json() + "\n"
        path = self._event_path(room_id)
        with self._authoring._lock:
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
        return event

    def replay(
        self,
        room: str,
        after_event_id: int = 0,
        limit: int = 500,
    ) -> list[NovelWebEvent]:
        room_id = NovelRoomId.parse(room)
        if after_event_id < 0:
            raise ValueError("after_event_id cannot be negative")
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        path = self._event_path(room_id)
        if not path.is_file():
            return []

        events: list[NovelWebEvent] = []
        with self._authoring._lock:
            lines = path.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                event = NovelWebEvent.model_validate_json(line)
            except Exception as exc:
                raise ValueError(
                    f"invalid conversation event at line {line_number}"
                ) from exc
            if event.project_id != self.project_id or event.room != str(room_id):
                raise ValueError(
                    f"conversation event at line {line_number} does not belong "
                    "to this project room"
                )
            if event.event_id > after_event_id:
                events.append(event)
        events.sort(key=lambda event: event.event_id)
        return events[:limit]

    def complete_editor_message(
        self,
        room: str,
        message_id: str,
        text: str,
    ) -> NovelWebEvent:
        if not message_id.strip():
            raise ValueError("message id cannot be empty")
        if not text.strip():
            raise ValueError("editor message cannot be empty")
        return self.append(
            room,
            "editor_message_completed",
            {"message_id": message_id, "text": text},
        )

    def _event_path(self, room: NovelRoomId) -> Path:
        filename = (
            "book.jsonl"
            if room.kind == "book"
            else f"chapter-{room.chapter_index:06d}.jsonl"
        )
        return self.root / filename


__all__ = ["NovelConversationStore"]
