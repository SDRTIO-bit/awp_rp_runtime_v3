"""AWPV2ContinuityRanker — ComfyUI node for ranking ContinuityResult."""

from __future__ import annotations
from typing import Any

from ..contracts.continuity_result import ContinuityResult
from ..runtime.continuity_ranker import ContinuityRanker


class AWPV2ContinuityRanker:
    """Rank continuity issues by priority."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "continuity_result": ("CONTINUITY_RESULT", {}),
            },
        }

    RETURN_TYPES = ("CONTINUITY_RESULT",)
    RETURN_NAMES = ("ranked_result",)
    FUNCTION = "rank"
    CATEGORY = "AWP V2/Continuity"

    def rank(self, continuity_result: ContinuityResult) -> tuple:
        ranker = ContinuityRanker()
        accepted, rejected = ranker.rank(continuity_result.issues)

        # Update the result with ranked issues
        from ..contracts.continuity_issue import ContinuitySeverity
        blocking = [i for i in accepted if i.severity == ContinuitySeverity.BLOCKING]
        warnings = [i for i in accepted if i.severity == ContinuitySeverity.WARNING]
        info = [i for i in accepted if i.severity == ContinuitySeverity.INFO]

        ranked_result = ContinuityResult(
            result_id=continuity_result.result_id,
            trace_id=continuity_result.trace_id,
            snapshot_id=continuity_result.snapshot_id,
            task_run_id=continuity_result.task_run_id,
            status=continuity_result.status,
            issues=accepted,
            blocking_issues=blocking,
            warnings=warnings,
            informational_notes=info,
            conflicts=continuity_result.conflicts,
            writer_constraints=continuity_result.writer_constraints,
            director_recommendations=continuity_result.director_recommendations,
            degraded_reasons=continuity_result.degraded_reasons,
            created_at=continuity_result.created_at,
        )
        return (ranked_result,)
