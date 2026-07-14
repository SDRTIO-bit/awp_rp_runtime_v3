import pytest
from pydantic import ValidationError

from awp_rp_runtime_v3.contracts.novel_pi_role_protocol import (
    NovelPiRoleResult,
    NovelPiRoleTask,
)


def test_role_task_rejects_unknown_role():
    with pytest.raises(ValidationError, match="unsupported Pi novel role"):
        NovelPiRoleTask(
            role="shell",
            project_id="p1",
            chapter_index=1,
            session_key="p1:1:1:shell",
            task_contract="run shell",
            input_payload={},
        )


def test_role_task_rejects_secret_values_in_payload():
    with pytest.raises(ValidationError, match="sensitive key"):
        NovelPiRoleTask(
            role="writer",
            project_id="p1",
            chapter_index=1,
            session_key="p1:1:1:writer",
            task_contract="write beat",
            input_payload={"api_key": "secret-value"},
        )


def test_role_task_round_trip_contains_no_connection_secret():
    task = NovelPiRoleTask(
        role="writer",
        project_id="p1",
        chapter_index=1,
        revision=1,
        phase="beat:0",
        session_key="p1:1:1:writer",
        task_contract="write beat",
        input_payload={"beat_index": 0},
        stream=True,
    )

    restored = NovelPiRoleTask.model_validate_json(task.model_dump_json())

    assert restored == task
    assert "api_key" not in task.model_dump_json().lower()


def test_role_result_requires_matching_supported_role():
    result = NovelPiRoleResult(
        request_id="req-1",
        role="architect",
        session_key="task:1",
        text='{"title": "第一章"}',
        model="kimi-k2.6",
        finish_reason="stop",
    )

    assert result.role == "architect"
    assert result.usage == {}

