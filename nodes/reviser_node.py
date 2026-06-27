"""AWPV2Reviser — ComfyUI node for revision.

Only runs when QualityPipeline returns 'revise'.
"""

from __future__ import annotations


class AWPV2Reviser:
    """AWP V2 修订节点"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "writer_draft": ("WRITER_DRAFT",),
                "quality_decision": ("QUALITY_DECISION",),
                "writer_input_bundle": ("WRITER_INPUT_BUNDLE",),
            },
            "optional": {
                "max_revisions": ("INT", {"default": 1, "min": 1, "max": 2}),
            },
        }

    RETURN_TYPES = ("WRITER_DRAFT", "REVISION_RESULT")
    RETURN_NAMES = ("revised_draft", "revision_result")
    FUNCTION = "execute"
    CATEGORY = "AWP V2 / Writer"

    def execute(self, writer_draft: dict, quality_decision: dict, writer_input_bundle: dict,
                max_revisions: int = 1):
        from ..runtime.reviser_runtime import ReviserRuntime
        from ..runtime.writer_v2_runtime import FakeWriterV2Adapter
        from ..contracts.writer_draft import WriterDraft
        from ..contracts.quality_decision import QualityDecision
        from ..contracts.revision_request import RevisionRequest
        from ..contracts.quality_issue import QualityIssue

        draft = WriterDraft.from_dict(writer_draft)
        decision = QualityDecision.from_dict(quality_decision)
        bundle_dict = writer_input_bundle

        # Build revision request from quality issues
        issues = []
        for check in decision.checks:
            if not check.get("passed", True):
                issues.append(QualityIssue(
                    gate_name=check.get("name", ""),
                    description=check.get("details", ""),
                ))

        request = RevisionRequest(
            request_id=f"rr_{draft.draft_id}",
            trace_id=draft.trace_id,
            snapshot_id=draft.snapshot_id,
            writer_draft_id=draft.draft_id,
            current_revision=draft.revision_number,
            max_revisions=max_revisions,
            issues=issues,
            original_text=draft.text,
        )

        adapter = FakeWriterV2Adapter()
        reviser = ReviserRuntime(adapter, max_revisions=max_revisions)

        from ..contracts.writer_input_bundle import WriterInputBundle
        bundle = WriterInputBundle.from_dict(bundle_dict)
        result = reviser.revise(request, bundle)

        # Create revised draft
        revised_draft = WriterDraft(
            draft_id=f"wd_rev_{draft.draft_id}",
            trace_id=draft.trace_id,
            snapshot_id=draft.snapshot_id,
            writer_input_bundle_id=draft.writer_input_bundle_id,
            text=result.revised_text,
            character_count=len(result.revised_text),
            revision_number=result.revision_number,
        )

        return (revised_draft.to_dict(), result.to_dict())
