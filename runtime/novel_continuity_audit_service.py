"""Evidence-backed, deterministic continuity checks for accepted chapters.

The service intentionally reports only facts it can point to.  It does not
attempt to infer canon from prose or treat an absent mention as a contradiction.
Authors can add explicit inline continuity markers while drafting, for example
``【道具:钥匙=在林舟手中】``.  They remain normal prose-adjacent annotations and
give the auditor a stable, cross-chapter fact key until richer extraction exists.
"""

from __future__ import annotations

import hashlib
import json
import re

from ..contracts.novel_revision import (
    AuditFinding,
    EvidenceRef,
    FindingDisposition,
    FindingDispositionStatus,
)
from .novel_chapter_revision_service import NovelChapterRevisionService


_FACT = re.compile(r"【(公开|私密|道具|时间|承诺|钩子)\s*[:：]\s*([^=＝:：]+?)\s*[=＝:：]\s*([^】]+)】")


class NovelContinuityAuditService:
    """Read-only accepted-prose audit plus persistent author dispositions."""

    def __init__(self, registry, *, project_id: str):
        self._registry = registry
        self._project_id = project_id
        self._chapters = NovelChapterRevisionService(registry, project_id=project_id)

    def audit_project(self, through_chapter: int) -> tuple[AuditFinding, ...]:
        if through_chapter < 1:
            raise ValueError("through_chapter must be positive")
        findings: list[AuditFinding] = []
        known_facts: dict[str, tuple[str, EvidenceRef]] = {}
        characters = self._registry.novel_character_store.list_by_project(self._project_id)
        for plan in self._registry.novel_chapter_plan_store.list_by_project(self._project_id):
            if plan.chapter_index > through_chapter:
                break
            try:
                chapter = self._chapters.read_chapter(plan.chapter_index)
            except ValueError:
                continue
            for paragraph in chapter.paragraphs:
                evidence = EvidenceRef(
                    chapter_index=chapter.chapter_index,
                    revision=chapter.accepted_revision,
                    paragraph_id=paragraph.paragraph_id,
                    excerpt=paragraph.text[:1_000],
                )
                for kind, subject, value in _FACT.findall(paragraph.text):
                    key = f"{kind}:{subject.strip()}"
                    normalized_value = value.strip()
                    previous = known_facts.get(key)
                    if previous is not None and previous[0] != normalized_value:
                        findings.append(self._finding(
                            rule="explicit_fact_conflict",
                            severity="error",
                            description=(
                                f"“{key}”在已接受正文中出现两个不同的显式状态："
                                f"“{previous[0]}”与“{normalized_value}”。"
                            ),
                            evidence=evidence,
                            related=previous[1],
                        ))
                    known_facts[key] = (normalized_value, evidence)
                for character in characters:
                    if (
                        character.name
                        and character.first_appearance > chapter.chapter_index
                        and character.name in paragraph.text
                    ):
                        findings.append(self._finding(
                            rule="character_before_first_appearance",
                            severity="error",
                            description=(
                                f"人物“{character.name}”在第 {chapter.chapter_index} 章出现，"
                                f"但人物资料的首次出场章为第 {character.first_appearance} 章。"
                            ),
                            evidence=evidence,
                        ))
        return tuple(findings)

    def list_dispositions(self) -> tuple[FindingDisposition, ...]:
        rows = self._registry.db.connect().execute(
            """SELECT disposition_json FROM novel_revision_audit_dispositions
               WHERE project_id = ? ORDER BY created_at DESC""",
            (self._project_id,),
        ).fetchall()
        return tuple(
            FindingDisposition.model_validate(json.loads(row["disposition_json"]))
            for row in rows
        )

    def set_disposition(
        self, finding: AuditFinding, disposition: FindingDisposition
    ) -> FindingDisposition:
        if finding.finding_id != disposition.finding_id or finding.fingerprint != disposition.fingerprint:
            raise ValueError("disposition must target the exact audit finding")
        if (
            disposition.status == FindingDispositionStatus.FALSE_POSITIVE
            and finding.rule in {"explicit_fact_conflict", "character_before_first_appearance"}
        ):
            raise ValueError("factual continuity findings cannot be marked false_positive")
        conn = self._registry.db.connect()
        conn.execute(
            """INSERT OR REPLACE INTO novel_revision_audit_dispositions
               (finding_id, fingerprint, project_id, disposition_json)
               VALUES (?, ?, ?, ?)""",
            (
                disposition.finding_id,
                disposition.fingerprint,
                self._project_id,
                json.dumps(disposition.model_dump(mode="json"), ensure_ascii=False),
            ),
        )
        conn.commit()
        return disposition

    @staticmethod
    def _finding(
        *, rule: str, severity: str, description: str, evidence: EvidenceRef,
        related: EvidenceRef | None = None,
    ) -> AuditFinding:
        references = (evidence,) if related is None else (evidence, related)
        fingerprint = hashlib.sha256(
            f"{rule}|".encode("utf-8")
            + "|".join(
                f"{item.chapter_index}:{item.revision}:{item.paragraph_id}"
                for item in references
            ).encode("utf-8")
        ).hexdigest()
        return AuditFinding(
            finding_id=f"audit-{fingerprint[:16]}",
            fingerprint=fingerprint,
            rule=rule,
            severity=severity,
            description=description,
            evidence=(evidence,),
            related_evidence=() if related is None else (related,),
        )


__all__ = ["NovelContinuityAuditService"]
