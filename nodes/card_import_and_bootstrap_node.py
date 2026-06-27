"""AWPV2CardImportAndBootstrap — end-to-end import+approve+bootstrap for testing.

This node chains: import → approve → bootstrap in a single execution.
Used by real Comfy API acceptance scenarios.
"""

from __future__ import annotations
import json
from typing import Any


class AWPV2CardImportAndBootstrap:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "source_path": ("STRING", {"default": ""}),
                "session_id": ("STRING", {"default": "test-session-001"}),
                "greeting_id": ("STRING", {"default": "g0"}),
                "request_id": ("STRING", {"default": "req-001"}),
            },
            "optional": {
                "workflow_run_id": ("STRING", {"default": ""}),
                "trace_id": ("STRING", {"default": ""}),
                "initial_state_seed": ("STRING", {"default": "{}"}),
            },
        }

    RETURN_TYPES = ("CARD_SESSION_BINDING", "OPENING_RECORD", "WORLDBOOK_BINDING", "BOOTSTRAP_RECEIPT", "DIAGNOSTICS")
    RETURN_NAMES = ("session_binding", "opening_record", "worldbook_binding", "bootstrap_receipt", "diagnostics")
    FUNCTION = "execute"
    CATEGORY = "AWP/CardSession"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Never cache — always re-execute
        return float("nan")

    def execute(
        self,
        source_path: str,
        session_id: str = "test-session-001",
        greeting_id: str = "g0",
        request_id: str = "req-001",
        workflow_run_id: str = "",
        trace_id: str = "",
        initial_state_seed: str = "{}",
    ) -> tuple[dict, dict, dict, dict, dict]:
        from datetime import datetime, timezone
        from ..runtime.card_source_loader import load_card_source
        from ..runtime.card_payload_parser import CardPayloadParser
        from ..runtime.card_security_scanner import CardSecurityScanner
        from ..runtime.card_greeting_sanitizer import sanitize_greeting_content
        from ..runtime.card_worldbook_chunk_builder import build_all_chunks
        from ..contracts.card_definition import CardDefinition, CardDefinitionStatus
        from ..contracts.card_greeting import CardGreeting
        from ..contracts.card_worldbook_entry import CardWorldbookEntry
        from ..contracts.card_import_approval import CardImportApproval, ApprovalDecision
        from ..contracts.card_session_bootstrap_request import CardSessionBootstrapRequest
        from ..testing.fakes.fake_card_import_stores import FakeCardDefinitionStore
        from ..testing.fakes.fake_card_session_stores import (
            FakeCardSessionBindingStore, FakeOpeningRecordStore,
            FakeWorldbookBindingStore, FakeBootstrapReceiptStore,
        )
        from ..runtime.card_session_bootstrap_pipeline import CardSessionBootstrapPipeline

        now = datetime.now(timezone.utc).isoformat()

        # Step 1: Load and parse card — resolve relative path from project root
        from pathlib import Path as _Path
        p = _Path(source_path)
        if not p.is_absolute():
            project_root = _Path(__file__).parent.parent
            p = project_root / source_path
        snap, payload = load_card_source(str(p), "", now)
        parser = CardPayloadParser()
        profile = parser.parse_profile(payload)
        greetings = parser.parse_greetings(payload)
        wb_entries = parser.parse_worldbook_entries(payload)
        hints = parser.parse_structure_hints(payload)

        # Step 2: Security scan
        scanner = CardSecurityScanner()
        q_records, sec_issues, sec_summary = scanner.scan(payload)

        # Step 3: Sanitize greetings
        san_greetings = []
        all_q = list(q_records)
        for g in greetings:
            safe, gq = sanitize_greeting_content(g.safe_display_content, g.greeting_id, g.source_path)
            all_q.extend(gq)
            san_greetings.append({**g.to_dict(), "safe_display_content": safe, "quarantine_refs": [r.record_id for r in gq]})

        # Step 4: Build chunks
        wb_entries, wb_chunks = build_all_chunks(wb_entries)

        # Step 5: Create CardDefinition
        import uuid
        logical_card_id = f"lcid_{uuid.uuid4().hex[:16]}"
        defn = CardDefinition(
            logical_card_id=logical_card_id, card_version=1,
            source_id=snap.source_id, source_hash=snap.source_hash,
            name=profile.name, display_name=profile.name,
            status=CardDefinitionStatus.READY,  # Direct to ready for test
            profile=profile.to_dict(), greetings=san_greetings,
            worldbook_catalog=[e.to_dict() for e in wb_entries],
            worldbook_chunks=[c.to_dict() for c in wb_chunks],
            structure_hints=hints.to_dict(),
            quarantine_summary={"total": len(all_q)},
            created_at=now, updated_at=now,
        )

        # Step 6: Save to store
        defs = FakeCardDefinitionStore()
        defs.save(defn)

        # Step 7: Bootstrap
        seed = {}
        if initial_state_seed:
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

        pl = CardSessionBootstrapPipeline(
            defs,
            FakeCardSessionBindingStore(),
            FakeOpeningRecordStore(),
            FakeWorldbookBindingStore(),
            FakeBootstrapReceiptStore(),
        )

        receipt, failure, diag = pl.bootstrap(req)

        if failure:
            raise RuntimeError(f"Bootstrap failed: {failure.failure_code} — {failure.failure_message}")

        return (
            pl._bindings.load(session_id).to_dict(),
            pl._openings.load(receipt.opening_record_id).to_dict(),
            pl._worldbooks.load(receipt.worldbook_binding_id).to_dict(),
            receipt.to_dict(),
            diag.to_dict(),
        )
