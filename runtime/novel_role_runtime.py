"""Runtime router for Pi-backed or explicitly selected legacy novel roles."""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Callable, Iterator

from ..contracts.novel_pi_role_protocol import NovelPiRoleResult, NovelPiRoleTask
from .novel_llm_factory import NovelLLMFactory
from .novel_pi_role_bridge import NovelPiRoleBridge
from .novel_role_context import NovelRoleContext


class PiNovelRoleRuntime:
    """Route role tasks into project-bound Pi Agent Sessions."""

    runtime_name = "PiRoles"

    def __init__(
        self,
        *,
        bridge: Any | None = None,
        bridge_factory: Callable[..., Any] = NovelPiRoleBridge,
    ) -> None:
        self._injected_bridge = bridge
        self._bridge_factory = bridge_factory
        self._bridges: dict[tuple[int, str, str], Any] = {}

    def run(
        self,
        task: NovelPiRoleTask,
        *,
        context: NovelRoleContext,
        on_chunk: Callable[[str], None] | None = None,
    ) -> NovelPiRoleResult:
        return self._bridge_for(context).run(
            task,
            context=context,
            on_chunk=on_chunk,
        )

    def close_session(
        self,
        session_key: str,
        *,
        context: NovelRoleContext | None = None,
    ) -> None:
        if self._injected_bridge is not None:
            self._injected_bridge.close_session(session_key)
            return
        if context is None:
            raise ValueError("context is required to close a project Pi role session")
        self._bridge_for(context).close_session(session_key)

    def cancel(self, request_id: str = "") -> None:
        bridges = (
            [self._injected_bridge]
            if self._injected_bridge is not None
            else list(self._bridges.values())
        )
        for bridge in bridges:
            if bridge is not None and (not request_id or bridge.active_request_id == request_id):
                bridge.cancel(request_id)
                return
        raise RuntimeError("no active Pi novel role task to cancel")

    def close(self) -> None:
        if self._injected_bridge is not None:
            self._injected_bridge.close()
            return
        for bridge in self._bridges.values():
            bridge.close()
        self._bridges.clear()

    def _bridge_for(self, context: NovelRoleContext):
        if self._injected_bridge is not None:
            return self._injected_bridge
        project_dir = self._project_dir(context)
        key = (id(context.registry), context.project_id, str(project_dir))
        bridge = self._bridges.get(key)
        if bridge is None:
            bridge = self._bridge_factory(
                context.registry,
                project_dir=project_dir,
                project_id=context.project_id,
            )
            self._bridges[key] = bridge
        return bridge

    @staticmethod
    def _project_dir(context: NovelRoleContext) -> Path:
        explicit = context.artifacts.get("project_dir")
        if explicit:
            return Path(explicit).resolve()
        db = getattr(context.registry, "db", None)
        db_path = getattr(db, "db_path", "")
        if db_path and db_path != ":memory:":
            return Path(db_path).resolve().parent
        raise RuntimeError(
            "Pi novel roles require a file-backed project directory in the role context"
        )


class LegacyNovelRoleRuntime:
    """Explicit compatibility boundary for the former one-shot LLM adapters."""

    runtime_name = "LegacyRoles"

    def __init__(self, *, llm_factory: NovelLLMFactory | None = None) -> None:
        self._llm_factory = llm_factory or NovelLLMFactory()

    def run(
        self,
        task: NovelPiRoleTask,
        *,
        context: NovelRoleContext,
        on_chunk: Callable[[str], None] | None = None,
    ) -> NovelPiRoleResult:
        del context
        adapter = self._llm_factory.get_adapter(task.role)
        prompt = str(task.input_payload.get("prompt") or json.dumps(
            task.input_payload,
            ensure_ascii=False,
        ))
        common = {
            "max_tokens": self._llm_factory.get_max_tokens(task.role),
            "provider_role": task.role,
            "model": self._llm_factory.get_model(task.role),
            "extra_body": self._llm_factory.get_thinking_config(task.role),
            "system_prompt": task.task_contract,
        }
        request_id = uuid.uuid4().hex
        receipt = None
        if on_chunk is not None and hasattr(adapter, "generate_text_stream"):
            text = adapter.generate_text_stream(prompt, on_chunk, **common)
        else:
            text, receipt = adapter.generate_text(prompt=prompt, **common)
        usage_source = getattr(receipt, "usage", {}) if receipt is not None else {}
        usage = dict(usage_source or {})
        return NovelPiRoleResult(
            request_id=getattr(receipt, "provider_request_id", request_id),
            role=task.role,
            session_key=task.session_key,
            text=text,
            model=getattr(receipt, "model", common["model"]),
            usage={
                "input": int(usage.get("prompt_tokens", 0)),
                "output": int(usage.get("completion_tokens", 0)),
                "total": int(usage.get("total_tokens", 0)),
            },
            finish_reason="legacy",
            latency_ms=int(getattr(receipt, "latency_ms", 0)),
        )

    def close_session(self, session_key: str, **_: Any) -> None:
        del session_key

    def cancel(self, request_id: str = "") -> None:
        del request_id
        raise RuntimeError("Legacy novel role calls do not support cancellation")

    def close(self) -> None:
        return None


def create_novel_role_runtime(
    *,
    llm_factory: NovelLLMFactory | None = None,
    bridge: Any | None = None,
    bridge_factory: Callable[..., Any] = NovelPiRoleBridge,
):
    """Select Pi by default; legacy mode must be explicitly requested."""

    mode = os.environ.get("NOVEL_AGENT_RUNTIME", "pi").lower()
    if mode == "pi":
        return PiNovelRoleRuntime(
            bridge=bridge,
            bridge_factory=bridge_factory,
        )
    if mode == "legacy":
        return LegacyNovelRoleRuntime(llm_factory=llm_factory)
    raise ValueError(f"Unsupported NOVEL_AGENT_RUNTIME: {mode}")


_OVERRIDE: ContextVar[Any | None] = ContextVar(
    "novel_role_runtime_override",
    default=None,
)
_DEFAULT_RUNTIME: Any | None = None
_DEFAULT_MODE = ""


def get_novel_role_runtime():
    """Return the current shared role runtime without silently changing modes."""

    override = _OVERRIDE.get()
    if override is not None:
        return override
    global _DEFAULT_RUNTIME, _DEFAULT_MODE
    mode = os.environ.get("NOVEL_AGENT_RUNTIME", "pi").lower()
    if _DEFAULT_RUNTIME is None or _DEFAULT_MODE != mode:
        if _DEFAULT_RUNTIME is not None:
            _DEFAULT_RUNTIME.close()
        _DEFAULT_RUNTIME = create_novel_role_runtime()
        _DEFAULT_MODE = mode
    return _DEFAULT_RUNTIME


@contextmanager
def novel_role_runtime_override(runtime: Any) -> Iterator[Any]:
    """Temporarily inject a recording/fake role runtime in adapter tests."""

    token = _OVERRIDE.set(runtime)
    try:
        yield runtime
    finally:
        _OVERRIDE.reset(token)


def close_novel_role_runtime() -> None:
    global _DEFAULT_RUNTIME, _DEFAULT_MODE
    if _DEFAULT_RUNTIME is not None:
        _DEFAULT_RUNTIME.close()
    _DEFAULT_RUNTIME = None
    _DEFAULT_MODE = ""
