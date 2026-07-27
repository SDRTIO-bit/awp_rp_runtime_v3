"""Validated WebSocket protocol for Novel Coding editor rooms."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from aiohttp import WSMsgType, web

from .novel_editor_session_manager import EditorRoomKey, EditorSessionManager

EDITOR_SESSION_MANAGER_KEY: web.AppKey[EditorSessionManager] = web.AppKey(
    "editor_session_manager",
    EditorSessionManager,
)


def _protocol_error(message: str) -> dict[str, Any]:
    return {
        "type": "protocol_error",
        "payload": {"message": message},
    }


async def editor_websocket(request: web.Request) -> web.WebSocketResponse:
    manager = request.app[EDITOR_SESSION_MANAGER_KEY]
    websocket = web.WebSocketResponse(heartbeat=30)
    await websocket.prepare(request)

    try:
        branch_id = request.match_info.get("branch_id", "main")
        key = EditorRoomKey.parse(
            request.match_info["project_id"],
            request.match_info["room"],
            branch_id=branch_id,
        )
        manager.catalog.require(key.project_id)
    except (KeyError, ValueError) as exc:
        await websocket.send_json(_protocol_error(str(exc)))
        await websocket.close(code=1008)
        return websocket

    subscription = await manager.subscribe(key, websocket)
    tasks: set[asyncio.Task[None]] = set()

    async def run_author_message(
        text: str, client_message_id: str,
        references: list[dict[str, str]] | None = None,
    ) -> None:
        try:
            await manager.handle_author_message(
                key, text, client_message_id, references=references,
            )
        except Exception as exc:
            if not websocket.closed:
                await websocket.send_json(_protocol_error(str(exc)))

    try:
        async for message in websocket:
            if message.type != WSMsgType.TEXT:
                if message.type == WSMsgType.ERROR:
                    break
                continue
            try:
                frame = json.loads(message.data)
                if not isinstance(frame, dict):
                    raise ValueError("frame must be a JSON object")
                frame_type = frame.get("type")
                if frame_type == "author_message":
                    allowed = {"type", "client_message_id", "text", "references"}
                    extra = set(frame) - allowed
                    if extra:
                        raise ValueError(
                            f"unknown author_message fields: {', '.join(sorted(extra))}"
                        )
                    # Must have at least the legacy 3 keys
                    if not all(k in frame for k in ("type", "client_message_id", "text")):
                        raise ValueError("invalid author_message frame")
                    text = frame["text"]
                    client_message_id = frame["client_message_id"]
                    references = frame.get("references")
                    if not isinstance(text, str) or not isinstance(
                        client_message_id, str
                    ):
                        raise ValueError(
                            "author_message fields must be strings"
                        )
                    if not text.strip() or len(text) > 20_000:
                        raise ValueError(
                            "author message must contain 1-20000 characters"
                        )
                    if references is not None:
                        if not isinstance(references, list) or len(references) > 12:
                            raise ValueError("references must be a list of at most 12 paths")
                        for ref in references:
                            if not isinstance(ref, dict) or set(ref) != {"path"}:
                                raise ValueError("each reference must have only a 'path' key")
                    task = asyncio.create_task(
                        run_author_message(text, client_message_id, references)
                    )
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
                elif frame_type == "resume_from":
                    if set(frame) != {"type", "event_id"}:
                        raise ValueError("invalid resume_from frame")
                    event_id = frame["event_id"]
                    if (
                        not isinstance(event_id, int)
                        or isinstance(event_id, bool)
                        or event_id < 0
                    ):
                        raise ValueError(
                            "event_id must be a non-negative integer"
                        )
                    await manager.replay(key, subscription, event_id)
                elif frame_type == "cancel":
                    if set(frame) != {"type"}:
                        raise ValueError("invalid cancel frame")
                    await manager.cancel(key)
                elif frame_type in {"approve_plan", "execute_plan"}:
                    if set(frame) != {"type", "plan_id", "revision"}:
                        raise ValueError(f"invalid {frame_type} frame")
                    plan_id = frame["plan_id"]
                    revision = frame["revision"]
                    if (
                        not isinstance(plan_id, str)
                        or not plan_id.strip()
                        or not isinstance(revision, int)
                        or isinstance(revision, bool)
                        or revision < 1
                    ):
                        raise ValueError("invalid author plan reference")
                    task = asyncio.create_task(
                        manager.handle_author_action(
                            key, frame_type, plan_id, revision
                        )
                    )
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
                elif frame_type == "tool_approval_decision":
                    if set(frame) != {
                        "type",
                        "approval_id",
                        "decision",
                        "remember",
                    }:
                        raise ValueError(
                            "invalid tool_approval_decision frame"
                        )
                    approval_id = frame["approval_id"]
                    decision = frame["decision"]
                    remember = frame["remember"]
                    if (
                        not isinstance(approval_id, str)
                        or not approval_id.strip()
                        or len(approval_id) > 128
                        or decision not in {"allow", "deny"}
                        or not isinstance(remember, bool)
                    ):
                        raise ValueError("invalid tool approval decision")
                    await manager.resolve_tool_approval(
                        key,
                        approval_id,
                        decision,
                        remember,
                    )
                elif frame_type == "restore_file_version":
                    if set(frame) != {"type", "path", "version_id", "expected_hash"}:
                        raise ValueError("invalid restore_file_version frame")
                    version_path = frame["path"]
                    version_id = frame["version_id"]
                    expected_hash = frame["expected_hash"]
                    task = asyncio.create_task(
                        manager.restore_file_version(
                            key, version_path, version_id, expected_hash
                        )
                    )
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
                else:
                    raise ValueError("unknown editor frame type")
            except (
                json.JSONDecodeError,
                KeyError,
                TypeError,
                ValueError,
                RuntimeError,
            ) as exc:
                await websocket.send_json(_protocol_error(str(exc)))
    finally:
        await subscription.close()
    return websocket


def register_novel_websocket_routes(
    app: web.Application,
) -> None:
    app.router.add_get(
        "/awp/ws/v1/novels/{project_id}/editor/{room}/branches/{branch_id}",
        editor_websocket,
    )
    app.router.add_get(
        "/awp/ws/v1/novels/{project_id}/editor/{room}",
        editor_websocket,
    )


__all__ = [
    "EDITOR_SESSION_MANAGER_KEY",
    "editor_websocket",
    "register_novel_websocket_routes",
]
