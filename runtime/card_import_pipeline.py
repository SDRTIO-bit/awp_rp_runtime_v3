"""CardImportPipeline — orchestrates the full card import pipeline."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from ..contracts.card_source_snapshot import CardSourceSnapshot
from ..contracts.card_import_request import CardImportRequest
from ..contracts.card_import_report import CardImportReport
from ..contracts.card_import_issue import CardImportIssue, IssueSeverity
from ..contracts.card_import_result import CardImportResult, ImportResultStatus
from ..contracts.card_import_approval import CardImportApproval, ApprovalDecision
from ..contracts.card_definition import CardDefinition, CardDefinitionStatus
from ..contracts.card_greeting import CardGreeting
from ..contracts.card_worldbook_entry import CardWorldbookEntry

from .card_source_loader import load_card_source, CardSourceLoadError
from .card_payload_parser import CardPayloadParser
from .card_format_validator import validate_card_format
from .card_security_scanner import CardSecurityScanner
from .card_greeting_sanitizer import sanitize_greeting_content
from .card_worldbook_chunk_builder import build_all_chunks

from ..storage.card_import_interfaces import (
    CardDefinitionStore, CardSourceStore, CardImportReportStore,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


class CardImportPipeline:

    def __init__(self, definition_store: CardDefinitionStore, source_store: CardSourceStore, report_store: CardImportReportStore):
        self._defs = definition_store
        self._srcs = source_store
        self._rpts = report_store
        self._parser = CardPayloadParser()
        self._scanner = CardSecurityScanner()

    def import_card(self, request: CardImportRequest) -> CardImportResult:
        trace_id = request.trace_id or _id("trace", request.request_id)
        now = _now()

        # Load
        try:
            snapshot, payload = load_card_source(request.source_path, request.source_filename, now)
        except CardSourceLoadError as e:
            return CardImportResult(result_id=_id("res", request.request_id), request_id=request.request_id,
                                    status=ImportResultStatus.VALIDATION_FAILED, error_message=f"[{e.code}] {e.message}", trace_id=trace_id)

        # Idempotency: same source_hash → return existing
        existing = self._defs.get_by_source_hash(snapshot.source_hash)
        if existing:
            return CardImportResult(result_id=_id("res", request.request_id), request_id=request.request_id,
                                    status=ImportResultStatus.ALREADY_EXISTS, logical_card_id=existing.logical_card_id,
                                    card_version=existing.card_version, source_id=existing.source_id,
                                    source_hash=existing.source_hash, name=existing.name, trace_id=trace_id)

        self._srcs.save(snapshot)

        # Parse
        profile = self._parser.parse_profile(payload)
        greetings = self._parser.parse_greetings(payload)
        wb_entries = self._parser.parse_worldbook_entries(payload)
        hints = self._parser.parse_structure_hints(payload)

        # Validate
        fmt_issues = validate_card_format(payload)
        if any(i.severity == IssueSeverity.ERROR for i in fmt_issues):
            return CardImportResult(result_id=_id("res", request.request_id), request_id=request.request_id,
                                    status=ImportResultStatus.VALIDATION_FAILED, source_id=snapshot.source_id,
                                    source_hash=snapshot.source_hash, error_message="Format validation failed", trace_id=trace_id)

        # Security scan
        q_records, sec_issues, sec_summary = self._scanner.scan(payload)
        all_issues = fmt_issues + sec_issues
        all_q = list(q_records)

        # Sanitize greetings
        san_greetings: list[dict] = []
        for g in greetings:
            safe, gq = sanitize_greeting_content(g.safe_display_content, g.greeting_id, g.source_path)
            all_q.extend(gq)
            san_greetings.append({**g.to_dict(), "safe_display_content": safe, "quarantine_refs": [r.record_id for r in gq]})

        # Chunks
        wb_entries, wb_chunks = build_all_chunks(wb_entries)

        # Determine logical_card_id and card_version
        if request.existing_logical_card_id:
            # Import as new version of existing logical card
            logical_card_id = request.existing_logical_card_id
            card_version = self._defs.get_next_version(logical_card_id)
        else:
            # New logical card
            logical_card_id = f"lcid_{uuid.uuid4().hex[:16]}"
            card_version = 1

        report_id = _id("rpt", f"{request.request_id}_{logical_card_id}")

        # Report
        report = CardImportReport(
            report_id=report_id, request_id=request.request_id, source_id=snapshot.source_id,
            logical_card_id=logical_card_id, card_version=card_version, trace_id=trace_id,
            status="warnings" if all_issues else "ok", name=profile.name, spec=snapshot.spec,
            greeting_count=len(san_greetings), worldbook_entry_count=len(wb_entries),
            worldbook_chunk_count=len(wb_chunks), quarantine_count=len(all_q),
            structure_hint_count=len(hints.phase_hints) + len(hints.event_hints) + len(hints.variable_hints) + len(hints.relationship_hints),
            issues=all_issues, quarantine_summary=sec_summary, created_at=now,
        )
        self._rpts.save(report)

        # Definition
        defn = CardDefinition(
            logical_card_id=logical_card_id, card_version=card_version, source_id=snapshot.source_id,
            source_hash=snapshot.source_hash, name=profile.name, display_name=profile.name,
            status=CardDefinitionStatus.STAGED, profile=profile.to_dict(),
            greetings=san_greetings,
            worldbook_catalog=[e.to_dict() for e in wb_entries],
            worldbook_chunks=[c.to_dict() for c in wb_chunks],
            structure_hints=hints.to_dict(),
            quarantine_summary={"total": len(all_q), "by_kind": sec_summary.get("kind_counts", {}), "variables_detected": sec_summary.get("variables_detected", False)},
            import_report_ref=report_id, created_at=now, updated_at=now, trace_id=trace_id,
        )
        self._defs.save(defn)

        return CardImportResult(result_id=_id("res", request.request_id), request_id=request.request_id,
                                status=ImportResultStatus.APPROVAL_REQUIRED, logical_card_id=logical_card_id, card_version=card_version,
                                source_id=snapshot.source_id, source_hash=snapshot.source_hash,
                                name=profile.name, report_ref=report_id, trace_id=trace_id)

    def approve_card(self, approval: CardImportApproval) -> CardDefinition | None:
        defn = self._defs.load(approval.logical_card_id, approval.card_version)
        if not defn:
            return None
        new_status = CardDefinitionStatus.READY if approval.decision == ApprovalDecision.APPROVE else CardDefinitionStatus.REJECTED if approval.decision == ApprovalDecision.REJECT else None
        if not new_status:
            return None
        self._defs.update_status(approval.logical_card_id, approval.card_version, new_status)
        if new_status == CardDefinitionStatus.READY:
            for d in self._defs.list_all():
                if d.logical_card_id == approval.logical_card_id and d.card_version < approval.card_version and d.status == CardDefinitionStatus.READY:
                    self._defs.update_status(d.logical_card_id, d.card_version, CardDefinitionStatus.SUPERSEDED)
        return self._defs.load(approval.logical_card_id, approval.card_version)

    def get_definition(self, logical_card_id: str, card_version: int = 0) -> CardDefinition | None:
        return self._defs.load(logical_card_id, card_version) if card_version > 0 else self._defs.get_latest(logical_card_id)

    def get_report(self, report_id: str) -> CardImportReport | None:
        return self._rpts.load(report_id)

    def list_definitions(self, status: str = "") -> list[CardDefinition]:
        return self._defs.list_all(status)
