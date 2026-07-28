from __future__ import annotations

import pytest
from pydantic import ValidationError

from awp_rp_runtime_v3.contracts.novel_revision import RevisionPatch


def test_patch_requires_revision_local_anchor_and_reason():
    with pytest.raises(ValidationError):
        RevisionPatch(
            patch_id="patch-one",
            chapter_index=2,
            base_revision=3,
            paragraph_id="p2",
            expected_paragraph_hash="a" * 64,
            operation="replace",
            replacement_text="新文本",
            reason="",
        )


def test_patch_accepts_exact_anchored_replacement():
    patch = RevisionPatch(
        patch_id="patch-one",
        chapter_index=2,
        base_revision=3,
        paragraph_id="r3:p2",
        expected_paragraph_hash="a" * 64,
        operation="replace",
        replacement_text="新文本",
        reason="删去解释，保留人物回避。",
    )

    assert patch.paragraph_id == "r3:p2"
