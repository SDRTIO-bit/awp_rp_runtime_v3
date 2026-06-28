"""CardSessionBootstrapPipeline — orchestrates the bootstrap chain.

Chain:
  Card Catalog Lookup
  → CardDefinition Ready Validation
  → Greeting Selection Validation
  → Bootstrap Request Validation
  → CardState Initialization
  → OpeningRecord Commit
  → Worldbook Binding Build
  → CardSessionBinding Commit
  → Bootstrap Receipt
  → Session Ready

Idempotency: same request_id → returns existing receipt (no duplicate writes).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from ..contracts.card_definition import CardDefinition, CardDefinitionStatus
from ..contracts.card_session_bootstrap_request import CardSessionBootstrapRequest
from ..contracts.card_session_binding import CardSessionBinding, CardSessionBindingStatus
from ..contracts.greeting_selection import GreetingSelection
from ..contracts.opening_record import OpeningRecord
from ..contracts.worldbook_binding import WorldbookBinding, WorldbookBindingEntry
from ..contracts.card_session_bootstrap_receipt import CardSessionBootstrapReceipt
from ..contracts.card_session_bootstrap_failure import CardSessionBootstrapFailure, BootstrapFailureCode
from ..contracts.card_session_bootstrap_diagnostics import CardSessionBootstrapDiagnostics
from ..contracts.card_state import CardState

from ..storage.card_import_interfaces import CardDefinitionStore
from ..storage.card_session_interfaces import (
    CardSessionBindingStore, OpeningRecordStore,
    WorldbookBindingStore, BootstrapReceiptStore,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


class CardSessionBootstrapPipeline:
    """Orchestrates the full CardSession bootstrap chain."""

    def __init__(
        self,
        definition_store: CardDefinitionStore,
        binding_store: CardSessionBindingStore,
        opening_store: OpeningRecordStore,
        worldbook_store: WorldbookBindingStore,
        receipt_store: BootstrapReceiptStore,
    ):
        self._defs = definition_store
        self._bindings = binding_store
        self._openings = opening_store
        self._worldbooks = worldbook_store
        self._receipts = receipt_store

    def bootstrap(
        self,
        request: CardSessionBootstrapRequest,
    ) -> tuple[CardSessionBootstrapReceipt | None, CardSessionBootstrapFailure | None, CardSessionBootstrapDiagnostics]:
        """Execute the bootstrap chain.

        Returns (receipt, failure, diagnostics).
        On success: receipt is set, failure is None.
        On failure: receipt is None, failure is set.
        Diagnostics is always set.
        """
        now = _now()
        trace_id = request.trace_id or _id("trace", request.request_id)

        # Initialize diagnostics
        diag = CardSessionBootstrapDiagnostics(
            logical_card_id=request.logical_card_id,
            card_version=request.card_version,
            session_id=request.session_id,
            request_id=request.request_id,
        )

        # ── Step 0: Idempotency check ──────────────────────────────────
        existing = self._receipts.get_by_request(request.request_id)
        if existing:
            return existing, None, CardSessionBootstrapDiagnostics(
                logical_card_id=existing.logical_card_id,
                card_version=existing.card_version,
                source_hash=existing.source_hash,
                session_id=existing.session_id,
                request_id=existing.request_id,
                selected_greeting_id=existing.greeting_id,
                opening_record_id=existing.opening_record_id,
                worldbook_binding_id=existing.worldbook_binding_id,
                card_state_revision_after=existing.card_state_revision,
                commit_status=existing.commit_status,
                idempotency_status="reused",
            )

        # ── Step 1: Validate request ────────────────────────────────────
        validation_errors = request.validate()
        if validation_errors:
            return None, CardSessionBootstrapFailure(
                failure_id=_id("fail", request.request_id),
                request_id=request.request_id,
                session_id=request.session_id,
                logical_card_id=request.logical_card_id,
                card_version=request.card_version,
                failure_code=BootstrapFailureCode.VALIDATION_ERROR,
                failure_message="; ".join(validation_errors),
                created_at=now,
            ), diag

        # ── Step 2: Card Catalog Lookup ─────────────────────────────────
        defn = self._defs.load(request.logical_card_id, request.card_version)
        if not defn:
            return None, CardSessionBootstrapFailure(
                failure_id=_id("fail", request.request_id),
                request_id=request.request_id,
                session_id=request.session_id,
                logical_card_id=request.logical_card_id,
                card_version=request.card_version,
                failure_code=BootstrapFailureCode.CARD_NOT_FOUND,
                failure_message=f"Card not found: {request.logical_card_id} v{request.card_version}",
                created_at=now,
            ), diag

        # ── Step 3: CardDefinition Ready Validation ─────────────────────
        if defn.status != CardDefinitionStatus.READY:
            return None, CardSessionBootstrapFailure(
                failure_id=_id("fail", request.request_id),
                request_id=request.request_id,
                session_id=request.session_id,
                logical_card_id=request.logical_card_id,
                card_version=request.card_version,
                failure_code=BootstrapFailureCode.CARD_NOT_READY,
                failure_message=f"Card status is '{defn.status}', expected 'ready'",
                created_at=now,
            ), diag

        # ── Step 4: Source hash validation ───────────────────────────────
        if defn.source_hash != request.expected_source_hash:
            return None, CardSessionBootstrapFailure(
                failure_id=_id("fail", request.request_id),
                request_id=request.request_id,
                session_id=request.session_id,
                logical_card_id=request.logical_card_id,
                card_version=request.card_version,
                failure_code=BootstrapFailureCode.SOURCE_HASH_MISMATCH,
                failure_message=f"Source hash mismatch: expected {request.expected_source_hash}, got {defn.source_hash}",
                created_at=now,
            ), diag

        diag = CardSessionBootstrapDiagnostics(
            logical_card_id=defn.logical_card_id,
            card_version=defn.card_version,
            source_hash=defn.source_hash,
            session_id=request.session_id,
            request_id=request.request_id,
        )

        # ── Step 5: Session version conflict check ──────────────────────
        existing_binding = self._bindings.load(request.session_id)
        if existing_binding and existing_binding.status == CardSessionBindingStatus.READY:
            if (existing_binding.logical_card_id != request.logical_card_id or
                    existing_binding.card_version != request.card_version):
                return None, CardSessionBootstrapFailure(
                    failure_id=_id("fail", request.request_id),
                    request_id=request.request_id,
                    session_id=request.session_id,
                    logical_card_id=request.logical_card_id,
                    card_version=request.card_version,
                    failure_code=BootstrapFailureCode.SESSION_VERSION_CONFLICT,
                    failure_message=(
                        f"Session {request.session_id} already bound to "
                        f"{existing_binding.logical_card_id} v{existing_binding.card_version}"
                    ),
                    created_at=now,
                ), diag

        # ── Step 6: Greeting Selection Validation ───────────────────────
        greeting = self._select_greeting(defn, request.greeting_id)
        if not greeting:
            return None, CardSessionBootstrapFailure(
                failure_id=_id("fail", request.request_id),
                request_id=request.request_id,
                session_id=request.session_id,
                logical_card_id=request.logical_card_id,
                card_version=request.card_version,
                failure_code=BootstrapFailureCode.GREETING_NOT_FOUND,
                failure_message=f"Greeting '{request.greeting_id}' not found in card {defn.logical_card_id} v{defn.card_version}",
                created_at=now,
            ), diag

        diag = CardSessionBootstrapDiagnostics(
            logical_card_id=defn.logical_card_id,
            card_version=defn.card_version,
            source_hash=defn.source_hash,
            session_id=request.session_id,
            request_id=request.request_id,
            selected_greeting_id=greeting.greeting_id,
        )

        # ── Step 7: CardState Initialization ────────────────────────────
        card_state = self._init_card_state(defn, request, now)
        diag = CardSessionBootstrapDiagnostics(
            logical_card_id=defn.logical_card_id,
            card_version=defn.card_version,
            source_hash=defn.source_hash,
            session_id=request.session_id,
            request_id=request.request_id,
            selected_greeting_id=greeting.greeting_id,
            card_state_revision_before=0,
            card_state_revision_after=card_state.revision,
        )

        # ── Step 8: OpeningRecord Commit ────────────────────────────────
        opening_record_id = _id("opr", f"{request.session_id}_{request.greeting_id}")
        opening = OpeningRecord(
            opening_record_id=opening_record_id,
            session_id=request.session_id,
            logical_card_id=defn.logical_card_id,
            card_version=defn.card_version,
            greeting_id=greeting.greeting_id,
            safe_display_content=greeting.safe_display_content,
            source_greeting_ref=f"{defn.logical_card_id}/v{defn.card_version}/greetings/{greeting.greeting_id}",
            created_at=now,
        )
        self._openings.save(opening)

        diag = CardSessionBootstrapDiagnostics(
            logical_card_id=defn.logical_card_id,
            card_version=defn.card_version,
            source_hash=defn.source_hash,
            session_id=request.session_id,
            request_id=request.request_id,
            selected_greeting_id=greeting.greeting_id,
            opening_record_id=opening_record_id,
            card_state_revision_before=0,
            card_state_revision_after=card_state.revision,
        )

        # ── Step 9: Worldbook Binding Build ─────────────────────────────
        wb_binding = self._build_worldbook_binding(defn, request, now)
        self._worldbooks.save(wb_binding)

        diag = CardSessionBootstrapDiagnostics(
            logical_card_id=defn.logical_card_id,
            card_version=defn.card_version,
            source_hash=defn.source_hash,
            session_id=request.session_id,
            request_id=request.request_id,
            selected_greeting_id=greeting.greeting_id,
            opening_record_id=opening_record_id,
            worldbook_binding_id=wb_binding.worldbook_binding_id,
            card_state_revision_before=0,
            card_state_revision_after=card_state.revision,
            bound_entry_count=len(wb_binding.bound_entry_ids),
            disabled_entry_count=len(wb_binding.disabled_entry_ids),
            deferred_entry_count=len(wb_binding.deferred_entry_ids),
        )

        # ── Step 10: CardSessionBinding Commit ──────────────────────────
        binding = CardSessionBinding(
            session_id=request.session_id,
            logical_card_id=defn.logical_card_id,
            card_version=defn.card_version,
            source_hash=defn.source_hash,
            card_definition_ref=f"{defn.logical_card_id}/v{defn.card_version}",
            selected_greeting_id=greeting.greeting_id,
            worldbook_binding_id=wb_binding.worldbook_binding_id,
            opening_record_id=opening_record_id,
            created_at=now,
            status=CardSessionBindingStatus.READY,
        )
        self._bindings.save(binding)

        # ── Step 11: Bootstrap Receipt ──────────────────────────────────
        receipt_id = _id("rcpt", f"{request.request_id}_{request.session_id}")
        receipt = CardSessionBootstrapReceipt(
            receipt_id=receipt_id,
            request_id=request.request_id,
            workflow_run_id=request.workflow_run_id,
            trace_id=trace_id,
            session_id=request.session_id,
            logical_card_id=defn.logical_card_id,
            card_version=defn.card_version,
            source_hash=defn.source_hash,
            greeting_id=greeting.greeting_id,
            opening_record_id=opening_record_id,
            worldbook_binding_id=wb_binding.worldbook_binding_id,
            card_state_revision=card_state.revision,
            commit_status="success",
            idempotency_status="new",
            created_at=now,
        )
        self._receipts.save(receipt)

        final_diag = CardSessionBootstrapDiagnostics(
            logical_card_id=defn.logical_card_id,
            card_version=defn.card_version,
            source_hash=defn.source_hash,
            session_id=request.session_id,
            request_id=request.request_id,
            selected_greeting_id=greeting.greeting_id,
            opening_record_id=opening_record_id,
            worldbook_binding_id=wb_binding.worldbook_binding_id,
            card_state_revision_before=0,
            card_state_revision_after=card_state.revision,
            bound_entry_count=len(wb_binding.bound_entry_ids),
            disabled_entry_count=len(wb_binding.disabled_entry_ids),
            deferred_entry_count=len(wb_binding.deferred_entry_ids),
            commit_status="success",
            idempotency_status="new",
        )

        return receipt, None, final_diag

    def _select_greeting(self, defn: CardDefinition, greeting_id: str) -> GreetingSelection | None:
        """Find and validate a greeting belongs to this exact card version."""
        for g_data in defn.greetings:
            if g_data.get("greeting_id") == greeting_id:
                return GreetingSelection(
                    greeting_id=greeting_id,
                    logical_card_id=defn.logical_card_id,
                    card_version=defn.card_version,
                    safe_display_content=g_data.get("safe_display_content", ""),
                    content_hash=g_data.get("content_hash", ""),
                    is_default=g_data.get("is_default", False),
                    index=g_data.get("index", 0),
                    label=g_data.get("label", ""),
                )
        return None

    def _init_card_state(
        self,
        defn: CardDefinition,
        request: CardSessionBootstrapRequest,
        now: str,
    ) -> CardState:
        """Initialize CardState from safe initialStateSeed only.

        NEVER from description/personality/scenario.
        NEVER from scripts/EJS/JS/Regex.
        """
        variables = {}
        if request.initial_state_seed:
            for k, v in request.initial_state_seed.items():
                from ..contracts.card_state import VariableEntry
                if isinstance(v, bool):
                    var_type = "bool"
                elif isinstance(v, int):
                    var_type = "int"
                elif isinstance(v, float):
                    var_type = "float"
                else:
                    var_type = "string"
                    v = str(v)
                variables[k] = VariableEntry(name=k, value=v, var_type=var_type)

        state = CardState(
            card_id=defn.logical_card_id,
            session_id=request.session_id,
            revision=1,
            variables=variables,
            created_at=now,
            updated_at=now,
        )
        return state

    def _build_worldbook_binding(
        self,
        defn: CardDefinition,
        request: CardSessionBootstrapRequest,
        now: str,
    ) -> WorldbookBinding:
        """Build WorldbookBinding from CardDefinition catalog.

        Rules:
        - disabled entries → disabled_entry_ids (not activatable by default)
        - constant entries → candidate (still budget-governed)
        - selective entries → candidate (conditional evaluation deferred)
        - unsupported activation → deferred/unsupported
        - long entry chunks → preserve parentEntryId traceability
        """
        binding_id = _id("wb", f"{request.session_id}_{defn.logical_card_id}")
        bound_ids: list[str] = []
        disabled_ids: list[str] = []
        deferred_ids: list[str] = []
        unsupported_ids: list[str] = []
        chunk_ids: list[str] = []
        entries: list[dict[str, Any]] = []

        for e_data in defn.worldbook_catalog:
            entry_id = e_data.get("entry_id", "")
            enabled = e_data.get("enabled", True)
            constant = e_data.get("constant", False)
            selective = e_data.get("selective", False)
            has_chunks = e_data.get("has_chunks", False)
            has_primary_keys = bool(e_data.get("keys", []))
            has_secondary_keys = bool(e_data.get("secondary_keys", []))
            activation_raw = e_data.get("activation_raw", {})
            if not isinstance(activation_raw, dict):
                activation_raw = {}
            unsupported_activation = any(
                key in activation_raw
                for key in (
                    "position",
                    "probability",
                    "useProbability",
                    "recursive",
                    "delayUntilRecursion",
                    "group",
                    "groupOverride",
                    "groupWeight",
                    "preventGroupRecursion",
                    "sticky",
                    "cooldown",
                    "delay",
                )
            )

            if not enabled:
                disabled_ids.append(entry_id)
                status = "disabled"
            elif selective:
                if has_primary_keys and not has_secondary_keys and not unsupported_activation:
                    bound_ids.append(entry_id)
                    status = "candidate"
                else:
                    deferred_ids.append(entry_id)
                    status = "deferred"
                    if has_secondary_keys or unsupported_activation or not has_primary_keys:
                        unsupported_ids.append(entry_id)
            elif constant:
                bound_ids.append(entry_id)
                status = "candidate"
            else:
                bound_ids.append(entry_id)
                status = "candidate"

            # Collect chunk IDs
            if has_chunks:
                for c_data in defn.worldbook_chunks:
                    if c_data.get("parent_entry_id") == entry_id:
                        cid = c_data.get("chunk_id", "")
                        if cid:
                            chunk_ids.append(cid)

            entries.append(WorldbookBindingEntry(
                entry_id=entry_id,
                source_uid=e_data.get("source_uid", -1),
                enabled=enabled,
                constant=constant,
                selective=selective,
                has_chunks=has_chunks,
                chunk_ids=[c.get("chunk_id", "") for c in defn.worldbook_chunks if c.get("parent_entry_id") == entry_id],
                activation_status=status,
            ).to_dict())

        return WorldbookBinding(
            worldbook_binding_id=binding_id,
            session_id=request.session_id,
            logical_card_id=defn.logical_card_id,
            card_version=defn.card_version,
            source_hash=defn.source_hash,
            catalog_ref=f"{defn.logical_card_id}/v{defn.card_version}/worldbook",
            bound_entry_ids=bound_ids,
            bound_chunk_ids=chunk_ids,
            disabled_entry_ids=disabled_ids,
            deferred_entry_ids=deferred_ids,
            unsupported_activation_entry_ids=unsupported_ids,
            entries=entries,
            created_at=now,
        )
