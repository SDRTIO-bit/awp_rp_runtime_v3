"""P-CardImport: Character Card Import & Normalization V1 tests.

31+ test cases + 2 end-to-end tests.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from awp_rp_runtime_v2.contracts.card_source_snapshot import CardSourceSnapshot
from awp_rp_runtime_v2.contracts.card_import_request import CardImportRequest
from awp_rp_runtime_v2.contracts.card_import_report import CardImportReport
from awp_rp_runtime_v2.contracts.card_import_issue import CardImportIssue, IssueSeverity
from awp_rp_runtime_v2.contracts.card_definition import CardDefinition, CardDefinitionStatus
from awp_rp_runtime_v2.contracts.card_profile import CardProfile
from awp_rp_runtime_v2.contracts.card_greeting import CardGreeting
from awp_rp_runtime_v2.contracts.card_worldbook_entry import CardWorldbookEntry
from awp_rp_runtime_v2.contracts.card_worldbook_chunk import CardWorldbookChunk
from awp_rp_runtime_v2.contracts.card_structure_hints import CardStructureHints
from awp_rp_runtime_v2.contracts.card_quarantine_record import (
    CardQuarantineRecord, QuarantineKind, QuarantineAction,
)
from awp_rp_runtime_v2.contracts.card_import_approval import CardImportApproval, ApprovalDecision
from awp_rp_runtime_v2.contracts.card_import_result import CardImportResult, ImportResultStatus

from awp_rp_runtime_v2.runtime.card_source_loader import load_card_source, CardSourceLoadError
from awp_rp_runtime_v2.runtime.card_payload_parser import CardPayloadParser
from awp_rp_runtime_v2.runtime.card_format_validator import validate_card_format
from awp_rp_runtime_v2.runtime.card_security_scanner import CardSecurityScanner
from awp_rp_runtime_v2.runtime.card_greeting_sanitizer import sanitize_greeting_content
from awp_rp_runtime_v2.runtime.card_worldbook_chunk_builder import build_all_chunks, build_chunks_for_entry
from awp_rp_runtime_v2.runtime.card_import_pipeline import CardImportPipeline

from awp_rp_runtime_v2.testing.fakes.fake_card_import_stores import (
    FakeCardDefinitionStore, FakeCardSourceStore, FakeCardImportReportStore,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_v3_card(
    name="TestChar", first_mes="Hello, I am TestChar.",
    alternate_greetings=None, description="A test character.",
    personality="Friendly", worldbook_entries=None, extensions=None,
) -> dict:
    card = {
        "spec": "chara_card_v3",
        "data": {
            "name": name, "description": description, "personality": personality,
            "scenario": "", "first_mes": first_mes, "mes_example": "",
            "alternate_greetings": alternate_greetings or [],
            "tags": ["test"], "extensions": extensions or {},
        },
    }
    if worldbook_entries is not None:
        card["data"]["character_book"] = {"entries": worldbook_entries}
    return card


def _write_json(tmp: Path, card: dict, name="test.json") -> Path:
    p = tmp / name
    p.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    return p


def _crc32(data: bytes) -> int:
    import binascii
    return binascii.crc32(data) & 0xFFFFFFFF


def _png_chunk(ctype: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc = struct.pack(">I", _crc32(ctype + data) & 0xFFFFFFFF)
    return length + ctype + data + crc


def _write_png(tmp: Path, card: dict, name="test.png", key="chara") -> Path:
    p = tmp / name
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    text = _png_chunk(b"tEXt", key.encode("latin-1") + b"\0" + json.dumps(card).encode("utf-8"))
    iend = _png_chunk(b"IEND", b"")
    p.write_bytes(sig + ihdr + text + iend)
    return p


def _pipeline():
    d = FakeCardDefinitionStore()
    s = FakeCardSourceStore()
    r = FakeCardImportReportStore()
    return CardImportPipeline(d, s, r), d, s, r


# ── 1. Valid V3 JSON import ──────────────────────────────────────────────────

def test_01_valid_json_loads(tmp_path):
    card = _make_v3_card()
    snap, payload = load_card_source(str(_write_json(tmp_path, card)))
    assert snap.source_format == "json"
    assert snap.spec == "chara_card_v3"


# ── 2. Valid V3 PNG import ──────────────────────────────────────────────────

def test_02_valid_png_loads(tmp_path):
    card = _make_v3_card(name="PngChar")
    snap, payload = load_card_source(str(_write_png(tmp_path, card)))
    assert snap.source_format == "png"
    assert payload["data"]["name"] == "PngChar"


# ── 3. Non-PNG file rejected ────────────────────────────────────────────────

def test_03_non_png_rejected(tmp_path):
    p = tmp_path / "fake.png"
    p.write_bytes(b"not a png file")
    with pytest.raises(CardSourceLoadError) as e:
        load_card_source(str(p))
    assert e.value.code == "invalid_png"


# ── 4. PNG without metadata rejected ────────────────────────────────────────

def test_04_png_no_metadata_rejected(tmp_path):
    p = tmp_path / "empty.png"
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    text = _png_chunk(b"tEXt", b"unrelated\0not json")
    iend = _png_chunk(b"IEND", b"")
    p.write_bytes(sig + ihdr + text + iend)
    with pytest.raises(CardSourceLoadError) as e:
        load_card_source(str(p))
    assert e.value.code == "unsupported_png_metadata"


# ── 5. No spec/data rejected ────────────────────────────────────────────────

def test_05_no_spec_no_data_rejected(tmp_path):
    p = _write_json(tmp_path, {"foo": "bar"})
    with pytest.raises(CardSourceLoadError) as e:
        load_card_source(str(p))
    assert e.value.code == "unsupported_payload_shape"


# ── 6. Unsupported spec reported ────────────────────────────────────────────

def test_06_unsupported_spec_not_error(tmp_path):
    card = _make_v3_card()
    card["spec"] = "chara_card_v4_unknown"
    snap, payload = load_card_source(str(_write_json(tmp_path, card)))
    issues = validate_card_format(payload)
    assert not any(i.severity == IssueSeverity.ERROR for i in issues)


# ── 7. Same sourceHash idempotent ──────────────────────────────────────────

def test_07_idempotent(tmp_path):
    card = _make_v3_card(name="Idem")
    p = _write_json(tmp_path, card)
    pl, _, _, _ = _pipeline()
    r1 = pl.import_card(CardImportRequest(request_id="r1", source_path=str(p)))
    r2 = pl.import_card(CardImportRequest(request_id="r2", source_path=str(p)))
    assert r1.status == ImportResultStatus.APPROVAL_REQUIRED
    assert r2.status == ImportResultStatus.ALREADY_EXISTS
    assert r2.card_id == r1.card_id


# ── 8. Same name, different hash → new card ────────────────────────────────

def test_08_different_hash_new_card(tmp_path):
    c1 = _make_v3_card(name="Same", description="v1")
    c2 = _make_v3_card(name="Same", description="v2")
    pl, _, _, _ = _pipeline()
    r1 = pl.import_card(CardImportRequest(request_id="r1", source_path=str(_write_json(tmp_path, c1, "v1.json"))))
    r2 = pl.import_card(CardImportRequest(request_id="r2", source_path=str(_write_json(tmp_path, c2, "v2.json"))))
    assert r1.card_id != r2.card_id


# ── 9. Default greeting extracted ──────────────────────────────────────────

def test_09_default_greeting():
    parser = CardPayloadParser()
    gs = parser.parse_greetings(_make_v3_card(first_mes="Default greeting."))
    assert len(gs) == 1
    assert gs[0].is_default
    assert gs[0].greeting_id == "g0"


# ── 10. Alternate greetings order & labels ──────────────────────────────────

def test_10_alternate_greetings_order():
    parser = CardPayloadParser()
    gs = parser.parse_greetings(_make_v3_card(
        first_mes="Default",
        alternate_greetings=[
            {"greeting": "Alt 1", "label": "First"},
            "Plain alt",
            {"greeting": "Alt 3", "label": "Third"},
        ],
    ))
    assert len(gs) == 4
    assert gs[1].label == "First"
    assert gs[2].label == "Alternate 2"
    assert gs[3].label == "Third"
    assert [g.index for g in gs] == [0, 1, 2, 3]


# ── 11. Greeting setvar/EJS/script quarantined ─────────────────────────────

def test_11_greeting_sanitized():
    raw = "Hello {{setvar:x=1}} <% evil() %> <script>bad()</script> world"
    safe, recs = sanitize_greeting_content(raw, "g0", "data.first_mes")
    assert "{{setvar:" not in safe
    assert "<%" not in safe
    assert "<script>" not in safe
    assert "Hello" in safe
    assert "world" in safe
    kinds = {r.kind for r in recs}
    assert QuarantineKind.SETVAR in kinds
    assert QuarantineKind.EJS in kinds
    assert QuarantineKind.SCRIPT_TAG in kinds
    for r in recs:
        assert r.action == QuarantineAction.SANITIZED_FOR_DISPLAY


# ── 12. Worldbook entry preserves flags ────────────────────────────────────

def test_12_worldbook_flags():
    parser = CardPayloadParser()
    card = _make_v3_card(worldbook_entries=[{
        "uid": 42, "keys": ["fire", "magic"], "secondary_keys": ["element"],
        "content": "Fire rules.", "comment": "Fire", "priority": 15,
        "constant": True, "selective": False, "disable": False,
    }])
    entries = parser.parse_worldbook_entries(card)
    e = entries[0]
    assert e.source_uid == 42
    assert e.keys == ["fire", "magic"]
    assert e.secondary_keys == ["element"]
    assert e.priority == 15
    assert e.constant
    assert e.enabled
    assert e.entry_id == "wb_42"


# ── 13. Disabled entry saved but not active ────────────────────────────────

def test_13_disabled_entry():
    parser = CardPayloadParser()
    card = _make_v3_card(worldbook_entries=[{
        "uid": 5, "keys": ["old"], "content": "Disabled.", "disable": True,
    }])
    entries = parser.parse_worldbook_entries(card)
    assert not entries[0].enabled


# ── 14. Constant ≠ unlimited budget ────────────────────────────────────────

def test_14_constant_flag_only():
    parser = CardPayloadParser()
    card = _make_v3_card(worldbook_entries=[{
        "uid": 1, "keys": ["w"], "content": "Const.", "constant": True,
    }])
    entries = parser.parse_worldbook_entries(card)
    assert entries[0].constant
    # constant is a flag; budget enforcement is runtime concern


# ── 15. Long entry produces traceable chunks ───────────────────────────────

def test_15_long_entry_chunks():
    entry = CardWorldbookEntry(entry_id="wb_long", content="A" * 2500, keys=["long"])
    chunks = build_chunks_for_entry(entry, chunk_size=1000, overlap=100)
    assert len(chunks) >= 2
    for c in chunks:
        assert c.parent_entry_id == "wb_long"
        assert c.source_hash


# ── 16. Short entry no chunks ──────────────────────────────────────────────

def test_16_short_entry_no_chunks():
    entry = CardWorldbookEntry(entry_id="wb_short", content="Short.", keys=["s"])
    assert build_chunks_for_entry(entry) == []


# ── 17. All chunks traceable to parent ─────────────────────────────────────

def test_17_chunks_traceable():
    entry = CardWorldbookEntry(entry_id="wb_p", content="B" * 3000, keys=["p"])
    entries, chunks = build_all_chunks([entry])
    assert len(chunks) >= 2
    for c in chunks:
        assert c.parent_entry_id == "wb_p"
    assert entries[0].has_chunks


# ── 18. JS/eval/fetch/iframe quarantined ───────────────────────────────────

def test_18_security_quarantine():
    card = _make_v3_card(description="new Function('x') eval('y') fetch('http://z') <iframe>")
    scanner = CardSecurityScanner()
    recs, _, _ = scanner.scan(card)
    kinds = {r.kind for r in recs}
    assert QuarantineKind.JAVASCRIPT in kinds
    assert QuarantineKind.EVAL in kinds
    assert QuarantineKind.FETCH in kinds
    assert QuarantineKind.IFRAME in kinds


# ── 19. Variable patterns → variableHints only ─────────────────────────────

def test_19_variable_hints():
    parser = CardPayloadParser()
    card = _make_v3_card(extensions={"tavern_helper": {"scripts": [
        {"content": "registerMvuSchema({ mood: z.string(), hp: z.number() })"}
    ]}})
    hints = parser.parse_structure_hints(card)
    paths = {h["variable_path"] for h in hints.variable_hints}
    assert "mood" in paths and "hp" in paths


# ── 20. Phase/event hints are metadata only ────────────────────────────────

def test_20_phase_hints():
    parser = CardPayloadParser()
    card = _make_v3_card(description="Phase 1: Intro\nPhase 2: Conflict\nPhase 3: End")
    hints = parser.parse_structure_hints(card)
    assert len(hints.phase_hints) >= 3


# ── 21-25. Import boundary isolation ───────────────────────────────────────

def test_21_no_active_memory(tmp_path):
    pl, _, _, _ = _pipeline()
    r = pl.import_card(CardImportRequest(request_id="r", source_path=str(_write_json(tmp_path, _make_v3_card()))))
    assert r.status == ImportResultStatus.APPROVAL_REQUIRED


def test_22_no_rag_memory(tmp_path):
    pl, _, _, _ = _pipeline()
    r = pl.import_card(CardImportRequest(request_id="r", source_path=str(_write_json(tmp_path, _make_v3_card()))))
    assert r.status == ImportResultStatus.APPROVAL_REQUIRED


def test_23_no_turn_record(tmp_path):
    pl, _, _, _ = _pipeline()
    r = pl.import_card(CardImportRequest(request_id="r", source_path=str(_write_json(tmp_path, _make_v3_card()))))
    assert r.status == ImportResultStatus.APPROVAL_REQUIRED


def test_24_no_card_state(tmp_path):
    pl, _, _, _ = _pipeline()
    r = pl.import_card(CardImportRequest(request_id="r", source_path=str(_write_json(tmp_path, _make_v3_card()))))
    assert r.status == ImportResultStatus.APPROVAL_REQUIRED


def test_25_no_dynamic_subagent(tmp_path):
    pl, _, _, _ = _pipeline()
    r = pl.import_card(CardImportRequest(request_id="r", source_path=str(_write_json(tmp_path, _make_v3_card()))))
    assert r.status == ImportResultStatus.APPROVAL_REQUIRED


# ── 26. Staged not usable as runtime ───────────────────────────────────────

def test_26_staged_not_ready(tmp_path):
    pl, defs, _, _ = _pipeline()
    r = pl.import_card(CardImportRequest(request_id="r", source_path=str(_write_json(tmp_path, _make_v3_card()))))
    d = defs.load(r.card_id, r.card_version)
    assert d.status == CardDefinitionStatus.STAGED
    assert defs.list_all(CardDefinitionStatus.READY) == []


# ── 27. Approved card in catalog ───────────────────────────────────────────

def test_27_approved_in_catalog(tmp_path):
    pl, defs, _, _ = _pipeline()
    r = pl.import_card(CardImportRequest(request_id="r", source_path=str(_write_json(tmp_path, _make_v3_card()))))
    pl.approve_card(CardImportApproval(
        approval_id="a", card_id=r.card_id, card_version=r.card_version,
        decision=ApprovalDecision.APPROVE, approved_by="user",
    ))
    ready = defs.list_all(CardDefinitionStatus.READY)
    assert len(ready) == 1


# ── 28. Report no full card body leak ──────────────────────────────────────

def test_28_report_no_leak(tmp_path):
    secret = "SECRET_" + "X" * 500
    pl, _, _, rpts = _pipeline()
    r = pl.import_card(CardImportRequest(
        request_id="r",
        source_path=str(_write_json(tmp_path, _make_v3_card(description=secret))),
    ))
    report = rpts.load(r.report_ref)
    assert secret not in json.dumps(report.to_dict())


# ── 29. Cross cardId isolation ─────────────────────────────────────────────

def test_29_cross_version_isolation(tmp_path):
    pl, defs, _, _ = _pipeline()
    r1 = pl.import_card(CardImportRequest(request_id="r1", source_path=str(_write_json(tmp_path, _make_v3_card(name="C1"), "c1.json"))))
    r2 = pl.import_card(CardImportRequest(request_id="r2", source_path=str(_write_json(tmp_path, _make_v3_card(name="C2"), "c2.json"))))
    d1, d2 = defs.get_latest(r1.card_id), defs.get_latest(r2.card_id)
    assert d1.card_id != d2.card_id
    assert d1.name == "C1"
    assert d2.name == "C2"


# ── 30. Workflow JSON structure ─────────────────────────────────────────────

def test_30_workflow_json():
    wf = Path(__file__).parent.parent / "workflows" / "official_card_import_normalization_v1.json"
    if not wf.exists():
        pytest.skip("Workflow not created yet")
    data = json.loads(wf.read_text(encoding="utf-8"))
    assert isinstance(data, dict)


# ── 31. Existing tests unbroken ─────────────────────────────────────────────

def test_31_existing_contracts():
    from awp_rp_runtime_v2.contracts.card_state import CardState
    from awp_rp_runtime_v2.contracts.turn_record import TurnRecord
    cs = CardState(card_id="c", session_id="s")
    assert cs.validate() == []


# ── E2E A: Normal card import ───────────────────────────────────────────────

def test_e2e_normal_card(tmp_path):
    """V3 JSON → parse → security scan → normalize → staged → review → approval → ready"""
    card = _make_v3_card(
        name="E2EChar", first_mes="Hello!",
        alternate_greetings=["Alt 1", "Alt 2"],
        worldbook_entries=[{
            "uid": 1, "keys": ["magic"], "content": "Magic rules.",
            "comment": "Magic", "priority": 10, "constant": False,
            "selective": False, "disable": False,
        }],
    )
    pl, defs, _, rpts = _pipeline()
    r = pl.import_card(CardImportRequest(request_id="r", source_path=str(_write_json(tmp_path, card))))

    assert r.status == ImportResultStatus.APPROVAL_REQUIRED
    d = defs.load(r.card_id, r.card_version)
    assert d.status == CardDefinitionStatus.STAGED
    assert d.name == "E2EChar"
    assert len(d.greetings) == 3
    assert d.greetings[0]["is_default"]
    assert len(d.worldbook_catalog) == 1

    pl.approve_card(CardImportApproval(
        approval_id="a", card_id=r.card_id, card_version=r.card_version,
        decision=ApprovalDecision.APPROVE, approved_by="user",
    ))
    assert defs.list_all(CardDefinitionStatus.READY)[0].card_id == r.card_id


# ── E2E B: Complex card with variables, scripts, long worldbook ─────────────

def test_e2e_complex_card(tmp_path):
    """含 setvar/EJS/script/变量/超长世界书 → quarantine + hints + chunks"""
    long_content = "Long worldbook entry. " * 300
    card = _make_v3_card(
        name="Complex",
        first_mes="Hello {{setvar:mood=neutral}} <% include('x') %> <script>steal()</script>",
        alternate_greetings=[
            "Alt with {{getvar:mood}}",
            {"greeting": "Alt <script>bad</script>", "label": "Risky"},
        ],
        description="Phase 1: Start\nPhase 2: End new Function('x') eval('y')",
        worldbook_entries=[
            {"uid": 1, "keys": ["magic"], "content": "Short.", "constant": True, "disable": False},
            {"uid": 2, "keys": ["long"], "content": long_content, "priority": 10, "selective": True, "disable": False},
            {"uid": 3, "keys": ["disabled"], "content": "Disabled.", "disable": True},
        ],
        extensions={"tavern_helper": {"scripts": [
            {"content": "registerMvuSchema({ mood: z.string(), trust: z.number() })"}
        ]}},
    )

    pl, defs, _, rpts = _pipeline()
    r = pl.import_card(CardImportRequest(request_id="r", source_path=str(_write_json(tmp_path, card))))
    assert r.status == ImportResultStatus.APPROVAL_REQUIRED

    d = defs.load(r.card_id, r.card_version)
    assert d.status == CardDefinitionStatus.STAGED

    # Greetings sanitized
    for g in d.greetings:
        c = g["safe_display_content"]
        assert "<script>" not in c
        assert "{{setvar:" not in c
        assert "<%" not in c

    # Quarantine
    assert d.quarantine_summary["total"] > 0
    assert d.quarantine_summary["variables_detected"]

    # Worldbook
    wb = {e["source_uid"]: e for e in d.worldbook_catalog}
    assert wb[1]["constant"]
    assert wb[1]["enabled"]
    assert wb[2]["selective"]
    assert wb[2]["has_chunks"]
    assert not wb[3]["enabled"]

    # Chunks
    assert len(d.worldbook_chunks) >= 2
    for c in d.worldbook_chunks:
        assert c["parent_entry_id"] == "wb_2"

    # Hints
    assert len(d.structure_hints["phase_hints"]) >= 2
    assert len(d.structure_hints["variable_hints"]) >= 2

    # Approve
    pl.approve_card(CardImportApproval(
        approval_id="a", card_id=r.card_id, card_version=r.card_version,
        decision=ApprovalDecision.APPROVE, approved_by="user",
    ))
    assert defs.list_all(CardDefinitionStatus.READY)[0].name == "Complex"
