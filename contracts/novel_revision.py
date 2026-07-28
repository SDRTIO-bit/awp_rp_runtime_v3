"""Strict contracts for controlled revisions of accepted novel chapters."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RevisionPatchOperation(str, Enum):
    REPLACE = "replace"
    DELETE = "delete"
    INSERT_BEFORE = "insert_before"
    INSERT_AFTER = "insert_after"


class RevisionBatchStatus(str, Enum):
    DRAFT = "draft"
    PENDING_CONFIRMATION = "pending_confirmation"
    APPROVED = "approved"
    APPLIED = "applied"
    REBUILD_FAILED = "rebuild_failed"
    SUPERSEDED = "superseded"


class FindingDispositionStatus(str, Enum):
    ACCEPT_REVISION = "accept_revision"
    KEEP_AS_IS = "keep_as_is"
    DEFER = "defer"
    FALSE_POSITIVE = "false_positive"


class ChapterParagraph(_StrictModel):
    paragraph_id: str = Field(pattern=r"r[1-9][0-9]*:p[1-9][0-9]*")
    ordinal: int = Field(ge=1)
    text: str
    sha256: str = Field(pattern=r"[0-9a-f]{64}")


class ChapterRead(_StrictModel):
    chapter_index: int = Field(ge=1)
    title: str = ""
    draft_id: str = Field(min_length=1)
    accepted_revision: int = Field(ge=1)
    text_sha256: str = Field(pattern=r"[0-9a-f]{64}")
    paragraphs: tuple[ChapterParagraph, ...]


class RevisionPatch(_StrictModel):
    patch_id: str = Field(pattern=r"patch-[a-z0-9-]{1,64}")
    chapter_index: int = Field(ge=1)
    base_revision: int = Field(ge=1)
    paragraph_id: str = Field(pattern=r"r[1-9][0-9]*:p[1-9][0-9]*")
    expected_paragraph_hash: str = Field(pattern=r"[0-9a-f]{64}")
    operation: RevisionPatchOperation
    replacement_text: str = Field(max_length=100_000)
    reason: str = Field(min_length=1, max_length=2_000)
    narrative_impact: str = Field(default="", max_length=2_000)
    downstream_impact: str = Field(default="", max_length=2_000)


class ChapterRevisionPlan(_StrictModel):
    plan_id: str = Field(pattern=r"revision-[a-z0-9-]{1,64}")
    project_id: str = Field(min_length=1)
    chapter_index: int = Field(ge=1)
    base_revision: int = Field(ge=1)
    status: RevisionBatchStatus = RevisionBatchStatus.DRAFT
    patches: tuple[RevisionPatch, ...] = Field(min_length=1, max_length=100)
    proposal_turn: int = Field(default=0, ge=0)
    approval_turn: int = Field(default=0, ge=0)
    reason: str = Field(default="", max_length=2_000)


class RevisionImpact(_StrictModel):
    stale_chapters: tuple[int, ...] = ()
    changed_facts: tuple[str, ...] = ()
    rebuild_status: str = "pending"
    rebuild_message: str = ""


class EvidenceRef(_StrictModel):
    chapter_index: int = Field(ge=1)
    revision: int = Field(ge=1)
    paragraph_id: str = Field(pattern=r"r[1-9][0-9]*:p[1-9][0-9]*")
    excerpt: str = Field(min_length=1, max_length=1_000)


class AuditFinding(_StrictModel):
    finding_id: str = Field(min_length=1)
    fingerprint: str = Field(pattern=r"[0-9a-f]{64}")
    rule: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence: tuple[EvidenceRef, ...] = Field(min_length=1)
    related_evidence: tuple[EvidenceRef, ...] = ()


class FindingDisposition(_StrictModel):
    finding_id: str = Field(min_length=1)
    fingerprint: str = Field(pattern=r"[0-9a-f]{64}")
    status: FindingDispositionStatus
    rationale: str = Field(default="", max_length=2_000)
    scope: str = Field(default="paragraph", pattern=r"(paragraph|chapter|character|project)")


__all__ = [
    "AuditFinding",
    "ChapterParagraph",
    "ChapterRead",
    "ChapterRevisionPlan",
    "EvidenceRef",
    "FindingDisposition",
    "FindingDispositionStatus",
    "RevisionBatchStatus",
    "RevisionImpact",
    "RevisionPatch",
    "RevisionPatchOperation",
]
