"""Python bridge for the project-owned embedded Pi novel-agent host."""

from __future__ import annotations

import queue
import re
import shutil
import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..contracts.novel_pi_protocol import (
    NovelPiFrame,
    NovelPiProtocolError,
    decode_frame,
    encode_frame,
)
from .novel_llm_factory import NovelLLMFactory
from .novel_pi_tool_service import NovelPiToolService
from .novel_authoring_service import NovelAuthoringService


class NovelPiBridgeError(RuntimeError):
    """Raised when the local Pi host cannot complete a protocol turn."""


class NovelPiBridge:
    """Own one project-bound Pi host process and route its five tools to Python."""

    _INIT_TIMEOUT_SECONDS = 15.0
    _TURN_TIMEOUT_SECONDS = 600.0

    def __init__(
        self,
        registry,
        callbacks,
        *,
        project_dir: Path,
        project_id: str,
        session_id: str | None = None,
        session_dir: Path | None = None,
        context_seed: str = "",
        host_command: list[str] | None = None,
    ):
        self._registry = registry
        self._callbacks = callbacks
        self._project_dir = Path(project_dir).resolve()
        self._project_id = project_id
        self._context_seed = context_seed
        self._host_command = host_command or self._default_host_command()
        self._session_dir = (
            Path(session_dir).resolve()
            if session_dir is not None
            else (self._project_dir / ".awp" / "pi-sessions").resolve()
        )
        try:
            self._session_dir.relative_to(self._project_dir)
        except ValueError as exc:
            raise ValueError("Pi session directory escaped project root") from exc
        self._process: subprocess.Popen[str] | None = None
        self._frames: queue.Queue[str | None] = queue.Queue()
        self._write_lock = threading.Lock()
        self._turn_lock = threading.Lock()
        self._active_request_id = ""
        self._session_id = session_id or f"pi-editor-{uuid.uuid4().hex}"
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", self._session_id):
            raise ValueError("invalid Pi session id")
        self._turn_counter = 0
        self._current_message_id = ""
        self._current_author_message = ""
        self._stderr_tail: deque[str] = deque(maxlen=80)
        self._stderr_lock = threading.Lock()
        self._stderr_thread: threading.Thread | None = None
        self.sent_tool_results: list[dict[str, Any]] = []
        self._start()

    @property
    def runtime_name(self) -> str:
        return "Pi"

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def session_dir(self) -> Path:
        return self._session_dir

    def handle_message(self, text: str) -> str:
        with self._turn_lock:
            authoring = NovelAuthoringService(
                self._project_dir, self._project_id
            )
            self._turn_counter = authoring.next_turn()
            self._current_author_message = text
            self._current_message_id = authoring.record_author_message(
                text,
                self._session_id,
                self._turn_counter,
            )
            request_id = uuid.uuid4().hex
            self._active_request_id = request_id
            try:
                self._write(NovelPiFrame(
                    kind="prompt", request_id=request_id, payload={"text": text}
                ))
                while True:
                    frame = self._read_frame(timeout_seconds=self._TURN_TIMEOUT_SECONDS)
                    self._assert_request(frame, request_id)
                    if frame.kind == "tool_call":
                        self._reply_to_tool_call(frame, request_id)
                    elif frame.kind == "event":
                        self._forward_event(frame.payload)
                    elif frame.kind == "turn_end":
                        return str(frame.payload.get("text", ""))
                    elif frame.kind == "error":
                        raise NovelPiBridgeError(
                            str(frame.payload.get("message", "Pi host failed"))
                        )
                    else:
                        raise NovelPiBridgeError(f"unexpected Pi frame during turn: {frame.kind}")
            finally:
                self._active_request_id = ""
                self._current_message_id = ""
                self._current_author_message = ""

    def abort(self) -> None:
        request_id = self._active_request_id
        if not request_id:
            raise NovelPiBridgeError("no active Pi prompt to cancel")
        self._write(NovelPiFrame(kind="cancel", request_id=request_id, payload={}))

    def reset(self) -> None:
        """Discard the active process and start a fresh isolated Pi session."""

        self.close()
        self._session_dir = self._project_dir / ".awp" / "pi-sessions" / uuid.uuid4().hex
        self._frames = queue.Queue()
        with self._stderr_lock:
            self._stderr_tail.clear()
        self._start()

    def close(self) -> None:
        process = self._process
        self._process = None
        if not process:
            return
        try:
            self._write(NovelPiFrame(
                kind="shutdown", request_id="shutdown", payload={}
            ), process=process)
        except NovelPiBridgeError:
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
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as exc:
            raise NovelPiBridgeError(f"unable to start Pi host: {exc}") from exc
        self._process = process
        threading.Thread(target=self._read_stdout, args=(process,), daemon=True).start()
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            args=(process,),
            daemon=True,
        )
        self._stderr_thread.start()
        connection = NovelLLMFactory.get_instance().get_pi_agent_connection()
        init_id = uuid.uuid4().hex
        self._write(NovelPiFrame(
            kind="init",
            request_id=init_id,
            payload={
                "project_root": str(self._project_dir),
                "session_dir": str(self._session_dir),
                "context_seed": self._context_seed,
                "connection": asdict(connection),
            },
        ))
        frame = self._read_frame(timeout_seconds=self._INIT_TIMEOUT_SECONDS)
        self._assert_request(frame, init_id)
        if frame.kind != "event" or frame.payload.get("type") != "ready":
            raise NovelPiBridgeError("Pi host did not acknowledge initialization")

    def _read_stdout(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for raw in process.stdout:
            self._frames.put(raw.rstrip("\r\n"))
        self._frames.put(None)

    def _read_stderr(self, process: subprocess.Popen[str]) -> None:
        assert process.stderr is not None
        for raw in process.stderr:
            with self._stderr_lock:
                self._stderr_tail.append(raw.rstrip("\r\n"))

    def _read_frame(self, *, timeout_seconds: float) -> NovelPiFrame:
        try:
            raw = self._frames.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            raise NovelPiBridgeError("Pi host timed out waiting for a response") from exc
        if raw is None:
            process = self._process
            if process is not None:
                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
            stderr_thread = self._stderr_thread
            if stderr_thread is not None:
                stderr_thread.join(timeout=0.2)
            raise NovelPiBridgeError(self._unexpected_exit_message())
        try:
            return decode_frame(raw)
        except NovelPiProtocolError as exc:
            raise NovelPiBridgeError(str(exc)) from exc

    def _unexpected_exit_message(self) -> str:
        with self._stderr_lock:
            diagnostics = "\n".join(self._stderr_tail).strip()
        if len(diagnostics) > 4096:
            diagnostics = diagnostics[-4096:]
        if diagnostics:
            return f"Pi host exited unexpectedly: {diagnostics}"
        return "Pi host exited unexpectedly"

    def _write(self, frame: NovelPiFrame, *, process: subprocess.Popen[str] | None = None) -> None:
        target = process or self._process
        if not target or target.poll() is not None or target.stdin is None:
            raise NovelPiBridgeError("Pi host is not running")
        with self._write_lock:
            target.stdin.write(encode_frame(frame) + "\n")
            target.stdin.flush()

    def _assert_request(self, frame: NovelPiFrame, request_id: str) -> None:
        if frame.request_id != request_id:
            raise NovelPiBridgeError(
                f"Pi host returned frame for unexpected request: {frame.request_id}"
            )

    def _reply_to_tool_call(self, frame: NovelPiFrame, request_id: str) -> None:
        payload = frame.payload
        tool_call_id = str(payload.get("tool_call_id", ""))
        name = str(payload.get("name", ""))
        arguments = payload.get("arguments", {})
        if not tool_call_id or not isinstance(arguments, dict):
            raise NovelPiBridgeError("Pi host emitted an invalid tool call")
        service = NovelPiToolService(
            self._registry,
            project_id=self._project_id,
            project_dir=self._project_dir,
            callbacks=self._callbacks,
            current_turn=self._turn_counter,
            current_message_id=self._current_message_id,
            current_author_message=self._current_author_message,
        )
        try:
            result = service.execute(name, arguments)
            tool_payload = {
                "tool_call_id": tool_call_id,
                "ok": bool(result["ok"]),
                "content": str(result["content"]),
            }
        except Exception as exc:
            tool_payload = {"tool_call_id": tool_call_id, "ok": False, "content": str(exc)}
        response = NovelPiFrame(
            kind="tool_result", request_id=request_id, payload=tool_payload
        )
        self.sent_tool_results.append(response.model_dump())
        self._write(response)

    def _forward_event(self, payload: dict[str, Any]) -> None:
        event_type = payload.get("type")
        if event_type == "assistant_delta":
            callback = getattr(self._callbacks, "on_chat", None)
            if callback:
                callback(str(payload.get("text", "")))
        elif event_type == "pipeline_phase":
            self._callbacks.on_phase(payload["event"], payload["name"], payload.get("data", {}))
        elif event_type == "pipeline_beat":
            self._callbacks.on_beat(payload["event"], int(payload["beat_index"]), payload.get("data", {}))
        elif event_type == "pipeline_chunk":
            self._callbacks.on_chunk(str(payload.get("text", "")))
        elif event_type == "pipeline_error":
            self._callbacks.on_error(str(payload.get("phase", "pi")), str(payload.get("message", "")))

    @staticmethod
    def _default_host_command() -> list[str]:
        node = shutil.which("node")
        if not node:
            raise NovelPiBridgeError("Node.js >=22.19 is required for the Pi novel harness")
        project_root = Path(__file__).resolve().parent.parent
        return [node, str(project_root / "agent_harness" / "src" / "novel_agent_host.mjs")]
