"""Python bridge for the project-owned embedded Pi novel-agent host."""

from __future__ import annotations

import queue
import shutil
import subprocess
import threading
import time
import uuid
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
        host_command: list[str] | None = None,
    ):
        self._registry = registry
        self._callbacks = callbacks
        self._project_dir = Path(project_dir).resolve()
        self._project_id = project_id
        self._host_command = host_command or self._default_host_command()
        self._session_dir = self._project_dir / ".awp" / "pi-sessions"
        self._process: subprocess.Popen[str] | None = None
        self._frames: queue.Queue[str | None] = queue.Queue()
        self._write_lock = threading.Lock()
        self._turn_lock = threading.Lock()
        self._active_request_id = ""
        self._session_id = f"pi-editor-{uuid.uuid4().hex}"
        self._turn_counter = 0
        self._current_message_id = ""
        self._current_author_message = ""
        self.sent_tool_results: list[dict[str, Any]] = []
        self._start()

    @property
    def runtime_name(self) -> str:
        return "Pi"

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
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as exc:
            raise NovelPiBridgeError(f"unable to start Pi host: {exc}") from exc
        self._process = process
        threading.Thread(target=self._read_stdout, args=(process,), daemon=True).start()
        connection = NovelLLMFactory().get_pi_agent_connection()
        init_id = uuid.uuid4().hex
        self._write(NovelPiFrame(
            kind="init",
            request_id=init_id,
            payload={
                "project_root": str(self._project_dir),
                "session_dir": str(self._session_dir),
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

    def _read_frame(self, *, timeout_seconds: float) -> NovelPiFrame:
        try:
            raw = self._frames.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            raise NovelPiBridgeError("Pi host timed out waiting for a response") from exc
        if raw is None:
            raise NovelPiBridgeError("Pi host exited unexpectedly")
        try:
            return decode_frame(raw)
        except NovelPiProtocolError as exc:
            raise NovelPiBridgeError(str(exc)) from exc

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
