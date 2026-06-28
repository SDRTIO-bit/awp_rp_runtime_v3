"""AWPV2SessionRuntimeLoad — loads session state from persistent stores.

Given a sessionId, restores:
  L0: CardSessionBinding + CardState + OpeningRecord + WorldbookBinding
  L1: Recent accepted TurnRecords
  L2: ActiveMemory recall
  L3: RagMemory recall

Builds the canonical RoundSnapshot via RoundSnapshotBuilder.
No JSON injection. No client-provided history.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..storage.sqlite.database import Database
from ..runtime.session_runtime_registry import SessionRuntimeStoreRegistry
from ..runtime.session_runtime_load import SessionRuntimeLoad


# Module-level registry cache keyed by db_path
_registry_cache: dict[str, SessionRuntimeStoreRegistry] = {}


def _get_registry(db_path: str) -> SessionRuntimeStoreRegistry:
    """Get or create a registry for the given database path."""
    if db_path not in _registry_cache:
        db = Database(db_path)
        db.initialize()
        _registry_cache[db_path] = SessionRuntimeStoreRegistry(db)
    return _registry_cache[db_path]


def _clear_registry_cache() -> None:
    """Clear the registry cache (for testing)."""
    for registry in _registry_cache.values():
        registry.db.close()
    _registry_cache.clear()


def _resolve_db_path() -> str:
    """Resolve the database path from environment or default.

    Priority:
    1. AWP_TEST_STORE_ROOT + namespace (test mode)
    2. AWP_RUNTIME_DB_PATH (explicit override)
    3. Default: awp_rp_runtime.db in current directory
    """
    profile = os.environ.get("AWP_RUNTIME_PROFILE", "production")

    if profile == "test":
        store_root = os.environ.get("AWP_TEST_STORE_ROOT", "")
        namespace = os.environ.get("AWP_TEST_RUNTIME_NAMESPACE", "default")
        if store_root:
            db_dir = Path(store_root) / namespace
        else:
            db_dir = Path("artifacts") / "test-runtime" / namespace
        db_dir.mkdir(parents=True, exist_ok=True)
        return str(db_dir / "awp_session.db")

    explicit = os.environ.get("AWP_RUNTIME_DB_PATH", "")
    if explicit:
        return explicit

    return "awp_rp_runtime.db"


class AWPV2SessionRuntimeLoad:
    """Load session state from persistent SQLite stores.

    Restores L0 (bootstrap), L1 (turn history), L2 (active memory),
    L3 (RAG memory), and builds the canonical RoundSnapshot.

    OUTPUT_NODE = False — this is a data-loading node, not terminal.
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "session_id": ("STRING", {"default": ""}),
                "player_input": ("STRING", {"default": "", "multiline": True}),
            },
            "optional": {
                "expected_logical_card_id": ("STRING", {"default": ""}),
                "expected_card_version": ("INT", {"default": 0, "min": 0}),
                "expected_source_hash": ("STRING", {"default": ""}),
                "db_path": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = (
        "CARD_SESSION_BINDING", "CARD_STATE", "OPENING_RECORD",
        "WORLDBOOK_BINDING", "ROUND_SNAPSHOT", "JSON",
    )
    RETURN_NAMES = (
        "card_session_binding", "card_state", "opening_record",
        "worldbook_binding", "round_snapshot", "load_diagnostics",
    )
    FUNCTION = "execute"
    CATEGORY = "AWP V2/Persistent Runtime"
    OUTPUT_NODE = False

    def execute(
        self,
        session_id: str,
        player_input: str,
        expected_logical_card_id: str = "",
        expected_card_version: int = 0,
        expected_source_hash: str = "",
        db_path: str = "",
    ) -> tuple:
        # Resolve database
        resolved_db_path = db_path if db_path else _resolve_db_path()
        registry = _get_registry(resolved_db_path)

        # Load session runtime
        loader = SessionRuntimeLoad(registry)
        bundle = loader.load(
            session_id=session_id,
            player_input=player_input,
            expected_logical_card_id=expected_logical_card_id,
            expected_card_version=expected_card_version,
            expected_source_hash=expected_source_hash,
        )

        # Build outputs
        binding_dict = bundle.card_session_binding.to_dict() if bundle.card_session_binding else {}
        card_state_dict = bundle.card_state.to_dict() if bundle.card_state else {}
        opening_dict = bundle.opening_record.to_dict() if bundle.opening_record else {}
        wb_dict = bundle.worldbook_binding.to_dict() if bundle.worldbook_binding else {}
        snapshot_dict = bundle.round_snapshot.to_dict() if bundle.round_snapshot else {}
        diag_dict = bundle.to_dict()

        return (
            binding_dict,
            card_state_dict,
            opening_dict,
            wb_dict,
            snapshot_dict,
            diag_dict,
        )


NODE_CLASS_MAPPINGS = {
    "AWPV2SessionRuntimeLoad": AWPV2SessionRuntimeLoad,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2SessionRuntimeLoad": "AWP V2 Session Runtime Load",
}
