from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan


def test_chapter_plan_accepts_llm_character_range_for_target_chars() -> None:
    plan = ChapterPlan.from_dict({"target_chars": "2200-2500"})

    assert plan.target_chars == 2350
