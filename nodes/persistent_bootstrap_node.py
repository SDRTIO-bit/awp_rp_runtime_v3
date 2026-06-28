"""AWPV2PersistentBootstrap — Bootstrap using RuntimeStoreFactory + SQLite.

Replaces AWPV2CardImportAndBootstrap for the canonical persistent path.
All stores come from RuntimeStoreFactory. No Fake stores. No dbPath input.
Session data persisted to SQLite, recoverable by sessionId alone.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts.card_definition import CardDefinition, CardDefinitionStatus
from ..contracts.card_session_bootstrap_request import CardSessionBootstrapRequest
from ..contracts.card_session_bootstrap_receipt import CardSessionBootstrapReceipt
from ..contracts.card_session_bootstrap_failure import CardSessionBootstrapFailure
from ..contracts.card_session_bootstrap_diagnostics import CardSessionBootstrapDiagnostics
from ..contracts.card_session_binding import CardSessionBinding, CardSessionBindingStatus
from ..contracts.greeting_selection import GreetingSelection
from ..contracts.opening_record import OpeningRecord
from ..contracts.worldbook_binding import WorldbookBinding, WorldbookBindingEntry
from ..contracts.card_state import CardState

from ..runtime.runtime_store_factory import RuntimeStoreFactory
from ..runtime.card_session_bootstrap_pipeline import CardSessionBootstrapPipeline
from ..storage.card_import_interfaces import CardDefinitionStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


class _SqliteCardDefinitionStore(CardDefinitionStore):
    """SQLite-backed CardDefinitionStore for bootstrap."""

    def __init__(self, db):
        self._db = db

    def save(self, defn: CardDefinition) -> None:
        import json
        conn = self._db.connect()
        conn.execute(
            """INSERT OR REPLACE INTO card_definitions
               (card_id, card_version, source_id, source_hash, name, display_name,
                status, definition_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                defn.logical_card_id, defn.card_version,
                defn.source_id, defn.source_hash,
                defn.name, defn.display_name,
                defn.status.value if hasattr(defn.status, 'value') else defn.status,
                json.dumps(defn.to_dict(), ensure_ascii=False),
                defn.created_at, defn.updated_at,
            ),
        )
        conn.commit()

    def load(self, card_id: str, card_version: int) -> CardDefinition | None:
        import json
        conn = self._db.connect()
        row = conn.execute(
            "SELECT definition_json FROM card_definitions WHERE card_id=? AND card_version=?",
            (card_id, card_version),
        ).fetchone()
        if not row:
            return None
        return CardDefinition.from_dict(json.loads(row["definition_json"]))

    def get_by_source_hash(self, source_hash: str) -> CardDefinition | None:
        import json
        conn = self._db.connect()
        row = conn.execute(
            "SELECT definition_json FROM card_definitions WHERE source_hash=? LIMIT 1",
            (source_hash,),
        ).fetchone()
        if not row:
            return None
        return CardDefinition.from_dict(json.loads(row["definition_json"]))

    def get_latest(self, logical_card_id: str) -> CardDefinition | None:
        import json
        conn = self._db.connect()
        row = conn.execute(
            "SELECT definition_json FROM card_definitions WHERE card_id=? "
            "ORDER BY card_version DESC LIMIT 1",
            (logical_card_id,),
        ).fetchone()
        if not row:
            return None
        return CardDefinition.from_dict(json.loads(row["definition_json"]))

    def list_all(self, status: str = "") -> list:
        import json
        conn = self._db.connect()
        if status:
            rows = conn.execute(
                "SELECT definition_json FROM card_definitions WHERE status=?",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT definition_json FROM card_definitions",
            ).fetchall()
        return [CardDefinition.from_dict(json.loads(r["definition_json"])) for r in rows]

    def update_status(self, logical_card_id: str, card_version: int, status: str) -> None:
        conn = self._db.connect()
        conn.execute(
            "UPDATE card_definitions SET status=? WHERE card_id=? AND card_version=?",
            (status, logical_card_id, card_version),
        )
        conn.commit()

    def get_next_version(self, logical_card_id: str) -> int:
        conn = self._db.connect()
        row = conn.execute(
            "SELECT MAX(card_version) as max_ver FROM card_definitions WHERE card_id=?",
            (logical_card_id,),
        ).fetchone()
        return (row["max_ver"] or 0) + 1


class AWPV2PersistentBootstrap:
    """Import card and bootstrap session using RuntimeStoreFactory + SQLite.

    No Fake stores. No dbPath input. Session persisted to SQLite.
    ComfyUI restart → same sessionId → session recoverable.
    """

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "source_path": ("STRING", {"default": ""}),
                "session_id": ("STRING", {"default": "test-session-001"}),
                "greeting_id": ("STRING", {"default": "g0"}),
                "request_id": ("STRING", {"default": "req-001"}),
                "run_id": ("STRING", {"default": ""}),
            },
            "optional": {
                "workflow_run_id": ("STRING", {"default": ""}),
                "trace_id": ("STRING", {"default": ""}),
                "initial_state_seed": ("STRING", {"default": "{}"}),
            },
        }

    RETURN_TYPES = (
        "CARD_SESSION_BINDING", "OPENING_RECORD", "WORLDBOOK_BINDING",
        "BOOTSTRAP_RECEIPT", "DIAGNOSTICS",
    )
    RETURN_NAMES = (
        "session_binding", "opening_record", "worldbook_binding",
        "bootstrap_receipt", "diagnostics",
    )
    FUNCTION = "execute"
    CATEGORY = "AWP V2/Persistent Runtime"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return time.time()

    def execute(
        self,
        source_path: str,
        session_id: str = "test-session-001",
        greeting_id: str = "g0",
        request_id: str = "req-001",
        run_id: str = "",
        workflow_run_id: str = "",
        trace_id: str = "",
        initial_state_seed: str = "{}",
    ) -> tuple:
        from ..runtime.card_source_loader import load_card_source
        from ..runtime.card_payload_parser import CardPayloadParser
        from ..runtime.card_security_scanner import CardSecurityScanner
        from ..runtime.card_greeting_sanitizer import sanitize_greeting_content
        from ..runtime.card_worldbook_chunk_builder import build_all_chunks

        now = _now()

        # ── Resolve factory from env ─────────────────────────────────────
        factory = RuntimeStoreFactory.from_env()
        registry = factory.registry

        # ── Load and parse card ──────────────────────────────────────────
        p = Path(source_path)
        if not p.is_absolute():
            project_root = Path(__file__).parent.parent
            p = project_root / source_path
        snap, payload = load_card_source(str(p), "", now)
        parser = CardPayloadParser()
        profile = parser.parse_profile(payload)
        greetings = parser.parse_greetings(payload)
        wb_entries = parser.parse_worldbook_entries(payload)
        hints = parser.parse_structure_hints(payload)

        # Security scan
        scanner = CardSecurityScanner()
        q_records, sec_issues, sec_summary = scanner.scan(payload)

        # Sanitize greetings
        san_greetings = []
        all_q = list(q_records)
        for g in greetings:
            safe, gq = sanitize_greeting_content(g.safe_display_content, g.greeting_id, g.source_path)
            all_q.extend(gq)
            san_greetings.append({**g.to_dict(), "safe_display_content": safe})

        # Build chunks
        wb_entries, wb_chunks = build_all_chunks(wb_entries)

        # Create CardDefinition
        import uuid
        logical_card_id = f"lcid_{uuid.uuid4().hex[:16]}"
        defn = CardDefinition(
            logical_card_id=logical_card_id,
            card_version=1,
            source_id=snap.source_id,
            source_hash=snap.source_hash,
            name=profile.name,
            display_name=profile.name,
            status=CardDefinitionStatus.READY,
            profile=profile.to_dict(),
            greetings=san_greetings,
            worldbook_catalog=[e.to_dict() for e in wb_entries],
            worldbook_chunks=[c.to_dict() for c in wb_chunks],
            structure_hints=hints.to_dict(),
            quarantine_summary={"total": len(all_q)},
            created_at=now,
            updated_at=now,
        )

        # Save definition to SQLite
        defs_store = _SqliteCardDefinitionStore(registry.db)
        defs_store.save(defn)

        # ── Bootstrap using SQLite stores ────────────────────────────────
        seed = {}
        if initial_state_seed:
            import json
            try:
                seed = json.loads(initial_state_seed) if isinstance(initial_state_seed, str) else initial_state_seed
            except (json.JSONDecodeError, TypeError):
                seed = {}

        req = CardSessionBootstrapRequest(
            request_id=request_id,
            workflow_run_id=workflow_run_id or f"wr_{request_id}",
            trace_id=trace_id or f"tr_{request_id}",
            session_id=session_id,
            logical_card_id=logical_card_id,
            card_version=1,
            greeting_id=greeting_id,
            expected_source_hash=snap.source_hash,
            initial_state_seed=seed,
            created_at=now,
        )

        # Use SQLite stores for bootstrap
        pipeline = CardSessionBootstrapPipeline(
            definition_store=defs_store,
            binding_store=registry.card_session_binding_store,
            opening_store=registry.opening_record_store,
            worldbook_store=registry.worldbook_binding_store,
            receipt_store=registry.bootstrap_receipt_store,
        )

        receipt, failure, diag = pipeline.bootstrap(req)

        if failure:
            raise RuntimeError(
                f"Bootstrap failed: {failure.failure_code} — {failure.failure_message}"
            )

        # Load committed data from SQLite
        binding = registry.card_session_binding_store.load(session_id)
        opening = registry.opening_record_store.get_by_session(session_id)
        wb = registry.worldbook_binding_store.get_by_session(session_id)

        return (
            binding.to_dict() if binding else {},
            opening.to_dict() if opening else {},
            wb.to_dict() if wb else {},
            receipt.to_dict() if receipt else {},
            diag.to_dict(),
        )


NODE_CLASS_MAPPINGS = {
    "AWPV2PersistentBootstrap": AWPV2PersistentBootstrap,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2PersistentBootstrap": "AWP V2 Persistent Bootstrap",
}
