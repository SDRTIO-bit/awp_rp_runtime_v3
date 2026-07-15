"""Shared test fixtures."""

import sys
import types
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root.parent))

# ComfyUI runtime module `comfy_execution.validation` is only available inside a
# running ComfyUI process. Several node/workflow tests exercise its
# `validate_node_input` to check link type compatibility. Provide a faithful
# offline stub when the real module is absent so these tests run under plain
# pytest. The stub honours the AnyType("*") wildcard declared by
# AWPV2TraceDisplay (accepts any received type) and otherwise falls back to
# exact match or membership for union (list/tuple) input declarations.
try:  # pragma: no cover - exercised only inside ComfyUI
    import comfy_execution.validation  # noqa: F401
except ModuleNotFoundError:
    _stub = types.ModuleType("comfy_execution")
    _stub_validation = types.ModuleType("comfy_execution.validation")

    def validate_node_input(received, expected, *args, **kwargs):
        if str(expected) == "*":
            return True
        if isinstance(expected, (list, tuple, set)):
            return any(str(e) == "*" or e == received for e in expected)
        return expected == received

    _stub_validation.validate_node_input = validate_node_input
    _stub.validation = _stub_validation
    sys.modules["comfy_execution"] = _stub
    sys.modules["comfy_execution.validation"] = _stub_validation

import pytest
from awp_rp_runtime_v3.testing.fakes import (
    FakeCardStateStore, FakeTurnRecordStore, FakeActiveMemoryStore,
    FakeRagMemoryStore, FakeTraceStore, FakeLLMProvider,
)
from awp_rp_runtime_v3.contracts.card_state import CardState, VariableEntry, SceneState
from awp_rp_runtime_v3.contracts.novel_pi_role_protocol import NovelPiRoleResult
from awp_rp_runtime_v3.runtime.novel_role_runtime import novel_role_runtime_override


@pytest.fixture
def fake_card_state_store():
    return FakeCardStateStore()

@pytest.fixture
def fake_turn_record_store():
    return FakeTurnRecordStore()

@pytest.fixture
def fake_active_memory_store():
    return FakeActiveMemoryStore()

@pytest.fixture
def fake_rag_memory_store():
    return FakeRagMemoryStore()

@pytest.fixture
def fake_trace_store():
    return FakeTraceStore()

@pytest.fixture
def fake_llm():
    return FakeLLMProvider()


class DeterministicNovelRoleRuntime:
    """Schema-valid Pi role double for tests that exercise the whole engine."""

    runtime_name = "TestPiRoles"

    def __init__(self):
        self.tasks = []
        self.closed_sessions = []

    def run(self, task, *, context, on_chunk=None):
        del context
        self.tasks.append(task)
        text = self._text(task)
        if on_chunk:
            on_chunk(text)
        return NovelPiRoleResult(
            request_id=f"test-role-{len(self.tasks)}",
            role=task.role,
            session_key=task.session_key,
            text=text,
            model="test-pi-model",
        )

    def close_session(self, session_key, **kwargs):
        del kwargs
        self.closed_sessions.append(session_key)

    def _text(self, task):
        if task.role == "architect":
            return json.dumps({
                "chapter_id": f"ch-{task.project_id}-{task.chapter_index}",
                "project_id": task.project_id,
                "chapter_index": task.chapter_index,
                "title": f"第{task.chapter_index}章",
                "target_chars": 300,
                "chapter_position": "progression",
                "target_emotion": "紧张",
                "opening_hook": "人物在冲突中开场",
                "main_payoff": "角色作出新决定",
                "scene_beats": [{
                    "beat_id": f"ch{task.chapter_index}-b1",
                    "description": "角色通过对话推进当前冲突",
                    "function_tag": "推进",
                    "density": "normal",
                    "budget_chars": 300,
                }],
            }, ensure_ascii=False)
        if task.role == "director":
            return json.dumps({
                "beat_details": [{
                    "beat_id": f"ch{task.chapter_index}-b1",
                    "content_outline": "人物围绕具体阻碍展开对话并作出决定",
                }],
                "risk_flags": [],
                "opportunities": [],
            }, ensure_ascii=False)
        if task.role == "writer":
            return (
                "门刚推开，桌边的人就问他为什么现在才来。"
                "他没有解释迟到，只把手里的文件放在两人中间，说名单已经改过一次。"
                "对方翻到最后一页，发现原本空着的位置多了一个名字，于是追问是谁同意的。"
                "走廊里有人经过，他们同时停了一秒，又把声音压低。"
                "争论没有结束，但原先没人肯接的任务终于有了负责人。"
                "他拿回文件时，纸角被对方按出一道折痕；那个人提醒他，明天之前还可以反悔。"
                "他把折痕抹平，说如果真想让他反悔，就不该提前把名字写上去。"
            )
        if task.role == "continuity_checker":
            return json.dumps(
                {"issues": [], "severity": "info", "suggestions": []},
                ensure_ascii=False,
            )
        if task.role == "ledger_curator":
            return json.dumps({
                "chapter_summary": "角色在争论后接下任务，关系与局势向前推进。",
                "ledger_updates": [],
                "ledger_resolves": [],
                "foreshadowing_changes": [],
            }, ensure_ascii=False)
        return str(task.input_payload.get("prompt", ""))


@pytest.fixture
def fake_novel_role_runtime():
    runtime = DeterministicNovelRoleRuntime()
    with novel_role_runtime_override(runtime):
        yield runtime
