"""AWPV2PersistentBootstrap for the canonical persistent path."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts.card_definition import CardDefinition, CardDefinitionStatus
from ..contracts.card_session_bootstrap_request import CardSessionBootstrapRequest
from ..runtime.card_session_bootstrap_pipeline import CardSessionBootstrapPipeline
from ..runtime.runtime_store_factory import RuntimeStoreFactory
from ..runtime.card_source_loader import load_card_source
from ..runtime.card_payload_parser import CardPayloadParser
from ..runtime.card_security_scanner import CardSecurityScanner
from ..runtime.card_greeting_sanitizer import sanitize_greeting_content
from ..runtime.card_worldbook_chunk_builder import build_all_chunks
from ..storage.sqlite.card_definition_store import SqliteCardDefinitionStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def _resolve_source_path(source_path: str) -> Path:
    path = Path(source_path)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parent.parent / source_path


def _derive_source_hash(source_path: str) -> str:
    try:
        snapshot, _payload = load_card_source(str(_resolve_source_path(source_path)), "", "")
        return snapshot.source_hash
    except Exception:
        path = _resolve_source_path(source_path)
        if path.exists():
            return hashlib.sha256(path.read_bytes()).hexdigest()
        return "missing"


class AWPV2PersistentBootstrap:
    """Import card and bootstrap session using RuntimeStoreFactory + SQLite."""

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
        "CARD_SESSION_BINDING",
        "OPENING_RECORD",
        "WORLDBOOK_BINDING",
        "BOOTSTRAP_RECEIPT",
        "DIAGNOSTICS",
    )
    RETURN_NAMES = (
        "session_binding",
        "opening_record",
        "worldbook_binding",
        "bootstrap_receipt",
        "diagnostics",
    )
    FUNCTION = "execute"
    CATEGORY = "AWP V2/Persistent Runtime"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(
        cls,
        source_path: str,
        session_id: str = "test-session-001",
        greeting_id: str = "g0",
        request_id: str = "req-001",
        run_id: str = "",
        workflow_run_id: str = "",
        trace_id: str = "",
        initial_state_seed: str = "{}",
    ):
        return (
            "bootstrap",
            str(_resolve_source_path(source_path)),
            _derive_source_hash(source_path),
            session_id,
            greeting_id,
            request_id,
        )

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
        now = _now()
        factory = RuntimeStoreFactory.from_env()
        registry = factory.registry
        defs_store = SqliteCardDefinitionStore(registry.db)

        source = _resolve_source_path(source_path)
        snapshot, payload = load_card_source(str(source), "", now)
        parser = CardPayloadParser()
        profile = parser.parse_profile(payload)
        greetings = parser.parse_greetings(payload)
        worldbook_entries = parser.parse_worldbook_entries(payload)
        hints = parser.parse_structure_hints(payload)

        scanner = CardSecurityScanner()
        quarantine_records, _security_issues, _security_summary = scanner.scan(payload)

        sanitized_greetings = []
        all_quarantine = list(quarantine_records)
        for greeting in greetings:
            safe_content, greeting_quarantine = sanitize_greeting_content(
                greeting.safe_display_content,
                greeting.greeting_id,
                greeting.source_path,
            )
            all_quarantine.extend(greeting_quarantine)
            sanitized_greetings.append({**greeting.to_dict(), "safe_display_content": safe_content})

        worldbook_entries, worldbook_chunks = build_all_chunks(worldbook_entries)

        import uuid

        logical_card_id = f"lcid_{uuid.uuid4().hex[:16]}"
        definition = CardDefinition(
            logical_card_id=logical_card_id,
            card_version=1,
            source_id=snapshot.source_id,
            source_hash=snapshot.source_hash,
            name=profile.name,
            display_name=profile.name,
            status=CardDefinitionStatus.READY,
            profile=profile.to_dict(),
            greetings=sanitized_greetings,
            worldbook_catalog=[entry.to_dict() for entry in worldbook_entries],
            worldbook_chunks=[chunk.to_dict() for chunk in worldbook_chunks],
            structure_hints=hints.to_dict(),
            quarantine_summary={"total": len(all_quarantine)},
            created_at=now,
            updated_at=now,
        )
        defs_store.save(definition)

        seed = {}
        if initial_state_seed:
            import json

            try:
                seed = json.loads(initial_state_seed) if isinstance(initial_state_seed, str) else initial_state_seed
            except (json.JSONDecodeError, TypeError):
                seed = {}

        request = CardSessionBootstrapRequest(
            request_id=request_id,
            workflow_run_id=workflow_run_id or f"wr_{request_id}",
            trace_id=trace_id or f"tr_{request_id}",
            session_id=session_id,
            logical_card_id=logical_card_id,
            card_version=1,
            greeting_id=greeting_id,
            expected_source_hash=snapshot.source_hash,
            initial_state_seed=seed,
            created_at=now,
        )

        pipeline = CardSessionBootstrapPipeline(
            definition_store=defs_store,
            binding_store=registry.card_session_binding_store,
            opening_store=registry.opening_record_store,
            worldbook_store=registry.worldbook_binding_store,
            receipt_store=registry.bootstrap_receipt_store,
        )
        receipt, failure, diagnostics = pipeline.bootstrap(request)
        if failure:
            raise RuntimeError(f"Bootstrap failed: {failure.failure_code} - {failure.failure_message}")

        binding = registry.card_session_binding_store.load(session_id)
        opening = registry.opening_record_store.get_by_session(session_id)
        worldbook = registry.worldbook_binding_store.get_by_session(session_id)
        return (
            binding.to_dict() if binding else {},
            opening.to_dict() if opening else {},
            worldbook.to_dict() if worldbook else {},
            receipt.to_dict() if receipt else {},
            diagnostics.to_dict(),
        )


NODE_CLASS_MAPPINGS = {
    "AWPV2PersistentBootstrap": AWPV2PersistentBootstrap,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "AWPV2PersistentBootstrap": "AWP V2 Persistent Bootstrap",
}
