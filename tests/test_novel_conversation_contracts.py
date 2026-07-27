"""Test the conversation branching, turn, file-reference, work-plan,
mutation, and search-result strict contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from awp_rp_runtime_v3.contracts.novel_conversation import (
    ConversationBranch,
    ConversationEffect,
    EditorWorkPlan,
    EditorWorkPlanItem,
    ProjectFileReference,
    ProjectMutationPreview,
    ProjectMutationReceipt,
    ConversationSearchHit,
    TurnStatus,
    WorkPlanStatus,
)
from awp_rp_runtime_v3.contracts.novel_web_event import NovelWebEvent


# ---------------------------------------------------------------------------
# NovelWebEvent backward-compat
# ---------------------------------------------------------------------------


def test_legacy_web_event_defaults_to_main_branch():
    event = NovelWebEvent.model_validate({
        "event_id": 1,
        "project_id": "p1",
        "room": "book",
        "type": "author_message_saved",
        "payload": {"text": "旧消息"},
        "created_at": "2026-07-27T00:00:00+00:00",
    })
    assert event.branch_id == "main"
    assert event.turn_id is None


def test_web_event_accepts_explicit_branch_and_turn():
    event = NovelWebEvent.model_validate({
        "event_id": 1,
        "project_id": "p1",
        "room": "book",
        "type": "turn_started",
        "payload": {"status": "queued"},
        "created_at": "2026-07-27T00:00:00+00:00",
        "branch_id": "conversation-abc123",
        "turn_id": "turn-xyz789",
    })
    assert event.branch_id == "conversation-abc123"
    assert event.turn_id == "turn-xyz789"


# ---------------------------------------------------------------------------
# ConversationBranch
# ---------------------------------------------------------------------------


def test_branch_id_must_match_pattern():
    valid = ["main", "a", "A", "branch-1", "conv.child_v2"]
    for bid in valid:
        ConversationBranch(
            branch_id=bid,
            project_id="p1",
            room="book",
            title="测试",
            created_at="2026-07-27T00:00:00+00:00",
            updated_at="2026-07-27T00:00:00+00:00",
        )

    invalid = ["", "-bad", ".hidden", "branch with spaces"]
    for bid in invalid:
        with pytest.raises(ValidationError):
            ConversationBranch(
                branch_id=bid,
                project_id="p1",
                room="book",
                title="测试",
                created_at="2026-07-27T00:00:00+00:00",
                updated_at="2026-07-27T00:00:00+00:00",
            )


def test_branch_title_length_bounds():
    ConversationBranch(
        branch_id="main",
        project_id="p1",
        room="book",
        title="A",
        created_at="2026-07-27T00:00:00+00:00",
        updated_at="2026-07-27T00:00:00+00:00",
    )
    ConversationBranch(
        branch_id="main",
        project_id="p1",
        room="book",
        title="A" * 80,
        created_at="2026-07-27T00:00:00+00:00",
        updated_at="2026-07-27T00:00:00+00:00",
    )
    with pytest.raises(ValidationError):
        ConversationBranch(
            branch_id="main",
            project_id="p1",
            room="book",
            title="",
            created_at="2026-07-27T00:00:00+00:00",
            updated_at="2026-07-27T00:00:00+00:00",
        )
    with pytest.raises(ValidationError):
        ConversationBranch(
            branch_id="main",
            project_id="p1",
            room="book",
            title="A" * 81,
            created_at="2026-07-27T00:00:00+00:00",
            updated_at="2026-07-27T00:00:00+00:00",
        )


# ---------------------------------------------------------------------------
# EditorWorkPlan
# ---------------------------------------------------------------------------


def test_work_plan_allows_only_one_in_progress_item():
    with pytest.raises(ValidationError, match="in_progress"):
        EditorWorkPlan(items=[
            EditorWorkPlanItem(id="a", step="读取总纲", status="in_progress"),
            EditorWorkPlanItem(id="b", step="核对人物", status="in_progress"),
        ])


def test_work_plan_item_count_bounds():
    # minimum 1
    with pytest.raises(ValidationError):
        EditorWorkPlan(items=[])
    # 1 item is OK
    EditorWorkPlan(items=[EditorWorkPlanItem(id="a", step="读取", status="pending")])
    # 20 items is OK
    EditorWorkPlan(items=[
        EditorWorkPlanItem(id=str(i), step=f"任务{i}", status="pending")
        for i in range(20)
    ])
    # 21 items rejected
    with pytest.raises(ValidationError):
        EditorWorkPlan(items=[
            EditorWorkPlanItem(id=str(i), step=f"任务{i}", status="pending")
            for i in range(21)
        ])


def test_work_plan_no_duplicate_item_ids():
    with pytest.raises(ValidationError, match="duplicate"):
        EditorWorkPlan(items=[
            EditorWorkPlanItem(id="a", step="读取总纲", status="pending"),
            EditorWorkPlanItem(id="a", step="核对人物", status="pending"),
        ])


# ---------------------------------------------------------------------------
# ProjectFileReference
# ---------------------------------------------------------------------------


def test_file_reference_rejects_parent_escape():
    with pytest.raises(ValidationError):
        ProjectFileReference(path="../outside.md")


def test_file_reference_rejects_absolute_path():
    with pytest.raises(ValidationError):
        ProjectFileReference(path="/etc/passwd")
    with pytest.raises(ValidationError):
        ProjectFileReference(path="C:\\windows\\system32\\config")
    with pytest.raises(ValidationError):
        ProjectFileReference(path="\\\\server\\share\\file")
    with pytest.raises(ValidationError):
        ProjectFileReference(path="D:file.txt")


def test_file_reference_with_optional_hash_and_size():
    ref = ProjectFileReference(
        path="outline.md",
        sha256="a" * 64,
        size_bytes=1024,
    )
    assert ref.path == "outline.md"
    assert ref.sha256 == "a" * 64
    assert ref.size_bytes == 1024


def test_file_reference_without_hash_and_size():
    ref = ProjectFileReference(path="outline.md")
    assert ref.path == "outline.md"
    assert ref.sha256 is None
    assert ref.size_bytes is None


def test_file_reference_rejects_negative_size():
    with pytest.raises(ValidationError):
        ProjectFileReference(path="outline.md", size_bytes=-1)


def test_file_reference_rejects_wrong_hash_length():
    with pytest.raises(ValidationError):
        ProjectFileReference(path="outline.md", sha256="short")


def test_file_reference_posix_style_path():
    ref = ProjectFileReference(path="sub/dir/notes.md")
    assert ref.path == "sub/dir/notes.md"


# ---------------------------------------------------------------------------
# ProjectMutationPreview and ProjectMutationReceipt
# ---------------------------------------------------------------------------


def test_mutation_preview_has_required_fields():
    preview = ProjectMutationPreview(
        path="outline.md",
        operation="edit",
        before_hash="a" * 64,
        after_hash="b" * 64,
        diff="--- a/outline.md\n+++ b/outline.md\n",
    )
    assert preview.path == "outline.md"
    assert preview.operation == "edit"
    assert len(preview.before_hash) == 64
    assert len(preview.after_hash) == 64
    assert "---" in preview.diff


def test_mutation_diff_capped_at_60000():
    diff_ok = "x" * 60_000
    preview = ProjectMutationPreview(
        path="outline.md",
        operation="edit",
        before_hash="a" * 64,
        after_hash="b" * 64,
        diff=diff_ok,
    )
    assert len(preview.diff) == 60_000

    with pytest.raises(ValidationError, match="diff"):
        ProjectMutationPreview(
            path="outline.md",
            operation="edit",
            before_hash="a" * 64,
            after_hash="b" * 64,
            diff="x" * 60_001,
        )


def test_receipt_operation_values():
    valid_ops = ["write", "edit", "restore"]
    for op in valid_ops:
        receipt = ProjectMutationReceipt(
            change_id="chg-1",
            turn_id="turn-1",
            branch_id="main",
            path="outline.md",
            operation=op,
            before_hash="a" * 64,
            after_hash="b" * 64,
            diff="",
            history_version_id="v1",
            created_at="2026-07-27T00:00:00+00:00",
        )
        assert receipt.operation == op

    with pytest.raises(ValidationError):
        ProjectMutationReceipt(
            change_id="chg-1",
            turn_id="turn-1",
            branch_id="main",
            path="outline.md",
            operation="delete",
            before_hash="a" * 64,
            after_hash="b" * 64,
            diff="",
            history_version_id="v1",
            created_at="2026-07-27T00:00:00+00:00",
        )


# ---------------------------------------------------------------------------
# ConversationEffect and ConversationSearchHit
# ---------------------------------------------------------------------------


def test_conversation_effect_requires_all_fields():
    effect = ConversationEffect(
        event_id=42,
        type="project_file_changed",
        summary="修改了 outline.md",
    )
    assert effect.event_id == 42
    assert effect.type == "project_file_changed"


def test_conversation_search_hit_structure():
    hit = ConversationSearchHit(
        event_id=99,
        branch_id="main",
        role="editor",
        excerpt="第三章的冲突设置有问题",
        created_at="2026-07-27T00:00:00+00:00",
    )
    assert hit.event_id == 99
    assert hit.role == "editor"
    assert "冲突" in hit.excerpt
