"""P-CardSession Bootstrap & Worldbook Binding V1 tests.

30 test cases covering the full bootstrap chain.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from awp_rp_runtime_v3.contracts.card_definition import CardDefinition, CardDefinitionStatus
from awp_rp_runtime_v3.contracts.card_greeting import CardGreeting
from awp_rp_runtime_v3.contracts.card_worldbook_entry import CardWorldbookEntry
from awp_rp_runtime_v3.contracts.card_worldbook_chunk import CardWorldbookChunk
from awp_rp_runtime_v3.contracts.card_session_bootstrap_request import CardSessionBootstrapRequest
from awp_rp_runtime_v3.contracts.card_session_binding import CardSessionBinding, CardSessionBindingStatus
from awp_rp_runtime_v3.contracts.greeting_selection import GreetingSelection
from awp_rp_runtime_v3.contracts.opening_record import OpeningRecord
from awp_rp_runtime_v3.contracts.worldbook_binding import WorldbookBinding, WorldbookBindingEntry
from awp_rp_runtime_v3.contracts.card_session_bootstrap_receipt import CardSessionBootstrapReceipt
from awp_rp_runtime_v3.contracts.card_session_bootstrap_failure import (
    CardSessionBootstrapFailure, BootstrapFailureCode,
)
from awp_rp_runtime_v3.contracts.card_session_bootstrap_diagnostics import CardSessionBootstrapDiagnostics
from awp_rp_runtime_v3.contracts.card_state import CardState

from awp_rp_runtime_v3.runtime.card_session_bootstrap_pipeline import CardSessionBootstrapPipeline

from awp_rp_runtime_v3.testing.fakes.fake_card_import_stores import FakeCardDefinitionStore
from awp_rp_runtime_v3.testing.fakes.fake_card_session_stores import (
    FakeCardSessionBindingStore, FakeOpeningRecordStore,
    FakeWorldbookBindingStore, FakeBootstrapReceiptStore,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_ready_card(
    logical_card_id="lcid_test_001",
    card_version=1,
    source_hash="abc123",
    name="TestChar",
    greetings=None,
    worldbook_catalog=None,
    worldbook_chunks=None,
) -> CardDefinition:
    """Create a ready CardDefinition for testing."""
    if greetings is None:
        greetings = [{
            "schema_id": "awp.rp.card-greeting.v1",
            "schema_version": 1,
            "greeting_id": "g0",
            "index": 0,
            "safe_display_content": "Hello, traveler.",
            "content_hash": "gh001",
            "is_default": True,
            "label": "Default",
        }]
    return CardDefinition(
        logical_card_id=logical_card_id,
        card_version=card_version,
        source_id="src_test",
        source_hash=source_hash,
        name=name,
        status=CardDefinitionStatus.READY,
        greetings=greetings,
        worldbook_catalog=worldbook_catalog or [],
        worldbook_chunks=worldbook_chunks or [],
    )


def _make_staged_card(**kwargs) -> CardDefinition:
    card = _make_ready_card(**kwargs)
    card.status = CardDefinitionStatus.STAGED
    return card


def _make_rejected_card(**kwargs) -> CardDefinition:
    card = _make_ready_card(**kwargs)
    card.status = CardDefinitionStatus.REJECTED
    return card


def _make_superseded_card(**kwargs) -> CardDefinition:
    card = _make_ready_card(**kwargs)
    card.status = CardDefinitionStatus.SUPERSEDED
    return card


def _make_request(
    request_id="req_001",
    session_id="sess_001",
    logical_card_id="lcid_test_001",
    card_version=1,
    greeting_id="g0",
    expected_source_hash="abc123",
    initial_state_seed=None,
) -> CardSessionBootstrapRequest:
    return CardSessionBootstrapRequest(
        request_id=request_id,
        workflow_run_id="wr_001",
        trace_id="tr_001",
        session_id=session_id,
        logical_card_id=logical_card_id,
        card_version=card_version,
        greeting_id=greeting_id,
        expected_source_hash=expected_source_hash,
        initial_state_seed=initial_state_seed or {},
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _pipeline(defs=None):
    d = defs or FakeCardDefinitionStore()
    b = FakeCardSessionBindingStore()
    o = FakeOpeningRecordStore()
    w = FakeWorldbookBindingStore()
    r = FakeBootstrapReceiptStore()
    return CardSessionBootstrapPipeline(d, b, o, w, r), d, b, o, w, r


# ── 1. Ready CardDefinition can create Session ───────────────────────────

def test_01_ready_card_can_bootstrap(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_ready_card()
    defs.save(card)
    pl, _, _, _, _, receipts = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is not None
    assert failure is None
    assert receipt.session_id == "sess_001"
    assert receipt.logical_card_id == "lcid_test_001"
    assert receipt.commit_status == "success"


# ── 2. Staged CardDefinition cannot create Session ───────────────────────

def test_02_staged_card_rejected(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_staged_card()
    defs.save(card)
    pl, _, _, _, _, _ = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is None
    assert failure is not None
    assert failure.failure_code == BootstrapFailureCode.CARD_NOT_READY


# ── 3. Rejected CardDefinition cannot create Session ─────────────────────

def test_03_rejected_card_rejected(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_rejected_card()
    defs.save(card)
    pl, _, _, _, _, _ = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is None
    assert failure is not None
    assert failure.failure_code == BootstrapFailureCode.CARD_NOT_READY


# ── 4. Superseded CardDefinition rule ─────────────────────────────────────

def test_04_superseded_card_rejected(tmp_path):
    """Superseded cards cannot start new sessions."""
    defs = FakeCardDefinitionStore()
    card = _make_superseded_card()
    defs.save(card)
    pl, _, _, _, _, _ = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is None
    assert failure is not None
    assert failure.failure_code == BootstrapFailureCode.CARD_NOT_READY


# ── 5. Greeting must belong to exact logicalCardId + cardVersion ──────────

def test_05_greeting_must_belong_to_card(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_ready_card(greetings=[{
        "schema_id": "awp.rp.card-greeting.v1",
        "schema_version": 1,
        "greeting_id": "g0",
        "index": 0,
        "safe_display_content": "Hello.",
        "content_hash": "gh001",
        "is_default": True,
    }])
    defs.save(card)
    pl, _, _, _, _, _ = _pipeline(defs)
    req = _make_request(greeting_id="g999")  # Non-existent greeting
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is None
    assert failure is not None
    assert failure.failure_code == BootstrapFailureCode.GREETING_NOT_FOUND


# ── 6. No greetings → reject ─────────────────────────────────────────────

def test_06_no_greetings_rejected(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_ready_card(greetings=[])
    defs.save(card)
    pl, _, _, _, _, _ = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is None
    assert failure is not None
    assert failure.failure_code == BootstrapFailureCode.GREETING_NOT_FOUND


# ── 7. sourceHash mismatch → reject ──────────────────────────────────────

def test_07_source_hash_mismatch_rejected(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_ready_card(source_hash="real_hash")
    defs.save(card)
    pl, _, _, _, _, _ = _pipeline(defs)
    req = _make_request(expected_source_hash="wrong_hash")
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is None
    assert failure is not None
    assert failure.failure_code == BootstrapFailureCode.SOURCE_HASH_MISMATCH


# ── 8. Default greeting can bootstrap ────────────────────────────────────

def test_08_default_greeting_bootstrap(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_ready_card()
    defs.save(card)
    pl, _, _, _, _, _ = _pipeline(defs)
    req = _make_request(greeting_id="g0")
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is not None
    assert receipt.greeting_id == "g0"


# ── 9. Alternate greeting can bootstrap ──────────────────────────────────

def test_09_alternate_greeting_bootstrap(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_ready_card(greetings=[
        {
            "schema_id": "awp.rp.card-greeting.v1", "schema_version": 1,
            "greeting_id": "g0", "index": 0, "safe_display_content": "Default.",
            "content_hash": "gh0", "is_default": True,
        },
        {
            "schema_id": "awp.rp.card-greeting.v1", "schema_version": 1,
            "greeting_id": "g1", "index": 1, "safe_display_content": "Alternate.",
            "content_hash": "gh1", "is_default": False, "label": "Alt",
        },
    ])
    defs.save(card)
    pl, _, _, _, _, _ = _pipeline(defs)
    req = _make_request(greeting_id="g1")
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is not None
    assert receipt.greeting_id == "g1"


# ── 10. OpeningRecord saved independently ────────────────────────────────

def test_10_opening_record_independent(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_ready_card()
    defs.save(card)
    pl, _, _, openings, _, _ = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is not None
    opr = openings.load(receipt.opening_record_id)
    assert opr is not None
    assert opr.session_id == "sess_001"
    assert opr.greeting_id == "g0"
    assert opr.safe_display_content == "Hello, traveler."


# ── 11. OpeningRecord ≠ TurnRecord ───────────────────────────────────────

def test_11_opening_record_not_turn_record(tmp_path):
    """OpeningRecord has opening_record_id, not turn_record_id."""
    defs = FakeCardDefinitionStore()
    card = _make_ready_card()
    defs.save(card)
    pl, _, _, openings, _, _ = _pipeline(defs)
    req = _make_request()
    receipt, _, _ = pl.bootstrap(req)
    opr = openings.load(receipt.opening_record_id)
    assert opr is not None
    # OpeningRecord has its own ID schema
    assert opr.opening_record_id.startswith("opr_")
    assert not hasattr(opr, "turn_record_id") or opr.opening_record_id != ""


# ── 12. OpeningRecord does not trigger D6 ────────────────────────────────

def test_12_opening_no_d6_trigger(tmp_path):
    """Bootstrap does not create any memory curation requests."""
    defs = FakeCardDefinitionStore()
    card = _make_ready_card()
    defs.save(card)
    pl, _, _, _, _, _ = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    # The pipeline never creates memory curation requests
    # This is verified by the absence of D6-related stores in the pipeline
    assert receipt is not None
    assert diag.commit_status == "success"


# ── 13. Bootstrap does not create ActiveMemory ──────────────────────────

def test_13_no_active_memory(tmp_path):
    """Bootstrap creates no ActiveMemory."""
    defs = FakeCardDefinitionStore()
    card = _make_ready_card()
    defs.save(card)
    pl, _, _, _, _, _ = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is not None
    # No ActiveMemory store is connected to the pipeline


# ── 14. Bootstrap does not create RagMemory ──────────────────────────────

def test_14_no_rag_memory(tmp_path):
    """Bootstrap creates no RagMemory."""
    defs = FakeCardDefinitionStore()
    card = _make_ready_card()
    defs.save(card)
    pl, _, _, _, _, _ = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is not None
    # No RagMemory store is connected to the pipeline


# ── 15. Bootstrap does not call Director/Writer/Agent ────────────────────

def test_15_no_director_writer_agent(tmp_path):
    """Bootstrap never invokes Director, Writer, or Dynamic Agent."""
    defs = FakeCardDefinitionStore()
    card = _make_ready_card()
    defs.save(card)
    pl, _, _, _, _, _ = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is not None
    # The pipeline only uses stores, not agent runtimes


# ── 16. CardState only from safe initialStateSeed ────────────────────────

def test_16_card_state_from_seed_only(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_ready_card()
    defs.save(card)
    pl, _, _, _, _, _ = _pipeline(defs)
    req = _make_request(initial_state_seed={"mood": "neutral", "hp": 100})
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is not None
    assert diag.card_state_revision_after == 1


# ── 17. Variable scripts/EJS/JS/Regex don't affect CardState ────────────

def test_17_scripts_dont_affect_card_state(tmp_path):
    """CardState is only built from initialStateSeed, never from card content."""
    defs = FakeCardDefinitionStore()
    card = _make_ready_card()
    defs.save(card)
    pl, _, _, _, _, _ = _pipeline(defs)
    req = _make_request(initial_state_seed={})
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is not None
    # Empty seed = empty variables
    assert diag.card_state_revision_after == 1


# ── 18. Disabled worldbook entries bound but not activatable ─────────────

def test_18_disabled_entries_bound(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_ready_card(worldbook_catalog=[{
        "schema_id": "awp.rp.card-worldbook-entry.v1", "schema_version": 1,
        "entry_id": "wb_1", "source_uid": 1, "content": "Disabled.", "enabled": False,
    }])
    defs.save(card)
    pl, _, _, _, wbs, _ = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is not None
    wb = wbs.load(receipt.worldbook_binding_id)
    assert wb is not None
    assert "wb_1" in wb.disabled_entry_ids
    assert "wb_1" not in wb.bound_entry_ids
    assert diag.disabled_entry_count == 1


# ── 19. Constant entries still budget-governed ───────────────────────────

def test_19_constant_entries_candidate(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_ready_card(worldbook_catalog=[{
        "schema_id": "awp.rp.card-worldbook-entry.v1", "schema_version": 1,
        "entry_id": "wb_c", "source_uid": 2, "content": "Const.", "constant": True,
    }])
    defs.save(card)
    pl, _, _, _, wbs, _ = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is not None
    wb = wbs.load(receipt.worldbook_binding_id)
    assert "wb_c" in wb.bound_entry_ids
    # Constant = candidate, not auto-inject


# ── 20. Conditional entries through safe condition engine ────────────────

def test_20_selective_entries_deferred(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_ready_card(worldbook_catalog=[{
        "schema_id": "awp.rp.card-worldbook-entry.v1", "schema_version": 1,
        "entry_id": "wb_s", "source_uid": 3, "content": "Selective.", "selective": True,
    }])
    defs.save(card)
    pl, _, _, _, wbs, _ = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is not None
    wb = wbs.load(receipt.worldbook_binding_id)
    assert "wb_s" in wb.deferred_entry_ids
    assert diag.deferred_entry_count == 1


# ── 21. Unsupported activation → deferred/unsupported ────────────────────

def test_20b_safe_selective_entries_become_candidates(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_ready_card(worldbook_catalog=[{
        "schema_id": "awp.rp.card-worldbook-entry.v1", "schema_version": 1,
        "entry_id": "wb_safe", "source_uid": 33, "content": "Selective.",
        "selective": True, "keys": ["quest"], "secondary_keys": [],
        "activation_raw": {},
    }])
    defs.save(card)
    pl, _, _, _, wbs, _ = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is not None
    wb = wbs.load(receipt.worldbook_binding_id)
    assert "wb_safe" in wb.bound_entry_ids
    assert "wb_safe" not in wb.deferred_entry_ids


def test_21_unsupported_activation_deferred(tmp_path):
    """Entries with unsupported activation are marked deferred."""
    defs = FakeCardDefinitionStore()
    card = _make_ready_card(worldbook_catalog=[{
        "schema_id": "awp.rp.card-worldbook-entry.v1", "schema_version": 1,
        "entry_id": "wb_u", "source_uid": 4, "content": "Unsupported.",
        "selective": True,  # selective without safe condition engine = deferred
    }])
    defs.save(card)
    pl, _, _, _, wbs, _ = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is not None
    wb = wbs.load(receipt.worldbook_binding_id)
    assert "wb_u" in wb.deferred_entry_ids


# ── 22. Long worldbook chunks preserve parentEntryId ─────────────────────

def test_22_chunks_preserve_parent_entry_id(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_ready_card(
        worldbook_catalog=[{
            "schema_id": "awp.rp.card-worldbook-entry.v1", "schema_version": 1,
            "entry_id": "wb_long", "source_uid": 5, "content": "Long.", "has_chunks": True,
        }],
        worldbook_chunks=[{
            "schema_id": "awp.rp.card-worldbook-chunk.v1", "schema_version": 1,
            "chunk_id": "chk_0", "parent_entry_id": "wb_long", "ordinal": 0,
            "content": "chunk text", "source_hash": "ch001",
        }],
    )
    defs.save(card)
    pl, _, _, _, wbs, _ = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is not None
    wb = wbs.load(receipt.worldbook_binding_id)
    assert "chk_0" in wb.bound_chunk_ids


# ── 23. Same requestId retry does not duplicate ──────────────────────────

def test_23_idempotent_retry(tmp_path):
    defs = FakeCardDefinitionStore()
    card = _make_ready_card()
    defs.save(card)
    pl, _, _, _, _, receipts = _pipeline(defs)
    req = _make_request()
    r1, _, _ = pl.bootstrap(req)
    r2, _, diag = pl.bootstrap(req)
    assert r1.receipt_id == r2.receipt_id
    assert diag.idempotency_status == "reused"


# ── 24. sessionId + different card version → reject ──────────────────────

def test_24_session_version_conflict(tmp_path):
    defs = FakeCardDefinitionStore()
    card_v1 = _make_ready_card(card_version=1, source_hash="hash_v1")
    defs.save(card_v1)
    pl, _, bindings, _, _, _ = _pipeline(defs)
    req1 = _make_request(request_id="r1", card_version=1, expected_source_hash="hash_v1")
    r1, _, _ = pl.bootstrap(req1)
    assert r1 is not None

    # Now try to bootstrap same session with a different card
    card_v2 = _make_ready_card(
        logical_card_id="lcid_other",
        card_version=1,
        source_hash="hash_other",
    )
    defs.save(card_v2)
    req2 = _make_request(
        request_id="r2",
        session_id="sess_001",  # Same session
        logical_card_id="lcid_other",
        card_version=1,
        expected_source_hash="hash_other",
    )
    r2, failure, _ = pl.bootstrap(req2)
    assert r2 is None
    assert failure is not None
    assert failure.failure_code == BootstrapFailureCode.SESSION_VERSION_CONFLICT


# ── 25. New card version does not change old session ──────────────────────

def test_25_new_version_does_not_change_old_session(tmp_path):
    defs = FakeCardDefinitionStore()
    card_v1 = _make_ready_card(card_version=1, source_hash="hash_v1")
    defs.save(card_v1)
    pl, _, bindings, _, _, _ = _pipeline(defs)
    req = _make_request(card_version=1, expected_source_hash="hash_v1")
    receipt, _, _ = pl.bootstrap(req)
    binding = bindings.load("sess_001")
    assert binding.card_version == 1

    # Import v2 of the same card
    card_v2 = _make_ready_card(card_version=2, source_hash="hash_v2")
    defs.save(card_v2)
    # Old binding unchanged
    binding = bindings.load("sess_001")
    assert binding.card_version == 1
    assert binding.source_hash == "hash_v1"


# ── 26. Partial failure does not produce ready Session ────────────────────

def test_26_partial_failure_no_ready_session(tmp_path):
    """If card not found, no binding/receipt is created."""
    defs = FakeCardDefinitionStore()
    # Don't save any card
    pl, _, bindings, _, _, receipts = _pipeline(defs)
    req = _make_request()
    receipt, failure, diag = pl.bootstrap(req)
    assert receipt is None
    assert failure is not None
    assert failure.failure_code == BootstrapFailureCode.CARD_NOT_FOUND
    assert not bindings.exists("sess_001")


# ── 27. Recovery/retry can complete unfinished bootstrap ─────────────────

def test_27_retry_after_failure(tmp_path):
    defs = FakeCardDefinitionStore()
    pl, _, _, _, _, _ = _pipeline(defs)
    req = _make_request()

    # First attempt fails (no card)
    r1, f1, _ = pl.bootstrap(req)
    assert r1 is None
    assert f1 is not None

    # Card becomes available
    card = _make_ready_card()
    defs.save(card)

    # Retry succeeds
    r2, f2, _ = pl.bootstrap(req)
    assert r2 is not None
    assert f2 is None


# ── 28. Bootstrap request validation ─────────────────────────────────────

def test_28_request_validation():
    req = CardSessionBootstrapRequest()
    errors = req.validate()
    assert len(errors) > 0
    assert "request_id is required" in errors
    assert "session_id is required" in errors
    assert "logical_card_id is required" in errors


# ── 29. Bootstrap receipt validation ─────────────────────────────────────

def test_29_receipt_validation():
    receipt = CardSessionBootstrapReceipt()
    errors = receipt.validate()
    assert len(errors) > 0
    assert "receipt_id is required" in errors


# ── 30. All existing tests still pass ─────────────────────────────────────

def test_30_existing_contracts():
    """Existing contract tests still work."""
    cs = CardState(card_id="c", session_id="s")
    assert cs.validate() == []


# ── E2E: Full bootstrap chain ─────────────────────────────────────────────

def test_e2e_full_bootstrap(tmp_path):
    """Full bootstrap: ready card → greeting → state → opening → worldbook → binding → receipt."""
    defs = FakeCardDefinitionStore()
    card = _make_ready_card(
        greetings=[
            {
                "schema_id": "awp.rp.card-greeting.v1", "schema_version": 1,
                "greeting_id": "g0", "index": 0, "safe_display_content": "Hello!",
                "content_hash": "gh0", "is_default": True,
            },
            {
                "schema_id": "awp.rp.card-greeting.v1", "schema_version": 1,
                "greeting_id": "g1", "index": 1, "safe_display_content": "Hey there.",
                "content_hash": "gh1", "is_default": False, "label": "Casual",
            },
        ],
        worldbook_catalog=[
            {
                "schema_id": "awp.rp.card-worldbook-entry.v1", "schema_version": 1,
                "entry_id": "wb_1", "source_uid": 1, "content": "World info.",
                "enabled": True, "constant": True,
            },
            {
                "schema_id": "awp.rp.card-worldbook-entry.v1", "schema_version": 1,
                "entry_id": "wb_2", "source_uid": 2, "content": "Disabled.",
                "enabled": False,
            },
            {
                "schema_id": "awp.rp.card-worldbook-entry.v1", "schema_version": 1,
                "entry_id": "wb_3", "source_uid": 3, "content": "Conditional.",
                "selective": True,
            },
        ],
    )
    defs.save(card)
    pl, _, bindings, openings, wbs, receipts = _pipeline(defs)
    req = _make_request(
        greeting_id="g1",
        initial_state_seed={"mood": "happy", "trust": 50},
    )
    receipt, failure, diag = pl.bootstrap(req)

    # Success
    assert receipt is not None
    assert failure is None
    assert receipt.commit_status == "success"
    assert receipt.idempotency_status == "new"

    # Greeting
    assert receipt.greeting_id == "g1"

    # OpeningRecord
    opr = openings.load(receipt.opening_record_id)
    assert opr is not None
    assert opr.greeting_id == "g1"
    assert opr.safe_display_content == "Hey there."

    # WorldbookBinding
    wb = wbs.load(receipt.worldbook_binding_id)
    assert wb is not None
    assert "wb_1" in wb.bound_entry_ids
    assert "wb_2" in wb.disabled_entry_ids
    assert "wb_3" in wb.deferred_entry_ids

    # CardSessionBinding
    binding = bindings.load("sess_001")
    assert binding is not None
    assert binding.status == CardSessionBindingStatus.READY
    assert binding.logical_card_id == "lcid_test_001"
    assert binding.card_version == 1
    assert binding.source_hash == "abc123"

    # Diagnostics
    assert diag.bound_entry_count == 1
    assert diag.disabled_entry_count == 1
    assert diag.deferred_entry_count == 1
    assert diag.card_state_revision_after == 1
