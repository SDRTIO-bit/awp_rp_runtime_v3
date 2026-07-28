from __future__ import annotations

import pytest
from pydantic import ValidationError

from awp_rp_runtime_v3.contracts.novel_project_skill import ProjectSkillVersion


def test_project_skill_rejects_mismatched_frontmatter_name():
    with pytest.raises(ValidationError, match="frontmatter"):
        ProjectSkillVersion(
            skill_id="voice-check",
            version=1,
            content="---\nname: other\ndescription: 检查口吻\n---\n正文",
        )


def test_project_skill_accepts_matching_small_markdown():
    skill = ProjectSkillVersion(
        skill_id="voice-check",
        version=1,
        content="---\nname: voice-check\ndescription: 检查角色口吻\n---\n只报告证据。",
    )

    assert skill.skill_id == "voice-check"
