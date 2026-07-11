"""Tests for MemoryPolicy."""

import pytest
from awp_rp_runtime_v3.policies.memory_policy import MemoryPolicy
from awp_rp_runtime_v3.contracts.memory_commit_plan import (
    MemoryCommitPlan, ActiveMemoryEntry,
)


class TestMemoryPolicy:
    """Test MemoryPolicy validation rules."""

    def setup_method(self):
        self.policy = MemoryPolicy()

    def test_valid_plan(self):
        plan = MemoryCommitPlan(
            new_active_entries=[
                ActiveMemoryEntry(
                    memory_id="m1",
                    kind="promise",
                    summary="主角向守卫许下黄昏前归还宝剑的承诺，然而日落将至仍未兑现，场面紧张且悬念未解",
                    importance=0.5,
                    source_turn_ids=["t1"],
                    source_card_state_revision=1,
                ),
            ],
        )
        result = self.policy.validate_commit_plan(plan, current_active_count=0)
        assert result.valid

    def test_active_memory_limit(self):
        entries = [
            ActiveMemoryEntry(
                memory_id=f"m{i}",
                kind="promise",
                summary=f"第{i}条剧情记忆，内容足够长以满足下限要求哦",
                importance=0.5,
            )
            for i in range(5)
        ]
        plan = MemoryCommitPlan(new_active_entries=entries)
        # Already have 13, adding 5 would exceed 15
        result = self.policy.validate_commit_plan(plan, current_active_count=13)
        assert not result.valid

    def test_empty_content_invalid(self):
        plan = MemoryCommitPlan(
            new_active_entries=[
                ActiveMemoryEntry(
                    memory_id="m1",
                    kind="promise",
                    summary="",
                    importance=0.5,
                ),
            ],
        )
        result = self.policy.validate_commit_plan(plan, current_active_count=0)
        assert not result.valid

    def test_only_commit_runtime_can_write(self):
        assert self.policy.is_writable_by("active_memory_commit_runtime")
        assert self.policy.is_writable_by("rag_memory_commit_runtime")
        assert self.policy.is_writable_by("MemoryCommitNode")
        assert not self.policy.is_writable_by("writer")
        assert not self.policy.is_writable_by("sub_agent")
