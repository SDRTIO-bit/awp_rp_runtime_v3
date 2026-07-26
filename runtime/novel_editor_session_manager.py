"""Project-bound Pi editor sessions for browser collaboration rooms."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine

from ..contracts.novel_web_event import NovelRoomId, NovelWebEvent
from .novel_agent_runtime import create_novel_agent_runtime
from .novel_brain import BrainCallbacks
from .novel_conversation_store import NovelConversationStore
from .novel_workspace_catalog import NovelWorkspaceCatalog


@dataclass(frozen=True)
class EditorRoomKey:
    project_id: str
    room: str

    @classmethod
    def parse(cls, project_id: str, room: str) -> "EditorRoomKey":
        if not project_id.strip():
            raise ValueError("project id cannot be empty")
        return cls(project_id=project_id, room=str(NovelRoomId.parse(room)))


class EditorSubscription:
    """A non-blocking per-browser delivery queue."""

    def __init__(
        self,
        websocket: Any,
        on_close: Callable[["EditorSubscription"], None],
        *,
        max_pending: int = 128,
    ):
        self.websocket = websocket
        self._on_close = on_close
        self._max_pending = max_pending
        self._pending: deque[NovelWebEvent] = deque()
        self._wakeup = asyncio.Event()
        self._closed = False
        self._sender = asyncio.create_task(self._send_loop())

    def enqueue(self, event: NovelWebEvent) -> None:
        if self._closed:
            return
        if (
            event.type == "editor_delta"
            and len(self._pending) >= self._max_pending
            and self._pending
            and self._pending[-1].type == "editor_delta"
            and self._pending[-1].payload.get("message_id")
            == event.payload.get("message_id")
        ):
            previous = self._pending.pop()
            payload = dict(event.payload)
            payload["text"] = (
                str(previous.payload.get("text", ""))
                + str(event.payload.get("text", ""))
            )
            self._pending.append(event.model_copy(update={"payload": payload}))
        else:
            # Control events are never dropped. This is a soft cap when
            # adjacent deltas cannot be combined without changing semantics.
            self._pending.append(event)
        self._wakeup.set()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._wakeup.set()
        if self._sender is not asyncio.current_task():
            await self._sender
        self._on_close(self)

    async def _send_loop(self) -> None:
        try:
            while True:
                await self._wakeup.wait()
                self._wakeup.clear()
                while self._pending:
                    event = self._pending.popleft()
                    await self.websocket.send_json(event.model_dump(mode="json"))
                if self._closed:
                    return
        except Exception:
            self._closed = True
            self._on_close(self)


@dataclass
class _RoomSession:
    key: EditorRoomKey
    store: NovelConversationStore
    project_dir: Path
    runtime: Any | None = None
    active_message_id: str = ""
    turn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    runtime_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    subscriptions: set[EditorSubscription] = field(default_factory=set)


class EditorSessionManager:
    """Own one persistent Pi editor runtime per full-book/chapter room."""

    def __init__(
        self,
        catalog: NovelWorkspaceCatalog,
        *,
        runtime_factory: Callable[..., Any] = create_novel_agent_runtime,
    ):
        self.catalog = catalog
        self._runtime_factory = runtime_factory
        self._sessions: dict[EditorRoomKey, _RoomSession] = {}
        self._closed = False

    @staticmethod
    def key(project_id: str, room: str) -> EditorRoomKey:
        return EditorRoomKey.parse(project_id, room)

    async def subscribe(
        self,
        key: EditorRoomKey,
        websocket: Any,
        *,
        after_event_id: int | None = None,
    ) -> EditorSubscription:
        session = self._require_session(key)
        subscription = EditorSubscription(
            websocket,
            lambda item: session.subscriptions.discard(item),
        )
        session.subscriptions.add(subscription)
        if after_event_id is not None:
            for event in session.store.replay(
                key.room, after_event_id=after_event_id
            ):
                subscription.enqueue(event)
        return subscription

    async def replay(
        self,
        key: EditorRoomKey,
        subscription: EditorSubscription,
        after_event_id: int,
    ) -> None:
        session = self._require_session(key)
        for event in session.store.replay(
            key.room, after_event_id=after_event_id
        ):
            subscription.enqueue(event)

    async def ensure_runtime(self, key: EditorRoomKey) -> Any:
        session = self._require_session(key)
        if session.runtime is not None:
            return session.runtime
        async with session.runtime_lock:
            if session.runtime is not None:
                return session.runtime
            loop = asyncio.get_running_loop()
            callbacks = BrainCallbacks(
                on_chat=lambda text: self._from_worker(
                    loop, self._emit_delta(key, text)
                ),
            )
            workspace = self.catalog.require(key.project_id)
            digest = hashlib.sha256(
                f"{key.project_id}\0{key.room}".encode("utf-8")
            ).hexdigest()[:24]
            session_id = f"novel-editor-{digest}"
            room_dir = (
                workspace.root
                / ".awp"
                / "pi-sessions"
                / "editor"
                / digest
            ).resolve()

            def create_runtime() -> Any:
                return self._runtime_factory(
                    self.catalog.registry(key.project_id),
                    callbacks,
                    workspace.root,
                    key.project_id,
                    session_id=session_id,
                    session_dir=room_dir,
                )

            session.runtime = await asyncio.to_thread(create_runtime)
            return session.runtime

    async def handle_author_message(
        self,
        key: EditorRoomKey,
        text: str,
        client_message_id: str,
    ) -> None:
        if not text.strip():
            raise ValueError("author message cannot be empty")
        if len(text) > 20_000:
            raise ValueError("author message exceeds 20000 characters")
        if not client_message_id.strip() or len(client_message_id) > 200:
            raise ValueError("invalid client message id")
        session = self._require_session(key)
        async with session.turn_lock:
            saved = session.store.append(
                key.room,
                "author_message_saved",
                {
                    "client_message_id": client_message_id,
                    "text": text,
                },
            )
            self._broadcast(session, saved)
            session.active_message_id = uuid.uuid4().hex
            try:
                runtime = await self.ensure_runtime(key)
                result = await asyncio.to_thread(runtime.handle_message, text)
            except Exception as exc:
                failed = session.store.append(
                    key.room,
                    "turn_failed",
                    {"message": str(exc)[-4000:]},
                )
                self._broadcast(session, failed)
                return
            finally:
                message_id = session.active_message_id
                session.active_message_id = ""
            completed = session.store.complete_editor_message(
                key.room, message_id, result
            )
            self._broadcast(session, completed)

    async def cancel(self, key: EditorRoomKey) -> None:
        session = self._require_session(key)
        if session.runtime is None:
            raise RuntimeError("no active editor runtime")
        await asyncio.to_thread(session.runtime.abort)
        cancelled = session.store.append(
            key.room, "turn_cancelled", {}
        )
        self._broadcast(session, cancelled)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        sessions = list(self._sessions.values())
        for session in sessions:
            for subscription in list(session.subscriptions):
                await subscription.close()
            if session.runtime is not None:
                await asyncio.to_thread(session.runtime.close)
        self._sessions.clear()

    async def _emit_delta(
        self,
        key: EditorRoomKey,
        text: str,
    ) -> None:
        if not text:
            return
        session = self._require_session(key)
        event = session.store.append(
            key.room,
            "editor_delta",
            {
                "message_id": session.active_message_id or "active",
                "text": text,
            },
        )
        self._broadcast(session, event)

    @staticmethod
    def _from_worker(
        loop: asyncio.AbstractEventLoop,
        coroutine: Coroutine[Any, Any, None],
    ) -> None:
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        future.result(timeout=30)

    def _require_session(self, key: EditorRoomKey) -> _RoomSession:
        if self._closed:
            raise RuntimeError("editor session manager is closed")
        canonical = EditorRoomKey.parse(key.project_id, key.room)
        workspace = self.catalog.require(canonical.project_id)
        session = self._sessions.get(canonical)
        if session is None:
            session = _RoomSession(
                key=canonical,
                store=NovelConversationStore(
                    workspace.root, workspace.project_id
                ),
                project_dir=workspace.root,
            )
            self._sessions[canonical] = session
        return session

    @staticmethod
    def _broadcast(
        session: _RoomSession,
        event: NovelWebEvent,
    ) -> None:
        for subscription in list(session.subscriptions):
            subscription.enqueue(event)


__all__ = [
    "EditorRoomKey",
    "EditorSessionManager",
    "EditorSubscription",
]
