import json

from awp_rp_runtime_v2.runtime.execution_dispatcher import ExecutionDispatcher


def _node_result(writer_output: str = "accepted text") -> tuple:
    return (
        {"turn_id": "turn-1"},
        {},
        {"outcome": "success"},
        {},
        {"turn_id": "turn-1", "turn_index": 2, "writer_output": writer_output},
        {},
    )


def test_python_mode_calls_node_directly(monkeypatch):
    calls = {}

    class FakeContinuationNode:
        def execute(self, session_id: str, player_input: str, **kwargs):
            calls["session_id"] = session_id
            calls["player_input"] = player_input
            return _node_result("direct python output")

    from awp_rp_runtime_v2.nodes import persistent_continuation_turn_node

    monkeypatch.setattr(
        persistent_continuation_turn_node,
        "AWPV2PersistentContinuationTurn",
        FakeContinuationNode,
    )

    result = ExecutionDispatcher().execute_turn(
        "session-1",
        "hello",
        mode="python",
    )

    assert calls == {"session_id": "session-1", "player_input": "hello"}
    assert result["success"] is True
    assert result["turn_id"] == "turn-1"
    assert result["writer_output"] == "direct python output"


def test_request_mode_overrides_global(monkeypatch):
    monkeypatch.setenv("AWP_EXECUTION_MODE", "python")
    calls = {}
    dispatcher = ExecutionDispatcher()

    def fake_hybrid(action, session_id, player_input, workflow):
        calls["action"] = action
        calls["session_id"] = session_id
        calls["player_input"] = player_input
        calls["workflow"] = workflow
        return {"success": True, "writer_output": "hybrid"}

    monkeypatch.setattr(dispatcher, "_hybrid", fake_hybrid)

    result = dispatcher.execute_turn(
        "session-1",
        "hello",
        mode="hybrid",
        workflow="custom_flow",
    )

    assert result["writer_output"] == "hybrid"
    assert calls == {
        "action": "turn",
        "session_id": "session-1",
        "player_input": "hello",
        "workflow": "custom_flow",
    }


def test_workflow_param_selects_workflow(monkeypatch):
    dispatcher = ExecutionDispatcher()
    loaded = []
    submitted = {}

    def fake_load_workflow(name):
        loaded.append(name)
        return {
            "1": {
                "class_type": "AWPV2PersistentContinuationTurn",
                "inputs": {"session_id": "", "player_input": ""},
            }
        }

    def fake_submit_and_wait(graph):
        submitted.update(graph["1"]["inputs"])
        return {"success": True}

    monkeypatch.setattr(dispatcher, "_load_workflow", fake_load_workflow)
    monkeypatch.setattr(dispatcher, "_submit_and_wait", fake_submit_and_wait)

    result = dispatcher.execute_turn(
        "session-1",
        "hello",
        mode="hybrid",
        workflow="custom_flow",
    )

    assert result["success"] is True
    assert loaded == ["custom_flow"]
    assert submitted == {"session_id": "session-1", "player_input": "hello"}


def test_extract_turn_result_from_comfy_history_ui_payload():
    projection = {
        "turn_id": "turn-9",
        "turn_index": 4,
        "diagnostic_status": "success",
    }
    history = {
        "outputs": {
            "10": {"ui": {"awp_accepted_text": ["full accepted text"]}},
            "11": {"ui": {"awp_turn_result_json": [json.dumps(projection)]}},
        }
    }

    result = ExecutionDispatcher()._extract_turn_result_from_history(history)

    assert result["success"] is True
    assert result["turn_id"] == "turn-9"
    assert result["turn_index"] == 4
    assert result["writer_output"] == "full accepted text"
