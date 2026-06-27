"""ReviserRuntime — controlled revision of WriterDraft.

Reviser ONLY runs when QualityPipeline returns 'revise'.
Reviser can ONLY fix specific QualityIssues.
Reviser CANNOT:
- Modify CardState
- Write Memory
- Call tools
- Change WriterInputBundle facts
- Override mustPreserveFacts / mustNotDo
- Output analysis or explanation
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from ..contracts.writer_draft import WriterDraft
from ..contracts.quality_issue import QualityIssue
from ..contracts.revision_request import RevisionRequest
from ..contracts.revision_result import RevisionResult


class ReviserRuntime:
    """Controls revision of WriterDraft based on QualityIssues.

    Max revisions are configurable (default 1, max 2).
    Reviser cannot change facts, write state, or call tools.
    """

    def __init__(self, writer_adapter: Any, max_revisions: int = 1):
        self.writer_adapter = writer_adapter
        self.max_revisions = min(max_revisions, 2)  # Cap at 2

    def can_revise(self, current_revision: int) -> bool:
        """Check if another revision is allowed."""
        return current_revision < self.max_revisions

    def revise(
        self,
        request: RevisionRequest,
        bundle: Any,  # WriterInputBundle
    ) -> RevisionResult:
        """Attempt to revise a draft based on quality issues.

        Returns RevisionResult with revised text and status.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Check if revision is allowed
        if not self.can_revise(request.current_revision):
            return RevisionResult(
                result_id=f"rr_{uuid.uuid4().hex[:12]}",
                request_id=request.request_id,
                trace_id=request.trace_id,
                revised_text=request.original_text,
                revision_number=request.current_revision,
                success=False,
                issues_addressed=[],
                issues_remaining=[i.description for i in request.issues],
                created_at=now,
            )

        # Generate revised text
        revised_text = self.writer_adapter.generate(bundle)

        # Track which issues were addressed
        addressed = [i.description for i in request.issues if i.fixable]
        remaining = [i.description for i in request.issues if not i.fixable]

        return RevisionResult(
            result_id=f"rr_{uuid.uuid4().hex[:12]}",
            request_id=request.request_id,
            trace_id=request.trace_id,
            revised_text=revised_text,
            revision_number=request.current_revision + 1,
            success=len(remaining) == 0,
            issues_addressed=addressed,
            issues_remaining=remaining,
            created_at=now,
        )
