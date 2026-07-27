"""Project-bound Pi editor sessions for browser collaboration rooms."""

from __future__ import annotations

import asyncio
import hashlib
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine

from ..contracts.novel_web_event import NovelRoomId, NovelWebEvent
from .novel_agent_runtime import create_novel_agent_runtime
from .novel_brain import BrainCallbacks
from .novel_conversation_store import NovelConversationStore
from .novel_authoring_service import NovelAuthoringService
from .novel_pi_tool_service import NovelPiToolService
from .novel_prompt_service import NovelPromptService
from .novel_trace import NovelPipelineCancelled, NovelStreamCallbacks
from .novel_workspace_catalog import NovelWorkspaceCatalog


@dataclass(frozen=True)
class EditorRoomKey:
    project_id: str
    room: str
    branch_id: str = "main"

    @classmethod
    def parse(
        cls, project_id: str, room: str, branch_id: str = "main"
    ) -> "EditorRoomKey":
        if not project_id.strip():
            raise ValueError("project id cannot be empty")
        return cls(
            project_id=project_id,
            room=str(NovelRoomId.parse(room)),
            branch_id=branch_id,
        )


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
class _PendingToolApproval:
    future: asyncio.Future[str]
    signature: str


@dataclass
class _RoomSession:
    key: EditorRoomKey
    store: NovelConversationStore
    project_dir: Path
    runtime: Any | None = None
    active_message_id: str = ""
    active_editor_turn: bool = False
    active_action: bool = False
    action_commit_started: bool = False
    action_cancel: threading.Event = field(default_factory=threading.Event)
    turn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    runtime_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    subscriptions: set[EditorSubscription] = field(default_factory=set)
    pending_approvals: dict[str, _PendingToolApproval] = field(
        default_factory=dict
    )
    remembered_tool_approvals: set[str] = field(default_factory=set)


class EditorSessionManager:
    """Own one persistent Pi editor runtime per project/room/branch."""

    def __init__(
        self,
        catalog: NovelWorkspaceCatalog,
        *,
        runtime_factory: Callable[..., Any] = create_novel_agent_runtime,
        tool_approval_timeout: float = 120.0,
    ):
        self.catalog = catalog
        self._runtime_factory = runtime_factory
        self._tool_approval_timeout = tool_approval_timeout
        self._sessions: dict[EditorRoomKey, _RoomSession] = {}
        self._room_locks: dict[tuple[str, str], asyncio.Lock] = {}
        self._closed = False

    @staticmethod
    def key(
        project_id: str, room: str, branch_id: str = "main"
    ) -> EditorRoomKey:
        return EditorRoomKey.parse(project_id, room, branch_id=branch_id)

    def _room_lock(self, key: EditorRoomKey) -> asyncio.Lock:
        room_key = (key.project_id, key.room)
        if room_key not in self._room_locks:
            self._room_locks[room_key] = asyncio.Lock()
        return self._room_locks[room_key]

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
                key.room, branch_id=key.branch_id, after_event_id=after_event_id
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
            key.room, branch_id=key.branch_id, after_event_id=after_event_id
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
                on_tool_event=lambda payload: self._from_worker(
                    loop,
                    self._emit_event(key, "tool_activity", payload),
                ),
                request_tool_approval=lambda payload: (
                    self._approval_from_worker(loop, key, payload)
                ),
            )
            workspace = self.catalog.require(key.project_id)
            digest = hashlib.sha256(
                f"{key.project_id}\0{key.room}\0{key.branch_id}".encode("utf-8")
            ).hexdigest()[:24]
            session_id = f"novel-editor-{digest}"
            room_dir = (
                workspace.root
                / ".awp"
                / "pi-sessions"
                / "editor"
                / digest
            ).resolve()

            # Compute context seed from branch's inherited history
            context_seed = ""
            if key.branch_id != "main" or key.branch_id == "main":
                context_seed = session.store.render_context(
                    key.room, branch_id=key.branch_id
                )

            def create_runtime() -> Any:
                return self._runtime_factory(
                    self.catalog.registry(key.project_id),
                    callbacks,
                    workspace.root,
                    key.project_id,
                    session_id=session_id,
                    session_dir=room_dir,
                    context_seed=context_seed,
                )

            session.runtime = await asyncio.to_thread(create_runtime)
            return session.runtime

    async def handle_author_message(
        self,
        key: EditorRoomKey,
        text: str,
        client_message_id: str,
        references: list[dict[str, str]] | None = None,
    ) -> None:
        if not text.strip():
            raise ValueError("author message cannot be empty")
        if len(text) > 20_000:
            raise ValueError("author message exceeds 20000 characters")
        if not client_message_id.strip() or len(client_message_id) > 200:
            raise ValueError("invalid client message id")
        session = self._require_session(key)
        turn_id = f"turn-{uuid.uuid4().hex}"

        # Materialize references into prompt context
        prompt_text = text
        validated_refs: list[dict[str, Any]] | None = None
        if references:
            from .novel_project_context_service import NovelProjectContextService
            context_svc = NovelProjectContextService(session.project_dir)
            materialized = context_svc.materialize(references)
            validated_refs = [
                {"path": r.path, "sha256": r.sha256, "size_bytes": r.size_bytes}
                for r in materialized.references
            ]
            prompt_text = text + "\n\n" + materialized.prompt_context

        async with session.turn_lock:
            # Durable turn lifecycle start
            started = session.store.append(
                key.room,
                "turn_started",
                {"status": "queued"},
                branch_id=key.branch_id,
                turn_id=turn_id,
            )
            self._broadcast(session, started)
            save_payload: dict[str, Any] = {
                "client_message_id": client_message_id,
                "text": text,
            }
            if validated_refs:
                save_payload["references"] = validated_refs
            saved = session.store.append(
                key.room,
                "author_message_saved",
                save_payload,
                branch_id=key.branch_id,
                turn_id=turn_id,
            )
            self._broadcast(session, saved)
            session.active_message_id = uuid.uuid4().hex
            try:
                runtime = await self.ensure_runtime(key)
                session.active_editor_turn = True
                result = await asyncio.to_thread(
                    runtime.handle_message, prompt_text
                )
            except Exception as exc:
                failed = session.store.append(
                    key.room,
                    "turn_failed",
                    {"message": str(exc)[-4000:]},
                    branch_id=key.branch_id,
                    turn_id=turn_id,
                )
                self._broadcast(session, failed)
                return
            finally:
                session.active_editor_turn = False
                message_id = session.active_message_id
                session.active_message_id = ""
            completed = session.store.complete_editor_message(
                key.room, message_id, result
            )
            self._broadcast(session, completed)
            # Durable turn lifecycle end
            turn_done = session.store.append(
                key.room,
                "turn_completed",
                {"status": "completed"},
                branch_id=key.branch_id,
                turn_id=turn_id,
            )
            self._broadcast(session, turn_done)
            chapter_index = (
                int(key.room.split(":", 1)[1])
                if key.room.startswith("chapter:")
                else None
            )
            context = NovelAuthoringService(
                session.project_dir, key.project_id
            ).authoring_context(chapter_index)
            for plan in context["plans"]:
                if plan["status"] in {
                    "draft",
                    "pending_confirmation",
                    "approved",
                }:
                    plan_event = session.store.append(
                        key.room, "author_plan_saved", plan
                    )
                    self._broadcast(session, plan_event)

    async def handle_author_action(
        self,
        key: EditorRoomKey,
        action: str,
        plan_id: str,
        revision: int,
    ) -> None:
        actions = {
            "approve_plan": (
                "approve_author_plan",
                "我确认这个计划。",
                "我确认这个计划",
                "author_plan_approved",
            ),
            "execute_plan": (
                "execute_author_plan",
                "现在执行这个计划。",
                "现在执行这个计划",
                "author_plan_executed",
            ),
        }
        if action not in actions:
            raise ValueError("unknown author action")
        if not plan_id.strip() or revision < 1:
            raise ValueError("invalid author plan reference")
        tool_name, author_text, quote, success_type = actions[action]
        session = self._require_session(key)
        workspace = self.catalog.require(key.project_id)

        async with session.turn_lock:
            authoring = NovelAuthoringService(
                workspace.root, workspace.project_id
            )
            turn = authoring.next_turn()
            message_id = authoring.record_author_message(
                author_text,
                f"web-{key.room}",
                turn,
                source="web_action",
            )
            saved = session.store.append(
                key.room,
                "author_message_saved",
                {
                    "client_message_id": message_id,
                    "text": author_text,
                    "source": "web_action",
                },
            )
            self._broadcast(session, saved)

            loop = asyncio.get_running_loop()
            session.action_cancel.clear()
            session.action_commit_started = False
            callbacks = NovelStreamCallbacks(
                on_phase=lambda event, phase, data: self._from_worker(
                    loop,
                    self._emit_pipeline_phase(
                        key, event, phase, data
                    ),
                ),
                on_chunk=lambda text: self._from_worker(
                    loop,
                    self._emit_event(
                        key, "writer_delta", {"text": text}
                    ),
                ),
                on_error=lambda phase, message: self._from_worker(
                    loop,
                    self._emit_event(
                        key,
                        "turn_failed",
                        {"phase": phase, "message": message[-4000:]},
                    ),
                ),
                on_draft_saved=lambda payload: self._from_worker(
                    loop,
                    self._emit_draft_saved(key, payload),
                ),
                should_cancel=session.action_cancel.is_set,
            )
            prompt_snapshot_id = ""
            if action == "execute_plan":
                prompt_snapshot_id = NovelPromptService(workspace).snapshot(
                    {
                        "writer",
                        "continuity_checker",
                        "style_cleaner",
                        "ledger_curator",
                    }
                ).snapshot_id

            def execute_action() -> dict[str, object]:
                service = NovelPiToolService(
                    self.catalog.registry(key.project_id),
                    project_id=key.project_id,
                    project_dir=workspace.root,
                    callbacks=callbacks,
                    current_turn=turn,
                    current_message_id=message_id,
                    current_author_message=author_text,
                    prompt_snapshot_id=prompt_snapshot_id,
                )
                return service.execute(
                    tool_name,
                    {
                        "plan_id": plan_id,
                        "revision": revision,
                        "confirmation_quote": quote,
                    },
                )

            session.active_action = True
            try:
                await asyncio.to_thread(execute_action)
            except NovelPipelineCancelled:
                return
            except Exception as exc:
                rejected = session.store.append(
                    key.room,
                    "action_rejected",
                    {
                        "action": action,
                        "plan_id": plan_id,
                        "revision": revision,
                        "message": str(exc)[-4000:],
                    },
                )
                self._broadcast(session, rejected)
                return
            finally:
                session.active_action = False

            plan = authoring.get_plan(plan_id, revision)
            success = session.store.append(
                key.room,
                success_type,
                {
                    "plan_id": plan.plan_id,
                    "revision": plan.revision,
                    "chapter_index": plan.chapter_index,
                    "status": plan.status.value,
                },
            )
            self._broadcast(session, success)

    async def cancel(self, key: EditorRoomKey) -> None:
        session = self._require_session(key)
        self._deny_pending_approvals(session)
        if session.active_action:
            if session.action_commit_started:
                raise RuntimeError(
                    "pipeline has already committed the accepted draft"
                )
            session.action_cancel.set()
        elif session.runtime is not None:
            await asyncio.to_thread(session.runtime.abort)
        else:
            raise RuntimeError("no active editor runtime")
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
            self._deny_pending_approvals(session)
            for subscription in list(session.subscriptions):
                await subscription.close()
            if session.runtime is not None:
                await asyncio.to_thread(session.runtime.close)
        self._sessions.clear()

    async def resolve_tool_approval(
        self,
        key: EditorRoomKey,
        approval_id: str,
        decision: str,
        remember: bool,
    ) -> None:
        if decision not in {"allow", "deny"}:
            raise ValueError("invalid tool approval decision")
        session = self._require_session(key)
        pending = session.pending_approvals.get(approval_id)
        if pending is None or pending.future.done():
            raise ValueError("unknown or already resolved tool approval")
        if remember and decision == "allow":
            session.remembered_tool_approvals.add(pending.signature)
        pending.future.set_result(decision)

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

    def _approval_from_worker(
        self,
        loop: asyncio.AbstractEventLoop,
        key: EditorRoomKey,
        payload: dict[str, Any],
    ) -> str:
        future = asyncio.run_coroutine_threadsafe(
            self._request_tool_approval(key, payload),
            loop,
        )
        try:
            return future.result(timeout=self._tool_approval_timeout + 10)
        except Exception:
            future.cancel()
            return "deny"

    async def _request_tool_approval(
        self,
        key: EditorRoomKey,
        payload: dict[str, Any],
    ) -> str:
        session = self._require_session(key)
        approval_id = str(payload.get("approval_id", ""))
        signature = str(payload.get("signature", ""))
        if not approval_id or not signature:
            return "deny"
        if signature in session.remembered_tool_approvals:
            await self._emit_event(
                key,
                "tool_approval_resolved",
                {
                    "approval_id": approval_id,
                    "decision": "allow",
                    "remembered": True,
                },
            )
            return "allow"
        if approval_id in session.pending_approvals:
            return "deny"
        decision_future = asyncio.get_running_loop().create_future()
        session.pending_approvals[approval_id] = _PendingToolApproval(
            future=decision_future,
            signature=signature,
        )
        await self._emit_event(key, "tool_approval_requested", payload)
        try:
            decision = await asyncio.wait_for(
                decision_future,
                timeout=self._tool_approval_timeout,
            )
        except (TimeoutError, asyncio.CancelledError):
            decision = "deny"
        finally:
            session.pending_approvals.pop(approval_id, None)
        await self._emit_event(
            key,
            "tool_approval_resolved",
            {
                "approval_id": approval_id,
                "decision": decision,
                "remembered": False,
            },
        )
        return decision

    async def _emit_pipeline_phase(
        self,
        key: EditorRoomKey,
        event: str,
        phase: str,
        data: dict[str, Any],
    ) -> None:
        await self._emit_event(
            key,
            "pipeline_phase",
            {"event": event, "phase": phase, "data": data},
        )
        if phase == "quality" and event == "end":
            issues = [
                *data.get("blocking_reasons", []),
                *data.get("warnings", []),
            ]
            for issue in issues:
                await self._emit_event(
                    key,
                    "quality_issue",
                    {
                        "severity": (
                            "blocking"
                            if issue in data.get("blocking_reasons", [])
                            else "warning"
                        ),
                        "message": str(issue),
                    },
                )

    async def _emit_draft_saved(
        self,
        key: EditorRoomKey,
        payload: dict[str, Any],
    ) -> None:
        session = self._require_session(key)
        session.action_commit_started = True
        await self._emit_event(key, "draft_version_saved", payload)

    async def _emit_event(
        self,
        key: EditorRoomKey,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        session = self._require_session(key)
        event = session.store.append(key.room, event_type, payload)
        self._broadcast(session, event)

    @staticmethod
    def _from_worker(
        loop: asyncio.AbstractEventLoop,
        coroutine: Coroutine[Any, Any, None],
    ) -> None:
        future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        future.result(timeout=30)

    @staticmethod
    def _deny_pending_approvals(session: _RoomSession) -> None:
        for pending in session.pending_approvals.values():
            if not pending.future.done():
                pending.future.set_result("deny")

    def _require_session(self, key: EditorRoomKey) -> _RoomSession:
        if self._closed:
            raise RuntimeError("editor session manager is closed")
        workspace = self.catalog.require(key.project_id)
        session = self._sessions.get(key)
        if session is None:
            session = _RoomSession(
                key=key,
                store=NovelConversationStore(
                    workspace.root, workspace.project_id
                ),
                project_dir=workspace.root,
            )
            self._sessions[key] = session
            # Recover any stale incomplete turn
            session.store.interrupt_incomplete_turn(
                key.room, branch_id=key.branch_id
            )
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
