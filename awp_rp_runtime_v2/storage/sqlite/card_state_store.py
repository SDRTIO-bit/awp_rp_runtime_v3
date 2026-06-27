"""SQLite CardStateStore with atomic commit.

Revision check + patch receipt + state write all in one transaction.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..interfaces import CardStateStore, RevisionConflictError, DuplicatePatchError
from ...contracts.card_state import CardState
from ...contracts.card_state_commit import (
    CardStateCommitRequest, CardStateCommitResult, CardStateCommitStatus,
)
from ...contracts.card_state_patch import validate_patch_operations, PatchOpType
from .database import Database


class SqliteCardStateStore(CardStateStore):
    """SQLite-backed CardState store with atomic commits."""

    def __init__(self, db: Database):
        self.db = db

    def initialize(self, card_id: str, session_id: str, greeting: str = "") -> CardState:
        conn = self.db.connect()
        row = conn.execute(
            "SELECT state_json FROM card_states WHERE card_id=? AND session_id=?",
            (card_id, session_id),
        ).fetchone()

        if row:
            return CardState.from_dict(json.loads(row["state_json"]))

        now = datetime.now(timezone.utc).isoformat()
        state = CardState(card_id=card_id, session_id=session_id, revision=0,
                          created_at=now, updated_at=now)
        conn.execute(
            "INSERT INTO card_states (card_id, session_id, state_json, revision, created_at, updated_at) "
            "VALUES (?, ?, ?, 0, ?, ?)",
            (card_id, session_id, json.dumps(state.to_dict()), now, now),
        )
        conn.commit()
        return state

    def load(self, card_id: str, session_id: str) -> CardState | None:
        conn = self.db.connect()
        row = conn.execute(
            "SELECT state_json FROM card_states WHERE card_id=? AND session_id=?",
            (card_id, session_id),
        ).fetchone()
        if not row:
            return None
        return CardState.from_dict(json.loads(row["state_json"]))

    def commit(
        self,
        request: CardStateCommitRequest,
        new_state: CardState,
    ) -> CardStateCommitResult:
        """Atomic commit: validate → write state → write receipt, all in one tx."""
        patch = request.patch
        conn = self.db.connect()

        try:
            # Begin transaction (sqlite3 auto-manages, but we use explicit try/except)
            # 1. Check duplicate patch
            existing = conn.execute(
                "SELECT patch_id FROM card_state_patch_receipts WHERE patch_id=?",
                (patch.patch_id,),
            ).fetchone()
            if existing:
                # Idempotent: return original result
                receipt = conn.execute(
                    "SELECT from_revision, to_revision FROM card_state_patch_receipts WHERE patch_id=?",
                    (patch.patch_id,),
                ).fetchone()
                return CardStateCommitResult(
                    status=CardStateCommitStatus.DUPLICATE_PATCH,
                    card_id=patch.card_id,
                    session_id=patch.session_id,
                    patch_id=patch.patch_id,
                    from_revision=receipt["from_revision"] if receipt else 0,
                    to_revision=receipt["to_revision"] if receipt else 0,
                    trace_id=patch.trace_id,
                    error_message="Duplicate patch_id — idempotent replay, no revision change",
                )

            # 2. Load current state
            row = conn.execute(
                "SELECT state_json, revision FROM card_states WHERE card_id=? AND session_id=?",
                (patch.card_id, patch.session_id),
            ).fetchone()
            if not row:
                return CardStateCommitResult(
                    status=CardStateCommitStatus.INTERNAL_ERROR,
                    card_id=patch.card_id,
                    session_id=patch.session_id,
                    patch_id=patch.patch_id,
                    error_message=f"No CardState for {patch.card_id}/{patch.session_id}",
                )

            current_state = CardState.from_dict(json.loads(row["state_json"]))
            current_revision = row["revision"]

            # 3. Revision check
            if current_revision != request.expected_revision:
                return CardStateCommitResult(
                    status=CardStateCommitStatus.REVISION_CONFLICT,
                    card_id=patch.card_id,
                    session_id=patch.session_id,
                    patch_id=patch.patch_id,
                    from_revision=current_revision,
                    to_revision=current_revision,
                    trace_id=patch.trace_id,
                    error_message=f"Revision conflict: expected {request.expected_revision}, got {current_revision}",
                )

            # 4. Validate all operations
            errors = validate_patch_operations(
                patch.operations,
                current_variables=set(current_state.variables.keys()),
                current_event_flags=set(current_state.event_flags.keys()),
                current_stages=list(current_state.active_stage_ids),
            )
            if errors:
                return CardStateCommitResult(
                    status=CardStateCommitStatus.VALIDATION_FAILED,
                    card_id=patch.card_id,
                    session_id=patch.session_id,
                    patch_id=patch.patch_id,
                    from_revision=current_revision,
                    to_revision=current_revision,
                    trace_id=patch.trace_id,
                    error_message=f"{len(errors)} validation errors",
                    validation_errors=[e.to_dict() for e in errors],
                )

            # 5. Apply operations
            new_revision = current_revision + 1
            new_state.revision = new_revision
            now = datetime.now(timezone.utc).isoformat()
            new_state.updated_at = now

            # 6. Write new state
            conn.execute(
                "UPDATE card_states SET state_json=?, revision=?, updated_at=? "
                "WHERE card_id=? AND session_id=?",
                (json.dumps(new_state.to_dict()), new_revision, now,
                 patch.card_id, patch.session_id),
            )

            # 7. Write patch receipt (same transaction)
            conn.execute(
                "INSERT INTO card_state_patch_receipts "
                "(patch_id, card_id, session_id, from_revision, to_revision, operations_json, trace_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (patch.patch_id, patch.card_id, patch.session_id,
                 current_revision, new_revision,
                 json.dumps([op.to_dict() for op in patch.operations]),
                 patch.trace_id),
            )

            conn.commit()

            return CardStateCommitResult(
                status=CardStateCommitStatus.ACCEPTED,
                card_id=patch.card_id,
                session_id=patch.session_id,
                patch_id=patch.patch_id,
                from_revision=current_revision,
                to_revision=new_revision,
                trace_id=patch.trace_id,
            )

        except Exception as e:
            conn.rollback()
            return CardStateCommitResult(
                status=CardStateCommitStatus.INTERNAL_ERROR,
                card_id=patch.card_id,
                session_id=patch.session_id,
                patch_id=patch.patch_id,
                trace_id=patch.trace_id,
                error_message=str(e),
            )

    def get_patch_log(self, card_id: str, session_id: str) -> list[dict[str, Any]]:
        conn = self.db.connect()
        rows = conn.execute(
            "SELECT patch_id, from_revision, to_revision, operations_json, trace_id, applied_at "
            "FROM card_state_patch_receipts WHERE card_id=? AND session_id=? ORDER BY applied_at",
            (card_id, session_id),
        ).fetchall()
        return [
            {
                "patch_id": r["patch_id"],
                "from_revision": r["from_revision"],
                "to_revision": r["to_revision"],
                "operations": json.loads(r["operations_json"]),
                "trace_id": r["trace_id"],
                "applied_at": r["applied_at"],
            }
            for r in rows
        ]
