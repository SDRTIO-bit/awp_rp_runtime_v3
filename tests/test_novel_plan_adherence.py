from __future__ import annotations

from awp_rp_runtime_v3.contracts.novel_chapter import (
    ChapterPlan,
    CharacterAppearance,
    ContentSummary,
)
from awp_rp_runtime_v3.runtime.novel_plan_adherence import NovelPlanAdherenceChecker
from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine
from awp_rp_runtime_v3.contracts.quality_decision import QualityDecision, QualityVerdict


def _plan() -> ChapterPlan:
    return ChapterPlan(
        chapter_index=1,
        title="扣子错位的新学期",
        main_payoff="陈默用好书换走破损教材，让沈溪重新认识他。",
        content_summary=ContentSummary(
            turning_point="班主任让陈默协助沈溪分发教材。",
            climax="陈默用自己的好书换走破损教材。",
            ending="沈溪在陈默名字旁留下问号。",
        ),
        character_appearance=CharacterAppearance(
            appearance_order=("陈默", "沈溪", "王磊"),
        ),
    )


def test_missing_central_payoff_is_blocking() -> None:
    result = NovelPlanAdherenceChecker().check(
        plan=_plan(),
        text="陈默迟到后讲了几个笑话，随后趴在桌上睡觉。",
        known_character_names={"陈默", "沈溪", "王磊", "赵小麦"},
    )

    assert any("核心高潮" in reason for reason in result.blocking_reasons)


def test_unauthorized_known_character_is_blocking() -> None:
    result = NovelPlanAdherenceChecker().check(
        plan=_plan(),
        text="陈默换走了那本破损教材。赵小麦忽然拿着秒表走进教室。",
        known_character_names={"陈默", "沈溪", "王磊", "赵小麦"},
    )

    assert any("赵小麦" in reason for reason in result.blocking_reasons)


def test_planned_payoff_and_cast_pass() -> None:
    result = NovelPlanAdherenceChecker().check(
        plan=_plan(),
        text=(
            "班主任让陈默帮沈溪分发教材。陈默看见一本书封面破损，"
            "便拿自己的新书换走了它。沈溪最后在他的名字旁画了一个问号。"
        ),
        known_character_names={"陈默", "沈溪", "王磊", "赵小麦"},
    )

    assert result.blocking_reasons == []
    assert result.coverage >= 0.6


def test_engine_merges_adherence_failure_into_quality_decision() -> None:
    decision = QualityDecision(verdict=QualityVerdict.ACCEPTED)

    NovelEngine._merge_plan_adherence(
        decision=decision,
        plan=_plan(),
        text="陈默迟到后讲了几个笑话。",
        known_character_names={"陈默", "沈溪", "王磊", "赵小麦"},
    )

    assert decision.verdict == QualityVerdict.REVISE
    assert any("核心高潮" in reason for reason in decision.blocking_reasons)
