from awp_rp_runtime_v3.contracts.novel_chapter import ChapterPlan
from awp_rp_runtime_v3.contracts.novel_draft import ChapterDraft


def test_chapter_plan_accepts_llm_character_range_for_target_chars() -> None:
    plan = ChapterPlan.from_dict({"target_chars": "2200-2500"})

    assert plan.target_chars == 2350


def test_chapter_draft_persists_quality_annotations() -> None:
    draft = ChapterDraft(
        draft_id="draft-1",
        quality_annotations=({"description": "末尾可能被截断", "severity": "error"},),
    )

    restored = ChapterDraft.from_dict(draft.to_dict())

    assert restored.quality_annotations == draft.quality_annotations


def test_chapter_draft_persists_raw_writer_text() -> None:
    draft = ChapterDraft(text="校对后正文", raw_text="Writer 原始正文")

    restored = ChapterDraft.from_dict(draft.to_dict())

    assert restored.raw_text == "Writer 原始正文"
