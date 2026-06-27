"""MemoryPolicy — deterministic rules for memory read/write/retention.

Enforces:
- Max 15 active memories per card+session
- Max 5 recent accepted turn records (L1)
- ActiveMemory summary 30-80 Unicode chars
- CardState always wins over memory (priority order fixed)
- No agent can write memory directly (only commit runtimes)
- Deterministic retention/eviction when the 15-slot is full (no random, no LLM)

Priority order (hard, never overridden by free LLM judgement):
  CardState hard facts
  > last 5 full accepted TurnRecords (L1)
  > ActiveMemory (L2)
  > high-confidence RAG (L3)
  > ordinary worldbook background
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts.memory_commit_plan import MemoryCommitPlan
from ..contracts.active_memory import (
    ActiveMemoryRecord, ActiveMemoryKind, ActiveMemoryStatus,
)
from ..contracts.memory_retention_decision import (
    RetentionDecision, RetentionAction, MemoryRetentionResult,
)


@dataclass
class MemoryValidation:
    """Result of memory policy validation."""
    valid: bool
    errors: list[str]


# Memory priority layers (lower number = higher priority). Fixed.
PRIORITY_CARD_STATE = 0
PRIORITY_L1_TURNS = 1
PRIORITY_ACTIVE_MEMORY = 2
PRIORITY_RAG_HIGH_CONFIDENCE = 3
PRIORITY_RAG = 4
PRIORITY_WORLDBOOK = 5

# Kinds that are strongly retained (evicted last).
HIGH_PRIORITY_KINDS = {
    ActiveMemoryKind.PROMISE.value,
    ActiveMemoryKind.RELATIONSHIP_SHIFT.value,
    ActiveMemoryKind.SECRET.value,
    ActiveMemoryKind.MISUNDERSTANDING.value,
    ActiveMemoryKind.PLAYER_GOAL.value,
    ActiveMemoryKind.SCENE_PRESSURE.value,
    ActiveMemoryKind.UNRESOLVED_THREAD.value,
}

# Statuses that are evicted first.
LOW_PRIORITY_STATUSES = {
    ActiveMemoryStatus.RESOLVED.value,
    ActiveMemoryStatus.EXPIRED.value,
    ActiveMemoryStatus.CONFLICTED.value,
    ActiveMemoryStatus.EVICTED.value,
    ActiveMemoryStatus.SUPERSEDED.value,
}


class MemoryPolicy:
    """Policy for memory access and mutation.

    Pure policy — no side effects, no I/O.
    """

    MAX_ACTIVE_MEMORIES = 15
    MAX_RECENT_TURNS = 5
    SUMMARY_MIN_CHARS = 30
    SUMMARY_MAX_CHARS = 80
    MAX_RAG_QUERY_LIMIT = 50

    def validate_commit_plan(
        self,
        plan: MemoryCommitPlan,
        current_active_count: int,
    ) -> MemoryValidation:
        """Validate a memory commit plan (pre-write)."""
        errors: list[str] = []

        # Active memory limit (after applying this plan, before retention).
        # Retention may evict to stay within 15; if even after evicting all
        # resolved/expired the plan would still overflow, it is invalid.
        net_new = len(plan.new_active_entries) - len(plan.resolved_active_ids)
        projected = current_active_count + net_new
        if projected > self.MAX_ACTIVE_MEMORIES:
            # Allowed only if retention can bring it back down to <= 15.
            # Retention evicts LOW_PRIORITY statuses first; if the overflow
            # cannot be absorbed, reject.
            if projected - self.MAX_ACTIVE_MEMORIES > len(plan.new_active_entries):
                errors.append(
                    f"Active memory limit cannot be satisfied: projected {projected} "
                    f"> max {self.MAX_ACTIVE_MEMORIES}"
                )

        for i, entry in enumerate(plan.new_active_entries):
            self._validate_active_entry(entry, prefix=f"New active[{i}]", errors=errors)

        for i, entry in enumerate(plan.updated_active_entries):
            self._validate_active_entry(entry, prefix=f"Updated active[{i}]", errors=errors)

        for i, entry in enumerate(plan.new_rag_entries):
            if not entry.content.strip() and not entry.summary.strip():
                errors.append(f"New RAG[{i}]: content/summary is empty")
            if not entry.memory_id:
                errors.append(f"New RAG[{i}]: memory_id is required")
            if not entry.source_turn_ids:
                errors.append(f"New RAG[{i}]: source_turn_ids is required (no sourceless memory)")

        return MemoryValidation(valid=len(errors) == 0, errors=errors)

    def _validate_active_entry(
        self, entry: ActiveMemoryRecord, prefix: str, errors: list[str]
    ) -> None:
        summary = entry.summary
        if not summary.strip():
            errors.append(f"{prefix}: summary is empty")
        else:
            char_len = len(summary)
            if char_len < self.SUMMARY_MIN_CHARS:
                errors.append(
                    f"{prefix}: summary too short ({char_len} < {self.SUMMARY_MIN_CHARS})"
                )
            if char_len > self.SUMMARY_MAX_CHARS:
                errors.append(
                    f"{prefix}: summary too long ({char_len} > {self.SUMMARY_MAX_CHARS})"
                )
        if not entry.memory_id:
            errors.append(f"{prefix}: memory_id is required")
        if not entry.source_turn_ids:
            errors.append(f"{prefix}: source_turn_ids is required (no sourceless memory)")
        if entry.importance < 0 or entry.importance > 1:
            errors.append(f"{prefix}: importance must be 0-1")
        if entry.confidence < 0 or entry.confidence > 1:
            errors.append(f"{prefix}: confidence must be 0-1")

    def is_writable_by(self, caller: str) -> bool:
        """Check if a caller is allowed to write memory."""
        allowed_writers = {
            "active_memory_commit_runtime",
            "rag_memory_commit_runtime",
            "AWPV2ActiveMemoryCommit",
            "AWPV2RagMemoryCommit",
            "ActiveMemoryCommitNode",
            "RAGMemoryCommitNode",
            "MemoryCommitNode",
        }
        return caller in allowed_writers

    # ------------------------------------------------------------------
    # Deterministic retention / eviction
    # ------------------------------------------------------------------
    def retention_score(self, entry: ActiveMemoryRecord, now_recalled: bool = False) -> float:
        """Higher score = more likely to KEEP. Deterministic, no randomness."""
        score = 0.0

        # Status dominates: low-priority statuses sink to the bottom.
        if entry.status in LOW_PRIORITY_STATUSES:
            score -= 100.0
        elif entry.status == ActiveMemoryStatus.ACTIVE.value:
            score += 10.0

        # Kind priority
        if entry.kind in HIGH_PRIORITY_KINDS:
            score += 20.0

        # Importance & confidence
        score += float(entry.importance) * 10.0
        score += float(entry.confidence) * 5.0

        # Entity binding: memories with entity refs are more actionable
        if entry.entity_refs:
            score += 3.0

        # Recency of recall: long-unrecalled sinks slightly
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
        """Decide which active memories to keep / evict when the slot is full.

        Deterministic: evict lowest-scored first. Never random. Never silent
        LLM overwrite. High-importance unresolved promises are never evicted by
        low-importance new memories.
        """
        combined = list(current_active) + list(new_entries)
        # Score everything
        scored = [
            (self.retention_score(e), idx, e) for idx, e in enumerate(combined)
        ]

        # Sort by score DESC, then by original order (stable) — keep highest.
        scored.sort(key=lambda t: (-t[0], t[1]))

        keep = [t[2] for t in scored[:max_active]]
        evict = [t[2] for t in scored[max_active:]]

        decisions: list[RetentionDecision] = []
        evicted_ids: list[str] = []
        for e in keep:
            decisions.append(RetentionDecision(
                memory_id=e.memory_id, action=RetentionAction.KEEP.value,
                reason="retained: score above eviction line",
                score=self.retention_score(e),
            ))
        for e in evict:
            reason = self._eviction_reason(e)
            decisions.append(RetentionDecision(
                memory_id=e.memory_id, action=RetentionAction.EVICT.value,
                reason=reason, score=self.retention_score(e),
            ))
            evicted_ids.append(e.memory_id)

        return MemoryRetentionResult(
            card_id=card_id, session_id=session_id, turn_id=turn_id,
            decisions=decisions, evicted_ids=evicted_ids,
            final_active_count=len(keep),
        )

    def _eviction_reason(self, entry: ActiveMemoryRecord) -> str:
        if entry.status == ActiveMemoryStatus.RESOLVED.value:
            return "evicted: resolved"
        if entry.status == ActiveMemoryStatus.EXPIRED.value:
            return "evicted: expired"
        if entry.status == ActiveMemoryStatus.CONFLICTED.value:
            return "evicted: conflicts with CardState"
        if entry.status == ActiveMemoryStatus.SUPERSEDED.value:
            return "evicted: superseded"
        if not entry.entity_refs:
            return "evicted: no entity refs"
        if entry.importance <= 0.2:
            return "evicted: low importance"
        if entry.recall_count == 0:
            return "evicted: long unrecalled"
        return "evicted: lowest retention score"
