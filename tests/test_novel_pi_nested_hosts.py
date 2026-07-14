from __future__ import annotations

import json
import sys
from pathlib import Path

from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_brain import BrainCallbacks
from awp_rp_runtime_v3.runtime.novel_pi_bridge import NovelPiBridge
from awp_rp_runtime_v3.runtime.novel_pi_role_bridge import NovelPiRoleBridge
from awp_rp_runtime_v3.runtime.novel_role_runtime import (
    PiNovelRoleRuntime,
    novel_role_runtime_override,
)
from awp_rp_runtime_v3.runtime.session_runtime_registry import (
    SessionRuntimeStoreRegistry,
)
from awp_rp_runtime_v3.storage.sqlite.database import Database


TOP_HOST = r'''
import json
import sys

stage = 0
for raw in sys.stdin:
    frame = json.loads(raw)
    kind = frame["kind"]
    request_id = frame["request_id"]
    if kind == "init":
        print(json.dumps({"kind": "event", "request_id": request_id,
                          "payload": {"type": "ready"}}), flush=True)
    elif kind == "prompt":
        print(json.dumps({"kind": "tool_call", "request_id": request_id,
                          "payload": {"tool_call_id": "plan-1", "name": "plan_chapter",
                                      "arguments": {"chapter": 1,
                                                    "task_description": "告白字幕事故"}}}), flush=True)
    elif kind == "tool_result" and stage == 0:
        stage = 1
        print(json.dumps({"kind": "tool_call", "request_id": request_id,
                          "payload": {"tool_call_id": "write-1", "name": "write_chapter",
                                      "arguments": {"chapter": 1}}}), flush=True)
    elif kind == "tool_result" and stage == 1:
        print(json.dumps({"kind": "turn_end", "request_id": request_id,
                          "payload": {"text": "规划与写作均已完成"}}), flush=True)
    elif kind == "shutdown":
        break
'''


ROLE_HOST = r'''
import json
import sys

log_path = sys.argv[1]
writer_text = (
    "“这不是我写给你的。”唐梨一把按住遥控器，字幕却还在往下滚。"
    "陈默看了眼台下举起的手机，问她现在解释还有没有用。"
    "“有用，至少能证明我们两个里面只有一个人疯了。”"
    "“那你先松手。全校现在都觉得疯的是我。”"
    "唐梨没松，反而把他往幕布后面拽了一步。真正的告白对象已经从侧门离开，"
    "留给他们的只有十二年告白词和一排等着看热闹的人。"
)

def role_text(role):
    if role == "architect":
        return json.dumps({
            "chapter_id": "ch-p1-1", "project_id": "p1", "chapter_index": 1,
            "title": "告白字幕停不下来", "target_chars": 120,
            "chapter_position": "opening", "opening_hook": "告白字幕当众失控",
            "main_payoff": "唐梨把陈默拽成临时告白对象",
            "scene_beats": [{"beat_id": "b1", "description": "字幕失控后两人互相甩锅",
                             "function_tag": "喜剧爆点", "density": "dense",
                             "budget_chars": 120}]
        }, ensure_ascii=False)
    if role == "director":
        return json.dumps({"beat_details": [{"beat_id": "b1",
                            "content_outline": "两人用对话争夺遥控器并发现告白对象离场"}],
                           "risk_flags": [], "opportunities": []}, ensure_ascii=False)
    if role == "writer":
        return writer_text
    if role == "continuity_checker":
        return json.dumps({"issues": [], "severity": "info", "suggestions": []},
                          ensure_ascii=False)
    if role == "ledger_curator":
        return json.dumps({"chapter_summary": "唐梨的告白字幕失控，陈默被迫上台救场。",
                           "ledger_updates": [], "ledger_resolves": [],
                           "foreshadowing_changes": []}, ensure_ascii=False)
    return writer_text

for raw in sys.stdin:
    frame = json.loads(raw)
    kind = frame["kind"]
    request_id = frame["request_id"]
    if kind == "role_init":
        print(json.dumps({"schema_version": 1, "kind": "event", "request_id": request_id,
                          "payload": {"type": "ready", "runtime": "fake-role-host"}}),
              flush=True)
    elif kind == "role_prompt":
        payload = frame["payload"]
        role = payload["role"]
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(role + "\n")
        print(json.dumps({"schema_version": 1, "kind": "role_end",
                          "request_id": request_id,
                          "payload": {"request_id": request_id, "role": role,
                                      "session_key": payload["session_key"],
                                      "text": role_text(role), "structured_data": None,
                                      "model": "fake-pi-model", "usage": {},
                                      "finish_reason": "stop", "latency_ms": 1}},
                         ensure_ascii=False), flush=True)
    elif kind == "close_session":
        print(json.dumps({"schema_version": 1, "kind": "event", "request_id": request_id,
                          "payload": {"type": "session_closed"}}), flush=True)
    elif kind == "shutdown":
        break
'''


def _write_script(path: Path, name: str, source: str) -> Path:
    script = path / name
    script.write_text(source, encoding="utf-8")
    return script


def test_top_level_pi_can_plan_and_write_via_separate_role_host(tmp_path):
    db = Database(str(tmp_path / "novel.db"))
    db.initialize()
    registry = SessionRuntimeStoreRegistry(db)
    registry.novel_project_store.create(NovelProject(project_id="p1", title="测试小说"))

    role_log = tmp_path / "roles.log"
    top_script = _write_script(tmp_path, "fake_top_host.py", TOP_HOST)
    role_script = _write_script(tmp_path, "fake_role_host.py", ROLE_HOST)
    role_bridge = NovelPiRoleBridge(
        registry,
        project_dir=tmp_path,
        project_id="p1",
        host_command=[sys.executable, "-u", str(role_script), str(role_log)],
        connection_resolver=lambda role: {
            "provider": "test", "model": f"fake-{role}",
            "base_url": "https://example.invalid/v1", "api_key_env": "TEST_KEY",
            "thinking_level": "low", "max_tokens": 4000,
        },
    )
    role_runtime = PiNovelRoleRuntime(bridge=role_bridge)
    top_bridge = NovelPiBridge(
        registry,
        BrainCallbacks(),
        project_dir=tmp_path,
        project_id="p1",
        host_command=[sys.executable, "-u", str(top_script)],
    )
    try:
        with novel_role_runtime_override(role_runtime):
            result = top_bridge.handle_message("规划并写第一章")
    finally:
        top_bridge.close()
        role_runtime.close()

    roles = role_log.read_text(encoding="utf-8").splitlines()
    assert result == "规划与写作均已完成"
    assert roles == [
        "architect", "director", "writer", "continuity_checker", "ledger_curator"
    ]
    plan = registry.novel_chapter_plan_store.load_by_index("p1", 1)
    assert registry.novel_chapter_draft_store.load_latest(plan.chapter_id)
