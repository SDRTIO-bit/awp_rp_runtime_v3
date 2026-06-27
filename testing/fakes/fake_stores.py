"""In-memory fake store implementations for testing.

Same contracts as SQLite stores, fully functional in memory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ...storage.interfaces import (
    CardStateStore, TurnRecordStore, RoundSnapshotStore,
    ActiveMemoryStore, RagMemoryStore, TraceStore,
    RecallLogStore, RetentionDecisionStore,
    RevisionConflictError, DuplicatePatchError, DuplicateTurnError,
)
from ...contracts.card_state import CardState
from ...contracts.card_state_commit import (
    CardStateCommitRequest, CardStateCommitResult, CardStateCommitStatus,
)
from ...contracts.card_state_patch import validate_patch_operations, PatchOpType
from ...contracts.turn_record import TurnRecord
from ...contracts.round_snapshot import RoundSnapshot
from ...contracts.active_memory import ActiveMemoryRecord, ActiveMemoryEntry, ActiveMemoryStatus
from ...contracts.rag_memory import RagMemoryRecord, RagMemoryEntry, RagMemoryStatus, RagMemoryScope
from ...contracts.memory_commit_plan import MemoryCommitReceipt
from ...contracts.memory_recall_request import MemoryRecallRequest
from ...contracts.memory_recall_result import MemoryRecallResult, RecallHit
from ...contracts.memory_retention_decision import MemoryRetentionResult
from ...contracts.execution_trace import ExecutionTrace


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FakeCardStateStore(CardStateStore):

    def __init__(self):
        self._states: dict[tuple[str, str], CardState] = {}
        self._receipts: dict[str, dict[str, Any]] = {}  # patch_id → receipt

    def initialize(self, card_id: str, session_id: str, greeting: str = "") -> CardState:
        key = (card_id, session_id)
        if key in self._states:
            return self._states[key]
        now = datetime.now(timezone.utc).isoformat()
        state = CardState(card_id=card_id, session_id=session_id, revision=0,
                          created_at=now, updated_at=now)
        self._states[key] = state
        return state

    def load(self, card_id: str, session_id: str) -> CardState | None:
        return self._states.get((card_id, session_id))

    def commit(
        self,
        request: CardStateCommitRequest,
        new_state: CardState,
    ) -> CardStateCommitResult:
        patch = request.patch

        # 1. Duplicate check
        if patch.patch_id in self._receipts:
            r = self._receipts[patch.patch_id]
            return CardStateCommitResult(
                status=CardStateCommitStatus.DUPLICATE_PATCH,
                card_id=patch.card_id, session_id=patch.session_id,
                patch_id=patch.patch_id,
                from_revision=r["from_revision"], to_revision=r["to_revision"],
                trace_id=patch.trace_id,
                error_message="Duplicate patch_id — idempotent replay",
            )

        # 2. Load current
        key = (patch.card_id, patch.session_id)
        current = self._states.get(key)
        if not current:
            return CardStateCommitResult(
                status=CardStateCommitStatus.INTERNAL_ERROR,
                card_id=patch.card_id, session_id=patch.session_id,
                patch_id=patch.patch_id,
                error_message=f"No CardState for {patch.card_id}/{patch.session_id}",
            )

        # 3. Revision check
        if current.revision != request.expected_revision:
            return CardStateCommitResult(
                status=CardStateCommitStatus.REVISION_CONFLICT,
                card_id=patch.card_id, session_id=patch.session_id,
                patch_id=patch.patch_id,
                from_revision=current.revision, to_revision=current.revision,
                trace_id=patch.trace_id,
                error_message=f"Revision conflict: expected {request.expected_revision}, got {current.revision}",
            )

        # 4. Validate all ops
        errors = validate_patch_operations(
            patch.operations,
            current_variables=set(current.variables.keys()),
            current_event_flags=set(current.event_flags.keys()),
            current_stages=list(current.active_stage_ids),
        )
        if errors:
            return CardStateCommitResult(
                status=CardStateCommitStatus.VALIDATION_FAILED,
                card_id=patch.card_id, session_id=patch.session_id,
                patch_id=patch.patch_id,
                from_revision=current.revision, to_revision=current.revision,
                trace_id=patch.trace_id,
                error_message=f"{len(errors)} validation errors",
                validation_errors=[e.to_dict() for e in errors],
            )

        # 5. Apply
        new_revision = current.revision + 1
        new_state.revision = new_revision
        now = datetime.now(timezone.utc).isoformat()
        new_state.updated_at = now
        self._states[key] = new_state

        # 6. Record receipt
        self._receipts[patch.patch_id] = {
            "from_revision": current.revision,
            "to_revision": new_revision,
        }

        return CardStateCommitResult(
            status=CardStateCommitStatus.ACCEPTED,
            card_id=patch.card_id, session_id=patch.session_id,
            patch_id=patch.patch_id,
            from_revision=current.revision, to_revision=new_revision,
            trace_id=patch.trace_id,
        )

    def get_patch_log(self, card_id: str, session_id: str) -> list[dict[str, Any]]:
        return [
            {"patch_id": pid, "from_revision": r["from_revision"], "to_revision": r["to_revision"]}
            for pid, r in self._receipts.items()
        ]


class FakeTurnRecordStore(TurnRecordStore):

    def __init__(self):
        self._records: dict[str, TurnRecord] = {}
        self._by_session: dict[tuple[str, str], list[str]] = {}

    def save(self, record: TurnRecord) -> None:
        if record.turn_id in self._records:
            raise DuplicateTurnError(record.turn_id)
        self._records[record.turn_id] = record
        key = (record.card_id, record.session_id)
        if key not in self._by_session:
            self._by_session[key] = []
        self._by_session[key].append(record.turn_id)

    def load(self, turn_id: str) -> TurnRecord | None:
        return self._records.get(turn_id)

    def get_recent(self, card_id: str, session_id: str, limit: int = 5) -> list[TurnRecord]:
        key = (card_id, session_id)
        turn_ids = self._by_session.get(key, [])
        recent_ids = list(reversed(turn_ids[-limit:]))
        return [self._records[tid] for tid in recent_ids if tid in self._records]

    def get_last_accepted(self, card_id: str, session_id: str) -> TurnRecord | None:
        records = self.get_recent(card_id, session_id, limit=1)
        return records[0] if records else None

    def get_next_turn_index(self, card_id: str, session_id: str) -> int:
        key = (card_id, session_id)
        turn_ids = self._by_session.get(key, [])
        if not turn_ids:
            return 1
        max_idx = max(self._records[tid].turn_index for tid in turn_ids if tid in self._records)
        return max_idx + 1


class FakeRoundSnapshotStore(RoundSnapshotStore):

    def __init__(self):
        self._snapshots: dict[str, RoundSnapshot] = {}

    def save(self, snapshot: RoundSnapshot) -> None:
        self._snapshots[snapshot.snapshot_id] = snapshot

    def load(self, snapshot_id: str) -> RoundSnapshot | None:
        return self._snapshots.get(snapshot_id)


class FakeActiveMemoryStore(ActiveMemoryStore):

    def __init__(self):
        self._memories: dict[tuple[str, str, str], ActiveMemoryEntry] = {}
        self._receipts: dict[tuple[str, str, str], MemoryCommitReceipt] = {}
        self.recall_log: list[MemoryRecallResult] = []

    def get_all(self, card_id: str, session_id: str) -> list[ActiveMemoryEntry]:
        return [
            entry for (cid, sid, _), entry in self._memories.items()
            if cid == card_id and sid == session_id and entry.status == "active"
        ]

    def get_all_records(self, card_id: str, session_id: str) -> list[ActiveMemoryRecord]:
        return [
            entry for (cid, sid, _), entry in self._memories.items()
            if cid == card_id and sid == session_id
        ]

    def upsert(self, card_id: str, session_id: str, entry: ActiveMemoryEntry) -> None:
        self._memories[(card_id, session_id, entry.memory_id)] = entry

    def resolve(self, card_id: str, session_id: str, memory_id: str) -> None:
        self.set_status(card_id, session_id, memory_id, ActiveMemoryStatus.RESOLVED.value)

    def delete(self, card_id: str, session_id: str, memory_id: str) -> None:
        self._memories.pop((card_id, session_id, memory_id), None)

    def get_active_count(self, card_id: str, session_id: str) -> int:
        return len(self.get_all(card_id, session_id))

    def set_status(
        self, card_id: str, session_id: str, memory_id: str, status: str, reason: str = ""
    ) -> None:
        key = (card_id, session_id, memory_id)
        if key in self._memories:
            old = self._memories[key]
            self._memories[key] = old.with_status(status, reason=reason)

    def touch_recall(self, card_id: str, session_id: str, memory_id: str) -> None:
        key = (card_id, session_id, memory_id)
        if key in self._memories:
            old = self._memories[key]
            self._memories[key] = ActiveMemoryRecord(
                **{**old.to_dict(), "recall_count": old.recall_count + 1,
                   "last_recalled_at": _now()}
            )

    def recall(self, card_id: str, session_id: str, request: MemoryRecallRequest) -> MemoryRecallResult:
        records = self.get_all(card_id, session_id)
        stale = {
            ActiveMemoryStatus.RESOLVED.value, ActiveMemoryStatus.EXPIRED.value,
            ActiveMemoryStatus.CONFLICTED.value, ActiveMemoryStatus.SUPERSEDED.value,
            ActiveMemoryStatus.EVICTED.value,
        }
        statuses = set(request.statuses) if request.statuses else {"active"}
        hits, excluded = [], []
        for r in records:
            if r.status not in statuses:
                excluded.append({"memory_id": r.memory_id, "reason": f"status={r.status}"})
                continue
            if request.exclude_stale and r.status in stale:
                excluded.append({"memory_id": r.memory_id, "reason": "stale"})
                continue
            if r.importance < request.min_importance:
                excluded.append({"memory_id": r.memory_id, "reason": "low importance"})
                continue
            if r.confidence < request.min_confidence:
                excluded.append({"memory_id": r.memory_id, "reason": "low confidence"})
                continue
            if request.entity_refs and not set(r.entity_refs) & set(request.entity_refs):
                excluded.append({"memory_id": r.memory_id, "reason": "entity filter miss"})
                continue
            if request.query and request.query.lower() not in r.summary.lower():
                excluded.append({"memory_id": r.memory_id, "reason": "query miss"})
                continue
            hits.append(r)
        hits.sort(key=lambda r: (r.importance, r.confidence, r.recall_count), reverse=True)
        limited = hits[: request.limit]
        hit_objs = [
            RecallHit(
                memory_id=r.memory_id, layer="active",
                score=r.importance, hit_reasons=["active_recall"],
                source_refs=list(r.source_turn_ids), provenance="",
                importance=r.importance, confidence=r.confidence,
                status=r.status, summary=r.summary, content=r.summary,
                entity_refs=list(r.entity_refs),
            )
            for r in limited
        ]
        result = MemoryRecallResult(
            request=request, hits=hit_objs, excluded=excluded,
            ordered_by="importance DESC, confidence DESC, recall_count DESC",
            total_available=len(hits),
        )
        self.recall_log.append(result)
        return result

    def record_receipt(self, receipt: MemoryCommitReceipt) -> None:
        self._receipts[(receipt.card_id, receipt.session_id, receipt.idempotency_key)] = receipt

    def get_receipt_by_idempotency_key(
        self, card_id: str, session_id: str, idempotency_key: str
    ) -> MemoryCommitReceipt | None:
        return self._receipts.get((card_id, session_id, idempotency_key))


class FakeRagMemoryStore(RagMemoryStore):

    def __init__(self):
        self._memories: dict[tuple[str, str, str], RagMemoryEntry] = {}
        self._receipts: dict[tuple[str, str, str], MemoryCommitReceipt] = {}
        self.recall_log: list[MemoryRecallResult] = []

    def save(self, card_id: str, session_id: str, entry: RagMemoryEntry) -> None:
        self._memories[(card_id, session_id, entry.memory_id)] = entry

    def search(self, card_id: str, session_id: str, query: str, limit: int = 10) -> list[RagMemoryEntry]:
        q = (query or "").lower()
        tokens = [t.strip() for t in q.split() if t.strip()] or ([q] if q else [])
        def matches(entry):
            if not tokens:
                return True
            text = (entry.content + " " + entry.summary + " " + " ".join(entry.aliases)).lower()
            return any(tok in text for tok in tokens)
        results = [
            entry for (cid, sid, _), entry in self._memories.items()
            if cid == card_id and sid == session_id and matches(entry)
        ]
        results.sort(key=lambda e: (e.importance, e.confidence), reverse=True)
        return results[:limit]

    def get_by_entity(self, card_id: str, session_id: str, entity: str) -> list[RagMemoryEntry]:
        return [
            entry for (cid, sid, _), entry in self._memories.items()
            if cid == card_id and sid == session_id
            and (entity in entry.entity_refs or entity in entry.aliases)
        ]

    def set_status(
        self, card_id: str, session_id: str, memory_id: str, status: str
    ) -> None:
        key = (card_id, session_id, memory_id)
        if key in self._memories:
            self._memories[key] = self._memories[key].with_status(status)

    def touch_recall(self, card_id: str, session_id: str, memory_id: str) -> None:
        key = (card_id, session_id, memory_id)
        if key in self._memories:
            old = self._memories[key]
            self._memories[key] = RagMemoryRecord(
                **{**old.to_dict(), "recall_count": old.recall_count + 1,
                   "last_recalled_at": _now()}
            )

    def recall(self, card_id: str, session_id: str, request: MemoryRecallRequest) -> MemoryRecallResult:
        stale = {
            RagMemoryStatus.RESOLVED.value, RagMemoryStatus.EXPIRED.value,
            RagMemoryStatus.CONFLICTED.value, RagMemoryStatus.SUPERSEDED.value,
        }
        statuses = set(request.statuses) if request.statuses else {"active"}
        q = (request.query or "").lower()
        hits, excluded = [], []
        for (cid, sid, _), entry in self._memories.items():
            if cid != card_id or sid != session_id:
                continue
            if entry.scope == RagMemoryScope.CARD_GLOBAL.value and entry.card_id != card_id:
                excluded.append({"memory_id": entry.memory_id, "reason": "card_scope_mismatch"})
                continue
            if request.scope and entry.scope != request.scope:
                excluded.append({"memory_id": entry.memory_id, "reason": "scope_mismatch"})
                continue
            if entry.status not in statuses:
                excluded.append({"memory_id": entry.memory_id, "reason": f"status={entry.status}"})
                continue
            if request.exclude_stale and entry.status in stale:
                excluded.append({"memory_id": entry.memory_id, "reason": f"stale:{entry.status}"})
                continue
            if q and not (q in entry.content.lower() or q in entry.summary.lower()
                          or any(q in a.lower() for a in entry.aliases)):
                excluded.append({"memory_id": entry.memory_id, "reason": "query miss"})
                continue
            if request.entity_refs and not (set(entry.entity_refs) | set(entry.aliases)) & set(request.entity_refs):
                excluded.append({"memory_id": entry.memory_id, "reason": "entity filter miss"})
                continue
            if request.event_tags and not set(entry.event_tags) & set(request.event_tags):
                excluded.append({"memory_id": entry.memory_id, "reason": "event_tag miss"})
                continue
            hits.append(entry)
        hits.sort(key=lambda e: (e.importance, e.confidence), reverse=True)
        limited = hits[: request.limit]
        hit_objs = [
            RecallHit(
                memory_id=e.memory_id, layer="rag",
                score=e.importance * 0.6 + e.confidence * 0.4,
                hit_reasons=["active_recall"] if not q else ["fts_match"],
                source_refs=list(e.source_turn_ids), provenance=e.provenance,
                importance=e.importance, confidence=e.confidence,
                status=e.status, summary=e.summary, content=e.content,
                entity_refs=list(e.entity_refs),
            )
            for e in limited
        ]
        result = MemoryRecallResult(
            request=request, hits=hit_objs, excluded=excluded,
            ordered_by="importance DESC, confidence DESC" if not q
            else "fts_match then importance DESC",
            total_available=len(hits),
        )
        self.recall_log.append(result)
        return result

    def record_receipt(self, receipt: MemoryCommitReceipt) -> None:
        self._receipts[(receipt.card_id, receipt.session_id, receipt.idempotency_key)] = receipt

    def get_receipt_by_idempotency_key(
        self, card_id: str, session_id: str, idempotency_key: str
    ) -> MemoryCommitReceipt | None:
        return self._receipts.get((card_id, session_id, idempotency_key))


class FakeTraceStore(TraceStore):

    def __init__(self):
        self._traces: dict[str, ExecutionTrace] = {}
        self._by_turn: dict[str, str] = {}

    def save(self, trace: ExecutionTrace) -> None:
        self._traces[trace.trace_id] = trace
        if trace.turn_id:
            self._by_turn[trace.turn_id] = trace.trace_id

    def load(self, trace_id: str) -> ExecutionTrace | None:
        return self._traces.get(trace_id)

    def get_by_turn(self, turn_id: str) -> ExecutionTrace | None:
        trace_id = self._by_turn.get(turn_id)
        return self._traces.get(trace_id) if trace_id else None


class FakeRecallLogStore(RecallLogStore):

    def __init__(self):
        self._logs: list[MemoryRecallResult] = []

    def log_recall(self, result: MemoryRecallResult) -> None:
        self._logs.append(result)

    def get_recent(self, card_id: str, session_id: str, limit: int = 20) -> list[dict]:
        out = []
        for r in self._logs:
            if r.request.card_id == card_id and r.request.session_id == session_id:
                out.append({"hits": len(r.hits), "excluded": len(r.excluded),
                            "ordered_by": r.ordered_by})
        return out[:limit]


class FakeRetentionDecisionStore(RetentionDecisionStore):

    def __init__(self):
        self._results: list[MemoryRetentionResult] = []

    def log_retention(self, result: MemoryRetentionResult) -> None:
        self._results.append(result)

    def get_by_turn(self, card_id: str, session_id: str, turn_id: str) -> list[dict]:
        out = []
        for r in self._results:
            if r.card_id == card_id and r.session_id == session_id and r.turn_id == turn_id:
                out.extend(d.to_dict() for d in r.decisions)
        return out
