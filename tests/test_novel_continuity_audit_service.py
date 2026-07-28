from __future__ import annotations

import pytest

from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan
from awp_rp_runtime_v3.contracts.novel_character import NovelCharacter
from awp_rp_runtime_v3.contracts.novel_draft import ChapterDraft
from awp_rp_runtime_v3.contracts.novel_project import NovelProject
from awp_rp_runtime_v3.contracts.novel_revision import (
    FindingDisposition,
    FindingDispositionStatus,
)
from awp_rp_runtime_v3.runtime.novel_continuity_audit_service import (
    NovelContinuityAuditService,
)



@pytest.fixture
def reg(tmp_path):
    from awp_rp_runtime_v3.runtime.session_runtime_registry import (
        SessionRuntimeStoreRegistry,
    )
    from awp_rp_runtime_v3.storage.sqlite.database import Database

    db = Database(str(tmp_path / "audit.db"))
    db.initialize()
    return SessionRuntimeStoreRegistry(db)


def _seed(reg, *, text: str) -> None:
    reg.novel_project_store.create(NovelProject(project_id="p1"))
    reg.novel_chapter_plan_store.save(
        ChapterPlan(chapter_id="ch1", project_id="p1", chapter_index=1, title="第一章")
    )
    reg.novel_chapter_draft_store.save(
        ChapterDraft(
            draft_id="draft-ch1-r1", chapter_id="ch1", revision=1,
            status="accepted", text=text, char_count=len(text),
        )
    )


def test_audit_cites_both_paragraphs_for_explicit_fact_conflict(reg):
    _seed(reg, text="【道具:钥匙=在桌上】\n\n【道具:钥匙=在林舟手中】")
    audit = NovelContinuityAuditService(reg, project_id="p1")

    finding = audit.audit_project(1)[0]

    assert finding.rule == "explicit_fact_conflict"
    assert finding.evidence[0].paragraph_id == "r1:p2"
    assert finding.related_evidence[0].paragraph_id == "r1:p1"


def test_audit_disposition_preserves_author_decision_and_rejects_suppression(reg):
    _seed(reg, text="【道具:钥匙=在桌上】\n\n【道具:钥匙=在林舟手中】")
    audit = NovelContinuityAuditService(reg, project_id="p1")
    finding = audit.audit_project(1)[0]

    kept = audit.set_disposition(
        finding,
        FindingDisposition(
            finding_id=finding.finding_id, fingerprint=finding.fingerprint,
            status=FindingDispositionStatus.KEEP_AS_IS, rationale="双钥匙",
        ),
    )

    assert audit.list_dispositions() == (kept,)
    with pytest.raises(ValueError, match="cannot be marked"):
        audit.set_disposition(
            finding,
            kept.model_copy(update={"status": FindingDispositionStatus.FALSE_POSITIVE}),
        )


def test_audit_detects_character_before_declared_first_appearance(reg):
    _seed(reg, text="林舟已经进门。")
    reg.novel_character_store.save(
        NovelCharacter(
            character_id="linzhou", project_id="p1", name="林舟", first_appearance=2
        )
    )

    findings = NovelContinuityAuditService(reg, project_id="p1").audit_project(1)

    assert findings[0].rule == "character_before_first_appearance"
    assert findings[0].evidence[0].paragraph_id == "r1:p1"
