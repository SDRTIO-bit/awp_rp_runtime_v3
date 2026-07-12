"""Deterministic, conservative checks for Plan-to-draft adherence."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from ..contracts.novel_chapter import ChapterPlan


@dataclass
class PlanAdherenceResult:
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    coverage: float = 0.0


class NovelPlanAdherenceChecker:
    """Catch reliable structural misses without dictating prose wording."""

    _STOP_BIGRAMS = {
        "自己", "他的", "她的", "一个", "这本", "那本", "时候", "已经",
        "主动", "发现", "看见", "开始", "最后", "进行", "留下", "重新",
    }

    def check(
        self,
        *,
        plan: ChapterPlan,
        text: str,
        known_character_names: set[str],
    ) -> PlanAdherenceResult:
        result = PlanAdherenceResult()
        allowed = set(plan.character_appearance.appearance_order)
        if not allowed:
            # Legacy plans did not declare a cast; preserve compatibility and
            # enforce the allowlist only when the Plan Agent supplied one.
            allowed = set(known_character_names)
        unauthorized = sorted(
            name for name in known_character_names
            if name and name not in allowed and name in text
        )
        if unauthorized:
            result.blocking_reasons.append(
                "出现计划外已知角色: " + "、".join(unauthorized)
            )

        claims = [
            ("转折", plan.content_summary.turning_point, False),
            ("核心高潮", plan.content_summary.climax or plan.main_payoff, True),
            ("结尾", plan.content_summary.ending, False),
        ]
        checked = 0
        matched = 0
        for label, claim, blocking in claims:
            if not claim:
                continue
            checked += 1
            if self._claim_matches(claim, text, known_character_names):
                matched += 1
            elif blocking:
                result.blocking_reasons.append(f"未兑现Plan核心高潮: {claim}")
            else:
                result.warnings.append(f"可能未完整兑现Plan{label}: {claim}")
        result.coverage = matched / checked if checked else 1.0
        return result

    def _claim_matches(
        self, claim: str, text: str, known_character_names: set[str]
    ) -> bool:
        cleaned = claim
        for name in known_character_names:
            cleaned = cleaned.replace(name, "")
        chunks = re.findall(r"[\u4e00-\u9fff]{2,}", cleaned)
        bigrams: set[str] = set()
        fourgrams: set[str] = set()
        for chunk in chunks:
            for index in range(max(0, len(chunk) - 1)):
                term = chunk[index : index + 2]
                if term not in self._STOP_BIGRAMS:
                    bigrams.add(term)
            for index in range(max(0, len(chunk) - 3)):
                fourgrams.add(chunk[index : index + 4])
        if any(term in text for term in fourgrams):
            return True
        return sum(1 for term in bigrams if term in text) >= 2
