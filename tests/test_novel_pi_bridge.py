import json
import sys
from pathlib import Path

import pytest

from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.runtime.novel_brain import BrainCallbacks
from awp_rp_runtime_v3.runtime.novel_pi_bridge import NovelPiBridge, NovelPiBridgeError
from awp_rp_runtime_v3.runtime.session_runtime_registry import SessionRuntimeStoreRegistry
from awp_rp_runtime_v3.storage.sqlite.database import Database


@pytest.fixture
def reg(tmp_path):
    db = Database(str(tmp_path / "novel.db"))
    db.initialize()
    registry = SessionRuntimeStoreRegistry(db)
    registry.novel_project_store.create(NovelProject(project_id="p1", title="测试"))
    return registry


def _write_host(path: Path, mode: str = "normal") -> Path:
    script = path / "fake_host.py"
    script.write_text(
        f'''import json, sys
mode = {mode!r}
for raw in sys.stdin:
    frame = json.loads(raw)
    if frame["kind"] == "init":
        print(json.dumps({{"kind":"event","request_id":frame["request_id"],"payload":{{"type":"ready"}}}}), flush=True)
    elif frame["kind"] == "prompt":
        request_id = frame["request_id"]
        if mode == "malformed":
            print("not-json", flush=True)
        else:
            print(json.dumps({{"kind":"tool_call","request_id":request_id,"payload":{{"tool_call_id":"tool-1","name":"project_status","arguments":{{}}}}}}), flush=True)
    elif frame["kind"] == "tool_result":
        request_id = frame["request_id"]
        print(json.dumps({{"kind":"event","request_id":request_id,"payload":{{"type":"assistant_delta","text":"已检查"}}}}), flush=True)
        print(json.dumps({{"kind":"turn_end","request_id":request_id,"payload":{{"text":"项目状态正常"}}}}), flush=True)
''',
        encoding="utf-8",
    )
    return script


def test_bridge_answers_tool_call_and_forwards_delta(tmp_path, reg):
    chat = []
    host = _write_host(tmp_path)
    bridge = NovelPiBridge(
        reg,
        BrainCallbacks(on_chat=chat.append),
        project_dir=tmp_path,
        project_id="p1",
        host_command=[sys.executable, str(host)],
    )
    try:
        assert bridge.handle_message("看状态") == "项目状态正常"
    finally:
        bridge.close()

    assert chat == ["已检查"]
    assert bridge.sent_tool_results[0]["payload"]["tool_call_id"] == "tool-1"
    journal_files = list((tmp_path / ".awp" / "authoring" / "journal").glob("*.jsonl"))
    assert len(journal_files) == 1
    assert "看状态" in journal_files[0].read_text(encoding="utf-8")


def test_bridge_rejects_malformed_host_frame(tmp_path, reg):
    host = _write_host(tmp_path, mode="malformed")
    bridge = NovelPiBridge(
        reg,
        BrainCallbacks(),
        project_dir=tmp_path,
        project_id="p1",
        host_command=[sys.executable, str(host)],
    )
    try:
        with pytest.raises(NovelPiBridgeError, match="invalid protocol frame"):
            bridge.handle_message("看状态")
    finally:
        bridge.close()
