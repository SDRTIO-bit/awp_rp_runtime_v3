"""Deterministic retention rules for novel Active/RAG memory."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.active_memory import (
    ActiveMemoryKind,
    ActiveMemoryRecord,
    ActiveMemoryStatus,
)
from ..contracts.memory_commit_plan import MemoryCommitPlan
from ..contracts.memory_retention_decision import (
    MemoryRetentionResult,
    RetentionAction,
    RetentionDecision,
)


@dataclass
class MemoryValidation:
    valid: bool
    errors: list[str]


_HIGH_PRIORITY_KINDS = {
    ActiveMemoryKind.PROMISE.value,
    ActiveMemoryKind.RELATIONSHIP_SHIFT.value,
    ActiveMemoryKind.SECRET.value,
    ActiveMemoryKind.MISUNDERSTANDING.value,
    ActiveMemoryKind.PLAYER_GOAL.value,
    ActiveMemoryKind.SCENE_PRESSURE.value,
    ActiveMemoryKind.UNRESOLVED_THREAD.value,
}
_LOW_PRIORITY_STATUSES = {
    ActiveMemoryStatus.RESOLVED.value,
    ActiveMemoryStatus.EXPIRED.value,
    ActiveMemoryStatus.CONFLICTED.value,
    ActiveMemoryStatus.EVICTED.value,
    ActiveMemoryStatus.SUPERSEDED.value,
}


class NovelMemoryPolicy:
    """Pure policy object; all persistence remains in commit runtimes."""

    MAX_ACTIVE_MEMORIES = 15
    SUMMARY_MIN_CHARS = 30
    SUMMARY_MAX_CHARS = 80

    def validate_commit_plan(
        self, plan: MemoryCommitPlan, current_active_count: int
    ) -> MemoryValidation:
        errors: list[str] = []
        projected = (
            current_active_count
            + len(plan.new_active_entries)
            - len(plan.resolved_active_ids)
        )
        if (
            projected > self.MAX_ACTIVE_MEMORIES
            and projected - self.MAX_ACTIVE_MEMORIES
            > len(plan.new_active_entries)
        ):
            errors.append(
                f"Active memory limit cannot be satisfied: projected {projected} "
                f"> max {self.MAX_ACTIVE_MEMORIES}"
            )
        for index, entry in enumerate(plan.new_active_entries):
            self._validate_active(entry, f"New active[{index}]", errors)
        for index, entry in enumerate(plan.updated_active_entries):
            self._validate_active(entry, f"Updated active[{index}]", errors)
        for index, entry in enumerate(plan.new_rag_entries):
            if not entry.content.strip() and not entry.summary.strip():
                errors.append(f"New RAG[{index}]: content/summary is empty")
            if not entry.memory_id:
                errors.append(f"New RAG[{index}]: memory_id is required")
            if not entry.source_turn_ids:
                errors.append(
                    f"New RAG[{index}]: source_turn_ids is required "
                    "(no sourceless memory)"
                )
        return MemoryValidation(valid=not errors, errors=errors)

    def _validate_active(
        self, entry: ActiveMemoryRecord, prefix: str, errors: list[str]
    ) -> None:
        length = len(entry.summary)
        if not entry.summary.strip():
            errors.append(f"{prefix}: summary is empty")
        elif length < self.SUMMARY_MIN_CHARS:
            errors.append(
                f"{prefix}: summary too short "
                f"({length} < {self.SUMMARY_MIN_CHARS})"
            )
        elif length > self.SUMMARY_MAX_CHARS:
            errors.append(
                f"{prefix}: summary too long "
                f"({length} > {self.SUMMARY_MAX_CHARS})"
            )
        if not entry.memory_id:
            errors.append(f"{prefix}: memory_id is required")
        if not entry.source_turn_ids:
            errors.append(f"{prefix}: source_turn_ids is required (no sourceless memory)")
        if not 0 <= entry.importance <= 1:
            errors.append(f"{prefix}: importance must be 0-1")
        if not 0 <= entry.confidence <= 1:
            errors.append(f"{prefix}: confidence must be 0-1")

    def retention_score(self, entry: ActiveMemoryRecord) -> float:
        score = -100.0 if entry.status in _LOW_PRIORITY_STATUSES else 0.0
        if entry.status == ActiveMemoryStatus.ACTIVE.value:
            score += 10.0
        if entry.kind in _HIGH_PRIORITY_KINDS:
            score += 20.0
        score += float(entry.importance) * 10.0
        score += float(entry.confidence) * 5.0
        if entry.entity_refs:
            score += 3.0
        if entry.recall_count == 0:
            score -= 2.0
        return score

    def decide_retention(
        self,
        current_active: list[ActiveMemoryRecord],
        new_entries: list[ActiveMemoryRecord],
        card_id: str,
        session_id: str,
        turn_id: str = "",
        max_active: int = 15,
    ) -> MemoryRetentionResult:
        combined = [*current_active, *new_entries]
        ranked = sorted(
            (
                (self.retention_score(entry), index, entry)
                for index, entry in enumerate(combined)
            ),
            key=lambda item: (-item[0], item[1]),
        )
        kept = [item[2] for item in ranked[:max_active]]
        evicted = [item[2] for item in ranked[max_active:]]
        decisions = [
            RetentionDecision(
                memory_id=entry.memory_id,
                action=RetentionAction.KEEP.value,
                reason="retained: score above eviction line",
                score=self.retention_score(entry),
            )
            for entry in kept
        ]
        decisions.extend(
            RetentionDecision(
                memory_id=entry.memory_id,
                action=RetentionAction.EVICT.value,
                reason="evicted: lowest retention score",
                score=self.retention_score(entry),
            )
            for entry in evicted
        )
        return MemoryRetentionResult(
            card_id=card_id,
            session_id=session_id,
            turn_id=turn_id,
            decisions=decisions,
            evicted_ids=[entry.memory_id for entry in evicted],
            final_active_count=len(kept),
        )


# Compatibility alias within retained shared commit runtimes.
MemoryPolicy = NovelMemoryPolicy

__all__ = ["MemoryPolicy", "MemoryValidation", "NovelMemoryPolicy"]
