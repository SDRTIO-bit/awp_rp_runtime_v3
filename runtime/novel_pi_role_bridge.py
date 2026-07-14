"""Synchronous Python bridge for dedicated Pi novel role Agent Sessions."""

from __future__ import annotations

import queue
import shutil
import subprocess
import threading
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from ..contracts.novel_pi_protocol import (
    NovelPiFrame,
    NovelPiProtocolError,
    decode_frame,
    encode_frame,
)
from ..contracts.novel_pi_role_protocol import NovelPiRoleResult, NovelPiRoleTask
from .novel_llm_factory import NovelLLMFactory
from .novel_pi_read_service import NovelPiReadService
from .novel_role_context import NovelRoleContext


class NovelPiRoleBridgeError(RuntimeError):
    """Raised when Pi cannot execute a role task; no legacy fallback occurs."""


def _thinking_level(factory: NovelLLMFactory, role: str) -> str:
    thinking = factory.get_thinking_config(role).get("thinking", {})
    if thinking.get("type") == "disabled":
        return "off"
    return str(thinking.get("reasoning_effort", "low"))


def _default_connection_resolver(role: str) -> dict[str, Any]:
    factory = NovelLLMFactory()
    connection = asdict(factory.get_pi_agent_connection())
    connection.pop("api_key", None)
    connection["model"] = factory.get_model(role)
    connection["thinking_level"] = _thinking_level(factory, role)
    connection["max_tokens"] = factory.get_max_tokens(role)
    return connection


class NovelPiRoleBridge:
    """Own one project-bound Role Host and route only read tools to Python."""

    _INIT_TIMEOUT_SECONDS = 15.0
    _TURN_TIMEOUT_SECONDS = 600.0

    def __init__(
        self,
        registry: Any,
        *,
        project_dir: Path,
        project_id: str,
        host_command: list[str] | None = None,
        connection_resolver: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self._registry = registry
        self._project_dir = Path(project_dir).resolve()
        self._project_id = project_id
        self._host_command = host_command or self._default_host_command()
        self._connection_resolver = connection_resolver or _default_connection_resolver
        self._session_root = self._project_dir / ".awp" / "pi-role-sessions"
        self._process: subprocess.Popen[str] | None = None
        self._frames: queue.Queue[str | None] = queue.Queue()
        self._write_lock = threading.Lock()
        self._turn_lock = threading.Lock()
        self._active_request_id = ""
        self.sent_tool_results: list[dict[str, Any]] = []
        self._start()

    @property
    def runtime_name(self) -> str:
        return "PiRoleAgents"

    @property
    def active_request_id(self) -> str:
        return self._active_request_id

    def run(
        self,
        task: NovelPiRoleTask,
        *,
        context: NovelRoleContext,
        on_chunk: Callable[[str], None] | None = None,
    ) -> NovelPiRoleResult:
        if task.project_id != self._project_id or context.project_id != self._project_id:
            raise NovelPiRoleBridgeError("Pi role task violated the project binding")
        with self._turn_lock:
            request_id = uuid.uuid4().hex
            self._active_request_id = request_id
            connection = dict(self._connection_resolver(task.role))
            max_tokens = int(connection.pop("max_tokens", 4000))
            thinking_level = str(connection.pop("thinking_level", "low"))
            payload = task.model_dump()
            payload.update({
                "connection": connection,
                "max_tokens": max_tokens,
                "thinking_level": thinking_level,
            })
            try:
                self._write(NovelPiFrame(
                    kind="role_prompt",
                    request_id=request_id,
                    payload=payload,
                ))
                while True:
                    frame = self._read_frame(timeout_seconds=self._TURN_TIMEOUT_SECONDS)
                    self._assert_request(frame, request_id)
                    if frame.kind == "tool_call":
                        self._reply_read_tool(frame, context)
                    elif frame.kind == "event":
                        event_type = frame.payload.get("type")
                        if event_type == "text_delta" and on_chunk:
                            on_chunk(str(frame.payload.get("text", "")))
                        elif event_type == "cancelled":
                            raise NovelPiRoleBridgeError("Pi novel role task was cancelled")
                    elif frame.kind == "role_end":
                        return NovelPiRoleResult.model_validate(frame.payload)
                    elif frame.kind == "error":
                        raise NovelPiRoleBridgeError(
                            str(frame.payload.get("message", "Pi role host failed"))
                        )
                    else:
                        raise NovelPiRoleBridgeError(
                            f"unexpected Pi role frame during task: {frame.kind}"
                        )
            finally:
                self._active_request_id = ""

    def close_session(self, session_key: str) -> None:
        with self._turn_lock:
            request_id = uuid.uuid4().hex
            self._write(NovelPiFrame(
                kind="close_session",
                request_id=request_id,
                payload={"session_key": session_key},
            ))
            frame = self._read_frame(timeout_seconds=self._INIT_TIMEOUT_SECONDS)
            self._assert_request(frame, request_id)
            if frame.kind == "error":
                raise NovelPiRoleBridgeError(
                    str(frame.payload.get("message", "Pi role session close failed"))
                )
            if frame.kind != "event" or frame.payload.get("type") != "session_closed":
                raise NovelPiRoleBridgeError("Pi role host did not close the requested session")

    def cancel(self, request_id: str = "") -> None:
        target = request_id or self._active_request_id
        if not target or target != self._active_request_id:
            raise NovelPiRoleBridgeError("no matching active Pi role task to cancel")
        self._write(NovelPiFrame(kind="cancel", request_id=target, payload={}))

    def close(self) -> None:
        process = self._process
        self._process = None
        if not process:
            return
        try:
            self._write(
                NovelPiFrame(kind="shutdown", request_id="shutdown", payload={}),
                process=process,
            )
        except NovelPiRoleBridgeError:
            pass
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()

    def _start(self) -> None:
        try:
            process = subprocess.Popen(
                self._host_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as exc:
            raise NovelPiRoleBridgeError(
                f"unable to start Pi role host: {exc}"
            ) from exc
        self._process = process
        threading.Thread(
            target=self._read_stdout,
            args=(process,),
            daemon=True,
        ).start()
        init_id = uuid.uuid4().hex
        try:
            self._write(NovelPiFrame(
                kind="role_init",
                request_id=init_id,
                payload={
                    "project_id": self._project_id,
                    "project_root": str(self._project_dir),
                    "session_root": str(self._session_root),
                },
            ))
            frame = self._read_frame(timeout_seconds=self._INIT_TIMEOUT_SECONDS)
            self._assert_request(frame, init_id)
            if frame.kind == "error":
                raise NovelPiRoleBridgeError(
                    str(frame.payload.get("message", "Pi role host initialization failed"))
                )
            if frame.kind != "event" or frame.payload.get("type") != "ready":
                raise NovelPiRoleBridgeError(
                    "Pi role host did not acknowledge initialization"
                )
        except Exception:
            self.close()
            raise

    def _read_stdout(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for raw in process.stdout:
            self._frames.put(raw.rstrip("\r\n"))
        self._frames.put(None)

    def _read_frame(self, *, timeout_seconds: float) -> NovelPiFrame:
        try:
            raw = self._frames.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            raise NovelPiRoleBridgeError(
                "Pi role host timed out waiting for a response"
            ) from exc
        if raw is None:
            raise NovelPiRoleBridgeError("Pi role host exited unexpectedly")
        try:
            return decode_frame(raw)
        except NovelPiProtocolError as exc:
            raise NovelPiRoleBridgeError(str(exc)) from exc

    def _write(
        self,
        frame: NovelPiFrame,
        *,
        process: subprocess.Popen[str] | None = None,
    ) -> None:
        target = process or self._process
        if not target or target.poll() is not None or target.stdin is None:
            raise NovelPiRoleBridgeError("Pi role host is not running")
        with self._write_lock:
            try:
                target.stdin.write(encode_frame(frame) + "\n")
                target.stdin.flush()
            except OSError as exc:
                raise NovelPiRoleBridgeError(
                    f"unable to write to Pi role host: {exc}"
                ) from exc

    @staticmethod
    def _assert_request(frame: NovelPiFrame, request_id: str) -> None:
        if frame.request_id != request_id:
            raise NovelPiRoleBridgeError(
                f"Pi role host returned frame for unexpected request: {frame.request_id}"
            )

    def _reply_read_tool(
        self,
        frame: NovelPiFrame,
        context: NovelRoleContext,
    ) -> None:
        payload = frame.payload
        tool_call_id = str(payload.get("tool_call_id", ""))
        name = str(payload.get("name", ""))
        arguments = payload.get("arguments", {})
        if not tool_call_id or not isinstance(arguments, dict):
            raise NovelPiRoleBridgeError("Pi role host emitted an invalid tool call")
        try:
            result = NovelPiReadService(context).execute(name, arguments)
            tool_payload = {
                "tool_call_id": tool_call_id,
                "ok": bool(result["ok"]),
                "content": str(result["content"]),
            }
        except Exception as exc:
            tool_payload = {
                "tool_call_id": tool_call_id,
                "ok": False,
                "content": str(exc),
            }
        response = NovelPiFrame(
            kind="tool_result",
            request_id=frame.request_id,
            payload=tool_payload,
        )
        self.sent_tool_results.append(response.model_dump())
        self._write(response)

    @staticmethod
    def _default_host_command() -> list[str]:
        node = shutil.which("node")
        if not node:
            raise NovelPiRoleBridgeError(
                "Node.js >=22.19 is required for Pi novel role agents"
            )
        project_root = Path(__file__).resolve().parent.parent
        return [
            node,
            str(project_root / "agent_harness" / "src" / "novel_role_host.mjs"),
        ]
