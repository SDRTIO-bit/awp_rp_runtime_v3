from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from awp_rp_runtime_v3.contracts.novel_pi_role_protocol import (
    NovelPiRoleResult,
    NovelPiRoleTask,
)
from awp_rp_runtime_v3.runtime.novel_pi_role_bridge import (
    NovelPiRoleBridge,
    NovelPiRoleBridgeError,
)
from awp_rp_runtime_v3.runtime.novel_role_context import NovelRoleContext
from awp_rp_runtime_v3.runtime.novel_role_receipt import build_pi_provider_receipt


FAKE_HOST = r'''
import json
import sys

tool_name = sys.argv[1]
for raw in sys.stdin:
    frame = json.loads(raw)
    kind = frame["kind"]
    request_id = frame["request_id"]
    if kind == "role_init":
        print(json.dumps({"schema_version": 1, "kind": "event", "request_id": request_id,
                          "payload": {"type": "ready", "runtime": "pi-role-agent"}}), flush=True)
    elif kind == "role_prompt":
        print(json.dumps({"schema_version": 1, "kind": "event", "request_id": request_id,
                          "payload": {"type": "text_delta", "text": "正"}}), flush=True)
        if tool_name == "__echo_max_tokens__":
            print(json.dumps({"schema_version": 1, "kind": "role_end", "request_id": request_id,
                              "payload": {"request_id": request_id, "role": "writer",
                                          "session_key": "p1:2:1:writer",
                                          "text": str(frame["payload"]["max_tokens"]),
                                          "structured_data": None, "model": "kimi-k2.6",
                                          "usage": {}, "finish_reason": "stop",
                                          "latency_ms": 1}}), flush=True)
            continue
        print(json.dumps({"schema_version": 1, "kind": "tool_call", "request_id": request_id,
                          "payload": {"tool_call_id": "tc-1", "name": tool_name, "arguments": {}}}), flush=True)
        tool_result = json.loads(sys.stdin.readline())
        content = tool_result["payload"]["content"]
        text = "正文" if tool_result["payload"]["ok"] else content
        print(json.dumps({"schema_version": 1, "kind": "role_end", "request_id": request_id,
                          "payload": {"request_id": request_id, "role": "writer",
                                      "session_key": "p1:2:1:writer", "text": text,
                                      "structured_data": None, "model": "kimi-k2.6",
                                      "usage": {"input": 11, "output": 7, "total": 18},
                                      "finish_reason": "stop", "latency_ms": 9}}), flush=True)
    elif kind == "close_session":
        print(json.dumps({"schema_version": 1, "kind": "event", "request_id": request_id,
                          "payload": {"type": "session_closed"}}), flush=True)
    elif kind == "shutdown":
        break
'''


def _host_command(tmp_path: Path, tool_name: str) -> list[str]:
    script = tmp_path / f"fake_role_host_{tool_name}.py"
    script.write_text(FAKE_HOST, encoding="utf-8")
    return [sys.executable, "-u", str(script), tool_name]


def _connection(_role: str) -> dict[str, object]:
    return {
        "provider": "test",
        "model": "kimi-k2.6",
        "base_url": "https://example.invalid/v1",
        "api_key_env": "TEST_API_KEY",
        "thinking_level": "medium",
        "max_tokens": 4096,
    }


def _task() -> NovelPiRoleTask:
    return NovelPiRoleTask(
        role="writer",
        project_id="p1",
        chapter_index=2,
        revision=1,
        phase="beat:0",
        session_key="p1:2:1:writer",
        task_contract="只输出正文",
        input_payload={"prompt": "写一段"},
        stream=True,
    )


def _context() -> NovelRoleContext:
    return NovelRoleContext(
        registry=SimpleNamespace(),
        project_id="p1",
        chapter_index=2,
        revision=1,
        artifacts={"write_packet": {"beat": "雨中相遇"}},
    )


def test_bridge_routes_project_bound_read_tool_and_streams_chunks(tmp_path):
    chunks: list[str] = []
    bridge = NovelPiRoleBridge(
        SimpleNamespace(),
        project_dir=tmp_path,
        project_id="p1",
        host_command=_host_command(tmp_path, "read_write_packet"),
        connection_resolver=_connection,
    )
    try:
        result = bridge.run(_task(), context=_context(), on_chunk=chunks.append)
    finally:
        bridge.close()

    assert result.text == "正文"
    assert chunks == ["正"]
    assert bridge.sent_tool_results[0]["payload"]["ok"] is True


def test_bridge_refuses_non_read_tool_without_executing_it(tmp_path):
    bridge = NovelPiRoleBridge(
        SimpleNamespace(),
        project_dir=tmp_path,
        project_id="p1",
        host_command=_host_command(tmp_path, "write_chapter"),
        connection_resolver=_connection,
    )
    try:
        result = bridge.run(_task(), context=_context())
    finally:
        bridge.close()

    assert "unsupported Pi role read tool" in result.text
    assert bridge.sent_tool_results[0]["payload"]["ok"] is False


def test_bridge_uses_task_specific_max_tokens_override(tmp_path):
    bridge = NovelPiRoleBridge(
        SimpleNamespace(),
        project_dir=tmp_path,
        project_id="p1",
        host_command=_host_command(tmp_path, "__echo_max_tokens__"),
        connection_resolver=_connection,
    )
    try:
        result = bridge.run(
            _task().model_copy(update={"max_tokens": 7350}),
            context=_context(),
        )
    finally:
        bridge.close()

    assert result.text == "7350"


def test_bridge_never_falls_back_when_role_host_cannot_start(tmp_path):
    with pytest.raises(NovelPiRoleBridgeError, match="unable to start Pi role host"):
        NovelPiRoleBridge(
            SimpleNamespace(),
            project_dir=tmp_path,
            project_id="p1",
            host_command=[str(tmp_path / "missing-pi-role-host")],
            connection_resolver=_connection,
        )


def test_bridge_rejects_context_from_another_project(tmp_path):
    bridge = NovelPiRoleBridge(
        SimpleNamespace(),
        project_dir=tmp_path,
        project_id="p1",
        host_command=_host_command(tmp_path, "read_write_packet"),
        connection_resolver=_connection,
    )
    wrong = NovelRoleContext(
        registry=SimpleNamespace(), project_id="p2", chapter_index=2
    )
    try:
        with pytest.raises(NovelPiRoleBridgeError, match="project binding"):
            bridge.run(_task(), context=wrong)
    finally:
        bridge.close()


def test_pi_receipt_contains_usage_but_not_prompt_or_secret():
    result = NovelPiRoleResult(
        request_id="req-1",
        role="writer",
        session_key="p1:2:1:writer",
        text="秘密正文",
        model="kimi-k2.6",
        usage={"input": 11, "output": 7, "total": 18},
        finish_reason="stop",
        latency_ms=9,
    )

    receipt = build_pi_provider_receipt(result).to_dict()
    serialized = repr(receipt)
    assert receipt["success"] is True
    assert receipt["usage"]["total_tokens"] == 18
    assert "秘密正文" not in serialized
    assert "api_key" not in serialized.lower()
