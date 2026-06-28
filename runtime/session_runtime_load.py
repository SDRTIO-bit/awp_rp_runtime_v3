"""SessionRuntimeLoad — restores L0/L1/L2/L3 from persistent stores.

Given a sessionId, loads:
  L0: CardSessionBinding + CardState + OpeningRecord + WorldbookBinding
  L1: Recent accepted TurnRecords (up to max_turn_history)
  L2: ActiveMemory recall
  L3: RagMemory recall

Uses the canonical RoundSnapshotBuilder for L1/L2/L3 assembly.
Returns a SessionRuntimeBundle with all loaded data + the RoundSnapshot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.card_state import CardState
from ..contracts.card_session_binding import CardSessionBinding
from ..contracts.opening_record import OpeningRecord
from ..contracts.worldbook_binding import WorldbookBinding
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.turn_record import TurnRecord

from .session_runtime_registry import SessionRuntimeStoreRegistry
from .round_snapshot_builder import RoundSnapshotBuilder


@dataclass
class SessionRuntimeBundle:
    """All data loaded from persistent stores for a single turn execution.

    Contains the L0 bootstrap data and the canonical RoundSnapshot
    built from L1/L2/L3.
    """

    # L0: session bootstrap
    card_session_binding: CardSessionBinding | None = None
    card_state: CardState | None = None
    opening_record: OpeningRecord | None = None
    worldbook_binding: WorldbookBinding | None = None

    # Canonical RoundSnapshot (built by RoundSnapshotBuilder)
    round_snapshot: RoundSnapshot | None = None

    # Diagnostics
    l1_turn_count: int = 0
    l2_active_memory_count: int = 0
    l3_rag_recall_count: int = 0
    load_errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """All L0 entities loaded successfully."""
        return (
            self.card_session_binding is not None
            and self.card_state is not None
            and self.opening_record is not None
            and self.worldbook_binding is not None
            and len(self.load_errors) == 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "card_session_binding": self.card_session_binding.to_dict() if self.card_session_binding else None,
            "card_state": self.card_state.to_dict() if self.card_state else None,
            "opening_record": self.opening_record.to_dict() if self.opening_record else None,
            "worldbook_binding": self.worldbook_binding.to_dict() if self.worldbook_binding else None,
            "round_snapshot_id": self.round_snapshot.snapshot_id if self.round_snapshot else "",
            "l1_turn_count": self.l1_turn_count,
            "l2_active_memory_count": self.l2_active_memory_count,
            "l3_rag_recall_count": self.l3_rag_recall_count,
            "load_errors": self.load_errors,
        }


class SessionRuntimeLoad:
    """Loads session state from persistent stores and builds RoundSnapshot.

    Uses RoundSnapshotBuilder for canonical L1/L2/L3 assembly.
    """

    def __init__(
        self,
        registry: SessionRuntimeStoreRegistry,
        max_turn_history: int = 5,
        max_active_memories: int = 15,
    ):
        self._registry = registry
        self._max_turn_history = max_turn_history
        self._max_active_memories = max_active_memories

    def load(
        self,
        session_id: str,
        player_input: str,
        expected_logical_card_id: str = "",
        expected_card_version: int = 0,
        expected_source_hash: str = "",
        worldbook_entries: list[dict[str, Any]] | None = None,
    ) -> SessionRuntimeBundle:
        """Load all session state and build the canonical RoundSnapshot.

        Args:
            session_id: The session to restore.
            player_input: Current player input for this turn.
            expected_*: Optional validation overrides.
            worldbook_entries: Optional override for worldbook entries
                (if None, reads from stored binding).

        Returns:
            SessionRuntimeBundle with all L0 data and the RoundSnapshot.
        """
        bundle = SessionRuntimeBundle()

        # ── L0: Session Bootstrap ───────────────────────────────────────
        binding = self._registry.card_session_binding_store.load(session_id)
        if not binding:
            bundle.load_errors.append(f"No CardSessionBinding for session {session_id}")
            return bundle
        bundle.card_session_binding = binding

        # Validate binding matches expectations
        if expected_logical_card_id and binding.logical_card_id != expected_logical_card_id:
            bundle.load_errors.append(
                f"logicalCardId mismatch: binding={binding.logical_card_id}, "
                f"expected={expected_logical_card_id}"
            )
        if expected_card_version and binding.card_version != expected_card_version:
            bundle.load_errors.append(
                f"cardVersion mismatch: binding={binding.card_version}, "
                f"expected={expected_card_version}"
            )
        if expected_source_hash and binding.source_hash != expected_source_hash:
            bundle.load_errors.append(
                f"sourceHash mismatch: binding={binding.source_hash}, "
                f"expected={expected_source_hash}"
            )

        if bundle.load_errors:
            return bundle

        # CardState
        card_state = self._registry.card_state_store.load(
            binding.logical_card_id, session_id
        )
        if not card_state:
            card_state = self._registry.card_state_store.initialize(
                binding.logical_card_id, session_id
            )
        bundle.card_state = card_state

        # OpeningRecord
        opening = self._registry.opening_record_store.get_by_session(session_id)
        if not opening:
            bundle.load_errors.append(f"No OpeningRecord for session {session_id}")
            return bundle
        bundle.opening_record = opening

        # WorldbookBinding
        wb_binding = self._registry.worldbook_binding_store.get_by_session(session_id)
        if not wb_binding:
            bundle.load_errors.append(f"No WorldbookBinding for session {session_id}")
            return bundle
        bundle.worldbook_binding = wb_binding

        # ── L1/L2/L3 via RoundSnapshotBuilder ──────────────────────────
        # Use stored worldbook entries unless overridden
        if worldbook_entries is None:
            worldbook_entries = self._extract_wb_entries(wb_binding)

        snapshot_builder = RoundSnapshotBuilder(
            card_state_store=self._registry.card_state_store,
            turn_record_store=self._registry.turn_record_store,
            active_memory_store=self._registry.active_memory_store,
            rag_memory_store=self._registry.rag_memory_store,
            max_turn_history=self._max_turn_history,
            max_active_memories=self._max_active_memories,
        )

        snapshot = snapshot_builder.build(
            card_id=binding.logical_card_id,
            session_id=session_id,
            player_input=player_input,
            worldbook_entries=worldbook_entries,
        )
        bundle.round_snapshot = snapshot
        bundle.l1_turn_count = len(snapshot.recent_turn_records)
        bundle.l2_active_memory_count = len(snapshot.active_memories)
        bundle.l3_rag_recall_count = len(snapshot.rag_recall)

        return bundle

    def _extract_wb_entries(self, wb_binding: WorldbookBinding) -> list[dict[str, Any]]:
        """Extract worldbook entries from a stored binding."""
        entries = []
        if hasattr(wb_binding, 'entries') and wb_binding.entries:
            for e in wb_binding.entries:
                if isinstance(e, dict):
                    entries.append(e)
        return entries
