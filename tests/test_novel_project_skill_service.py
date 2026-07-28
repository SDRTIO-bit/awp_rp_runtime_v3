from __future__ import annotations

import pytest

from awp_rp_runtime_v3.contracts.novel_project_skill import (
    ProjectSkillProposal,
    ProjectSkillVersion,
)
from awp_rp_runtime_v3.runtime.novel_project_skill_service import (
    NovelProjectSkillService,
)
from awp_rp_runtime_v3.runtime.session_runtime_registry import (
    SessionRuntimeStoreRegistry,
)
from awp_rp_runtime_v3.storage.sqlite.database import Database


@pytest.fixture
def reg(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.initialize()
    return SessionRuntimeStoreRegistry(db)


def test_activate_skill_materializes_only_approved_version(reg, tmp_path):
    service = NovelProjectSkillService(reg, project_id="p1", project_root=tmp_path)
    saved = service.save_author_version(ProjectSkillVersion(
        skill_id="voice-check",
        version=1,
        content="---\nname: voice-check\ndescription: 检查角色口吻\n---\n只报告证据。",
    ))

    service.activate_version("voice-check", saved.version)

    path = tmp_path / "agent" / "skills" / "voice-check" / "SKILL.md"
    assert path.read_text(encoding="utf-8") == saved.content
    assert [skill.skill_id for skill in service.list_enabled()] == ["voice-check"]
    assert (tmp_path / ".awp" / "enabled-project-skills.json").is_file()


def test_editor_skill_proposal_needs_later_author_approval_then_activation(reg, tmp_path):
    service = NovelProjectSkillService(reg, project_id="p1", project_root=tmp_path)
    proposal = service.save_editor_proposal(ProjectSkillProposal(
        proposal_id="skill-proposal-voice-check", project_id="p1", proposal_turn=1,
        purpose="检查人物口吻", behavior_impact="只输出证据，不改写正文",
        skill=ProjectSkillVersion(
            skill_id="voice-check", version=1,
            content="---\nname: voice-check\ndescription: 检查角色口吻\n---\n只报告证据。",
        ),
    ))

    with pytest.raises(ValueError, match="later"):
        service.approve_proposal(proposal.proposal_id, author_turn=1)
    saved = service.approve_proposal(proposal.proposal_id, author_turn=2)

    assert saved.source == "editor_proposal_approved"
    assert service.list_enabled() == []
    service.activate_version(saved.skill_id, saved.version)
    service.deactivate_skill(saved.skill_id)
    assert service.list_enabled() == []
