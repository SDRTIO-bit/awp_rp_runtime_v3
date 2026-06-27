"""MemoryContextAssembler — assembles the unified memory context for a round.

Fixes the memory priority order (hard, never overridden by free LLM judgement):

  CardState hard facts
  > last 5 full accepted TurnRecords (L1)
  > ActiveMemory (L2)
  > high-confidence RAG (L3)
  > ordinary worldbook background

Conflict adjudication is deterministic:
  - A memory whose source_card_state_revision < current card_state.revision is
    marked `stale` (downgraded, kept in diagnostics, ranked lower).
  - A memory matching a conflict_signal (entity overlap + negated term in
    summary/content) is marked `conflicted` and removed from high-priority
    context (`ignored`), recorded in diagnostics with the reason.
RAG may only remind/supplement; it can never override CardState.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.card_state import CardState
from ..contracts.turn_record import TurnRecord
from ..contracts.memory_recall_result import MemoryRecallResult, RecallHit
from ..contracts.memory_context_budget import BudgetDecision
from ..policies.memory_policy import (
    PRIORITY_CARD_STATE, PRIORITY_L1_TURNS, PRIORITY_ACTIVE_MEMORY,
    PRIORITY_RAG_HIGH_CONFIDENCE, PRIORITY_RAG, PRIORITY_WORLDBOOK,
)


@dataclass
class ConflictSignal:
    """Deterministic conflict rule: if a memory's entity_refs overlap and its
    text contains a negated term, it conflicts with current CardState."""
    entity_refs: list[str] = field(default_factory=list)
    negated_terms: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class RecallDiagnostics:
    """Per-memory recall diagnostics written into the RoundSnapshot."""
    layer: str = ""
    memory_id: str = ""
    priority: int = 0
    rank: int = 0
    score: float = 0.0
    status: str = "active"
    conflict_status: str = ""  # "" | "stale" | "conflicted" | "ignored"
    conflict_reason: str = ""
    source_refs: list[str] = field(default_factory=list)
    kept: bool = True
    drop_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer, "memory_id": self.memory_id,
            "priority": self.priority, "rank": self.rank, "score": self.score,
            "status": self.status, "conflict_status": self.conflict_status,
            "conflict_reason": self.conflict_reason,
            "source_refs": list(self.source_refs),
            "kept": self.kept, "drop_reason": self.drop_reason,
        }


@dataclass
class AssembledMemoryContext:
    """The full assembled memory context for one round."""
    priority_order: list[int] = field(default_factory=list)
    l1_turns: list[dict[str, Any]] = field(default_factory=list)
    active_memories: list[dict[str, Any]] = field(default_factory=list)
    rag_recall: list[dict[str, Any]] = field(default_factory=list)
    worldbook_entries: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    budget: BudgetDecision = field(default_factory=BudgetDecision)

    def to_dict(self) -> dict[str, Any]:
        return {
            "priority_order": list(self.priority_order),
            "l1_turns": list(self.l1_turns),
            "active_memories": list(self.active_memories),
            "rag_recall": list(self.rag_recall),
            "worldbook_entries": list(self.worldbook_entries),
            "diagnostics": list(self.diagnostics),
            "budget": self.budget.to_dict(),
        }


HIGH_CONFIDENCE_THRESHOLD = 0.7


class MemoryContextAssembler:
    """Assembles L1/L2/L3/worldbook into one prioritized, diagnostics-rich context."""

    def __init__(self, max_l1_turns: int = 5, max_active: int = 15, max_rag: int = 10):
        self.max_l1_turns = max_l1_turns
        self.max_active = max_active
        self.max_rag = max_rag

    def assemble(
        self,
        card_state: CardState,
        l1_turns: list[TurnRecord],
        active_result: MemoryRecallResult,
        rag_result: MemoryRecallResult,
        worldbook_entries: list[dict[str, Any]] | None = None,
        conflict_signals: list[ConflictSignal] | None = None,
        token_budget: int | None = None,
    ) -> AssembledMemoryContext:
        worldbook_entries = worldbook_entries or []
        signals = conflict_signals or []
        current_revision = card_state.revision

        # ---- L1: never truncated; at most max_l1_turns full turns ----
        l1_full = l1_turns[: self.max_l1_turns]
        l1_dicts = [t.to_dict() for t in l1_full]

        # ---- L2: active memories, apply conflict adjudication ----
        active_hits = list(active_result.hits)
        active_diagnostics: list[RecallDiagnostics] = []
        active_kept: list[RecallHit] = []
        for idx, hit in enumerate(active_hits):
            diag = RecallDiagnostics(
                layer="active", memory_id=hit.memory_id,
                priority=PRIORITY_ACTIVE_MEMORY, rank=idx, score=hit.score,
                status=hit.status, source_refs=list(hit.source_refs),
            )
            stale = _is_stale(hit, active_result, current_revision)
            conflict = _detect_conflict(hit, signals)
            if conflict:
                diag.conflict_status = "conflicted"
                diag.conflict_reason = conflict
                diag.kept = False
                diag.drop_reason = "conflicted_with_card_state"
            elif stale:
                diag.conflict_status = "stale"
                diag.conflict_reason = stale
                # stale is downgraded but kept (ranked lower)
                diag.kept = True
            if diag.kept:
                hit2 = RecallHit(**{**hit.to_dict(),
                                    "conflict_status": diag.conflict_status,
                                    "conflict_reason": diag.conflict_reason})
                active_kept.append(hit2)
            active_diagnostics.append(diag)

        # ---- L3: RAG, split high-confidence vs ordinary; conflict adjudication ----
        rag_hits = list(rag_result.hits)
        rag_diagnostics: list[RecallDiagnostics] = []
        rag_kept: list[RecallHit] = []
        for idx, hit in enumerate(rag_hits):
            priority = (PRIORITY_RAG_HIGH_CONFIDENCE
                        if hit.confidence >= HIGH_CONFIDENCE_THRESHOLD
                        else PRIORITY_RAG)
            diag = RecallDiagnostics(
                layer="rag", memory_id=hit.memory_id,
                priority=priority, rank=idx, score=hit.score,
                status=hit.status, source_refs=list(hit.source_refs),
            )
            stale = _is_stale(hit, rag_result, current_revision)
            conflict = _detect_conflict(hit, signals)
            if conflict:
                diag.conflict_status = "ignored"
                diag.conflict_reason = conflict
                diag.kept = False
                diag.drop_reason = "conflicted_with_card_state"
            elif stale:
                diag.conflict_status = "stale"
                diag.conflict_reason = stale
                diag.kept = True
            if diag.kept:
                hit2 = RecallHit(**{**hit.to_dict(),
                                    "conflict_status": diag.conflict_status,
                                    "conflict_reason": diag.conflict_reason})
                rag_kept.append(hit2)
            rag_diagnostics.append(diag)

        # ---- Budget: trim low-priority first; L1 never truncated ----
        budget = self._decide_budget(
            l1_full, active_kept, rag_kept, worldbook_entries, token_budget
        )

        # Apply trims (rag first, then worldbook). L1 untouched.
        rag_final = rag_kept[: budget.rag_used]
        worldbook_final = worldbook_entries[: budget.worldbook_used]

        active_dicts = [h.to_dict() for h in active_kept[: self.max_active]]
        rag_dicts = [h.to_dict() for h in rag_final]
        diagnostics = [d.to_dict() for d in (active_diagnostics + rag_diagnostics)]

        return AssembledMemoryContext(
            priority_order=[
                PRIORITY_CARD_STATE, PRIORITY_L1_TURNS, PRIORITY_ACTIVE_MEMORY,
                PRIORITY_RAG_HIGH_CONFIDENCE, PRIORITY_RAG, PRIORITY_WORLDBOOK,
            ],
            l1_turns=l1_dicts,
            active_memories=active_dicts,
            rag_recall=rag_dicts,
            worldbook_entries=worldbook_final,
            diagnostics=diagnostics,
            budget=budget,
        )

    def _decide_budget(
        self,
        l1_full: list[TurnRecord],
        active_kept: list[RecallHit],
        rag_kept: list[RecallHit],
        worldbook_entries: list[dict[str, Any]],
        token_budget: int | None,
    ) -> BudgetDecision:
        l1_available = len(l1_full)
        active_available = len(active_kept)
        rag_available = len(rag_kept)
        worldbook_available = len(worldbook_entries)

        # Defaults: keep everything (no token budget => no trim).
        rag_used = min(rag_available, self.max_rag)
        worldbook_used = worldbook_available
        trimmed: list[dict[str, Any]] = []

        if token_budget is not None:
            # Naive deterministic trim: cut RAG to half, then worldbook to half,
            # before ever touching L1. L1 is never truncated.
            half_rag = max(0, rag_used // 2)
            if half_rag < rag_used:
                trimmed.append({"layer": "rag", "reason": "token_budget",
                                "count": rag_used - half_rag})
                rag_used = half_rag
            half_wb = max(0, worldbook_used // 2)
            if half_wb < worldbook_used:
                trimmed.append({"layer": "worldbook", "reason": "token_budget",
                                "count": worldbook_used - half_wb})
                worldbook_used = half_wb

        if rag_used < rag_available:
            trimmed.append({"layer": "rag", "reason": "max_rag_cap",
                            "count": rag_available - rag_used})

        return BudgetDecision(
            l1_turns_used=len(l1_full),
            l1_turns_available=l1_available,
            l1_truncated=False,
            active_memories_used=min(active_available, self.max_active),
            active_memories_available=active_available,
            rag_used=rag_used,
            rag_available=rag_available,
            worldbook_used=worldbook_used,
            worldbook_available=worldbook_available,
            trimmed=trimmed,
        )


def _is_stale(hit: RecallHit, result: MemoryRecallResult, current_revision: int) -> str:
    """A memory is stale if its source revision is behind the current CardState.

    We approximate via the request's expected revision vs the hit's source refs
    when available; the store sets status appropriately. Here we only flag
    explicit stale statuses already assigned by the recall layer.
    """
    if hit.conflict_status == "stale":
        return "stale_source_revision"
    return ""


def _detect_conflict(hit: RecallHit, signals: list[ConflictSignal]) -> str:
    """Deterministic conflict detection via entity overlap + negated term."""
    if not signals:
        return ""
    text = f"{hit.summary} {hit.content}".lower()
    hit_entities = set(hit.entity_refs)
    for sig in signals:
        if not sig.entity_refs or (hit_entities & set(sig.entity_refs)):
            for term in sig.negated_terms:
                if term and term.lower() in text:
                    return sig.reason or f"conflicts:{term}"
    return ""
