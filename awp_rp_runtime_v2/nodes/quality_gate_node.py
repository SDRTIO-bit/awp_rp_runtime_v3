"""AWPV2QualityGate — quality gate with three-state verdict.

Input: candidate_text, round_snapshot, trace_id
Output: QUALITY_DECISION (JSON with verdict: accept|revise|reject)
"""

from __future__ import annotations

from typing import Any


class AWPV2QualityGate:

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "candidate_text": ("STRING",),
                "round_snapshot": ("ROUND_SNAPSHOT",),
            },
            "optional": {
                "trace_id": ("STRING", {"default": ""}),
                "retry_count": ("INT", {"default": 0}),
                "max_retries": ("INT", {"default": 3}),
                "auto_accept": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = ("QUALITY_DECISION",)
    RETURN_NAMES = ("quality_decision",)
    FUNCTION = "execute"
    CATEGORY = "AWP/RP_V2"

    def execute(
        self,
        candidate_text: str,
        round_snapshot: dict[str, Any],
        trace_id: str = "",
        retry_count: int = 0,
        max_retries: int = 3,
        auto_accept: bool = False,
    ) -> tuple[dict[str, Any]]:
        from ..contracts.quality_decision import QualityDecision, QualityVerdict
        from ..contracts.round_snapshot import RoundSnapshot

        snapshot = RoundSnapshot.from_dict(round_snapshot)
        effective_trace_id = trace_id or snapshot.trace_id

        # Deterministic checks
        blocking_reasons = []
        warnings = []
        checks = []

        # Length check
        min_len = 50
        passed = len(candidate_text) >= min_len
        checks.append({"name": "min_length", "passed": passed,
                        "details": f"len={len(candidate_text)}, min={min_len}"})
        if not passed:
            blocking_reasons.append(f"Text too short: {len(candidate_text)} < {min_len}")

        # No JSON check
        has_json = "{" in candidate_text and "}" in candidate_text and ":" in candidate_text
        checks.append({"name": "no_json", "passed": not has_json})
        if has_json:
            blocking_reasons.append("Contains JSON-like content")

        # No debug markers
        debug_markers = ["DEBUG", "TODO", "FIXME", "```"]
        has_debug = any(m in candidate_text for m in debug_markers)
        checks.append({"name": "no_debug", "passed": not has_debug})
        if has_debug:
            warnings.append("Contains debug markers")

        if auto_accept and not blocking_reasons:
            verdict = QualityVerdict.ACCEPTED
        elif blocking_reasons:
            verdict = QualityVerdict.REVISE if retry_count < max_retries else QualityVerdict.REJECTED
        else:
            verdict = QualityVerdict.ACCEPTED

        decision = QualityDecision(
            trace_id=effective_trace_id,
            source_turn_id=snapshot.snapshot_id,
            verdict=verdict,
            candidate_text=candidate_text,
            blocking_reasons=blocking_reasons,
            warnings=warnings,
            checks=checks,
            overall_score=0.9 if verdict == QualityVerdict.ACCEPTED else 0.3,
            retry_allowed=verdict == QualityVerdict.REVISE,
            retry_count=retry_count,
            max_retries=max_retries,
        )

        return (decision.to_dict(),)
