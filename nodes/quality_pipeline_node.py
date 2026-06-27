"""AWPV2QualityPipeline — ComfyUI node for quality checking.

Runs all quality gates and returns aggregate QualityDecision.
"""

from __future__ import annotations


class AWPV2QualityPipeline:
    """AWP V2 质量检查流水线节点"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "writer_draft": ("WRITER_DRAFT",),
                "round_snapshot": ("ROUND_SNAPSHOT",),
            },
        }

    RETURN_TYPES = ("QUALITY_DECISION", "QUALITY_GATE_RESULT_LIST")
    RETURN_NAMES = ("quality_decision", "gate_results")
    FUNCTION = "execute"
    CATEGORY = "AWP V2 / Quality"

    def execute(self, writer_draft: dict, round_snapshot: dict):
        from ..runtime.quality_pipeline_runtime import QualityPipelineRuntime
        from ..contracts.writer_draft import WriterDraft
        from ..contracts.round_snapshot import RoundSnapshot

        draft = WriterDraft.from_dict(writer_draft)
        snapshot = RoundSnapshot.from_dict(round_snapshot)

        pipeline = QualityPipelineRuntime()
        decision = pipeline.check(draft, snapshot)

        return (decision.to_dict(), decision.checks)
