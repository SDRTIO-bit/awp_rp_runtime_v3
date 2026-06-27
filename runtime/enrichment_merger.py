"""EnrichmentMerger — merges and validates tool results for Director.

Takes ToolResultBundle and produces EnrichmentBundle.
Validates sourceRefs, categorizes results, and prepares for Director consumption.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ..contracts.tool_result import ToolResult, ToolResultStatus
from ..contracts.tool_result_bundle import ToolResultBundle
from ..contracts.enrichment_bundle import EnrichmentBundle, EnrichmentItem
from .tool_result_validator import ToolResultValidator


class EnrichmentMerger:
    """Merges and validates tool results for Director consumption."""

    def __init__(self):
        self.validator = ToolResultValidator()

    def merge(self, bundle: ToolResultBundle) -> EnrichmentBundle:
        """Merge tool results into an EnrichmentBundle.

        Validates each result, categorizes as accepted/rejected/degraded.
        """
        now = datetime.now(timezone.utc).isoformat()
        accepted = []
        rejected = []
        degraded = []

        for result in bundle.results:
            is_valid, issues = self.validator.validate(result)

            if result.is_failed() or not is_valid:
                item = EnrichmentItem(
                    source_request_id=result.request_id,
                    tool_id=result.tool_id,
                    status=result.status,
                    summary=result.summary,
                    structured_data=result.structured_data,
                    evidence=result.evidence,
                    source_refs=result.source_refs,
                    accepted=False,
                    rejection_reason="; ".join(issues) if issues else result.failure_reason,
                )
                rejected.append(item)
            elif result.is_degraded():
                item = EnrichmentItem(
                    source_request_id=result.request_id,
                    tool_id=result.tool_id,
                    status=result.status,
                    summary=result.summary,
                    structured_data=result.structured_data,
                    evidence=result.evidence,
                    source_refs=result.source_refs,
                    accepted=True,
                )
                degraded.append(item)
            else:
                item = EnrichmentItem(
                    source_request_id=result.request_id,
                    tool_id=result.tool_id,
                    status=result.status,
                    summary=result.summary,
                    structured_data=result.structured_data,
                    evidence=result.evidence,
                    source_refs=result.source_refs,
                    accepted=True,
                )
                accepted.append(item)

        return EnrichmentBundle(
            bundle_id=f"eb_{uuid.uuid4().hex[:12]}",
            trace_id=bundle.trace_id,
            snapshot_id=bundle.snapshot_id,
            tool_result_bundle_id=bundle.bundle_id,
            accepted_items=accepted,
            rejected_items=rejected,
            degraded_items=degraded,
            total_tools_called=len(bundle.results),
            total_successful=len(accepted),
            total_failed=len(rejected),
            created_at=now,
        )
