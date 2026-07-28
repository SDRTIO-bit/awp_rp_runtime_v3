"""Author-controlled project skill persistence and materialization."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from ..contracts.novel_project_skill import (
    ProjectSkillProposal,
    ProjectSkillStatus,
    ProjectSkillVersion,
)


class NovelProjectSkillService:
    """Keeps project skills versioned and makes only enabled versions loadable."""

    MAX_ENABLED = 20

    def __init__(self, registry, *, project_id: str, project_root: str | Path):
        self._registry = registry
        self._project_id = project_id
        self._root = Path(project_root).resolve()

    def save_author_version(
        self, skill: ProjectSkillVersion, *, source: str = "author"
    ) -> ProjectSkillVersion:
        stored = skill.model_copy(update={
            "status": ProjectSkillStatus.SAVED, "source": source
        })
        conn = self._registry.db.connect()
        conn.execute(
            """INSERT OR REPLACE INTO novel_project_skill_versions
               (project_id, skill_id, version, skill_json)
               VALUES (?, ?, ?, ?)""",
            (
                self._project_id,
                stored.skill_id,
                stored.version,
                json.dumps(stored.model_dump(mode="json"), ensure_ascii=False),
            ),
        )
        conn.commit()
        return stored

    def list_versions(self, skill_id: str) -> list[ProjectSkillVersion]:
        rows = self._registry.db.connect().execute(
            """SELECT skill_json FROM novel_project_skill_versions
               WHERE project_id = ? AND skill_id = ? ORDER BY version DESC""",
            (self._project_id, skill_id),
        ).fetchall()
        return [
            ProjectSkillVersion.model_validate(json.loads(row["skill_json"]))
            for row in rows
        ]

    def save_editor_proposal(
        self, proposal: ProjectSkillProposal
    ) -> ProjectSkillProposal:
        if proposal.project_id != self._project_id:
            raise ValueError("project skill proposal does not belong to this project")
        pending = proposal.model_copy(update={
            "status": ProjectSkillStatus.PROPOSED,
            "approval_turn": 0,
            "skill": proposal.skill.model_copy(update={
                "status": ProjectSkillStatus.PROPOSED, "source": "editor"
            }),
        })
        conn = self._registry.db.connect()
        conn.execute(
            """INSERT OR REPLACE INTO novel_project_skill_proposals
               (proposal_id, project_id, status, proposal_json, updated_at)
               VALUES (?, ?, ?, ?, datetime('now'))""",
            (
                pending.proposal_id, self._project_id, pending.status.value,
                json.dumps(pending.model_dump(mode="json"), ensure_ascii=False),
            ),
        )
        conn.commit()
        return pending

    def get_proposal(self, proposal_id: str) -> ProjectSkillProposal:
        row = self._registry.db.connect().execute(
            """SELECT proposal_json FROM novel_project_skill_proposals
               WHERE proposal_id = ? AND project_id = ?""",
            (proposal_id, self._project_id),
        ).fetchone()
        if row is None:
            raise FileNotFoundError("project skill proposal not found")
        return ProjectSkillProposal.model_validate(json.loads(row["proposal_json"]))

    def approve_proposal(
        self, proposal_id: str, *, author_turn: int
    ) -> ProjectSkillVersion:
        proposal = self.get_proposal(proposal_id)
        if proposal.status != ProjectSkillStatus.PROPOSED:
            raise ValueError("project skill proposal is not pending confirmation")
        if author_turn <= proposal.proposal_turn:
            raise ValueError("project skill proposal approval requires a later author turn")
        row = self._registry.db.connect().execute(
            """SELECT COALESCE(MAX(version), 0) AS latest
               FROM novel_project_skill_versions WHERE project_id = ? AND skill_id = ?""",
            (self._project_id, proposal.skill.skill_id),
        ).fetchone()
        saved = self.save_author_version(
            proposal.skill.model_copy(update={"version": int(row["latest"]) + 1}),
            source="editor_proposal_approved",
        )
        approved = proposal.model_copy(update={
            "status": ProjectSkillStatus.SAVED, "approval_turn": author_turn,
        })
        conn = self._registry.db.connect()
        conn.execute(
            """UPDATE novel_project_skill_proposals
               SET status = ?, proposal_json = ?, updated_at = datetime('now')
               WHERE proposal_id = ?""",
            (
                approved.status.value,
                json.dumps(approved.model_dump(mode="json"), ensure_ascii=False),
                proposal_id,
            ),
        )
        conn.commit()
        return saved

    def activate_version(self, skill_id: str, version: int) -> ProjectSkillVersion:
        skill = self._load_version(skill_id, version)
        conn = self._registry.db.connect()
        active_count = conn.execute(
            "SELECT COUNT(*) AS count FROM novel_project_skill_registry "
            "WHERE project_id = ? AND status = 'enabled' AND skill_id != ?",
            (self._project_id, skill_id),
        ).fetchone()["count"]
        if active_count >= self.MAX_ENABLED:
            raise ValueError("at most 20 project skills may be enabled")
        enabled = skill.model_copy(update={"status": ProjectSkillStatus.ENABLED})
        conn.execute(
            """INSERT OR REPLACE INTO novel_project_skill_registry
               (project_id, skill_id, version, status, updated_at)
               VALUES (?, ?, ?, 'enabled', datetime('now'))""",
            (self._project_id, skill_id, version),
        )
        conn.commit()
        self._write_enabled_skill(enabled)
        self._write_enabled_manifest()
        return enabled

    def deactivate_skill(self, skill_id: str) -> None:
        conn = self._registry.db.connect()
        cursor = conn.execute(
            """UPDATE novel_project_skill_registry SET status = 'disabled',
               updated_at = datetime('now') WHERE project_id = ? AND skill_id = ?""",
            (self._project_id, skill_id),
        )
        if cursor.rowcount == 0:
            raise FileNotFoundError("enabled project skill not found")
        conn.commit()
        self._write_enabled_manifest()

    def list_enabled(self) -> list[ProjectSkillVersion]:
        conn = self._registry.db.connect()
        rows = conn.execute(
            """SELECT versions.skill_json FROM novel_project_skill_registry AS registry
               JOIN novel_project_skill_versions AS versions
                 ON versions.project_id = registry.project_id
                AND versions.skill_id = registry.skill_id
                AND versions.version = registry.version
               WHERE registry.project_id = ? AND registry.status = 'enabled'
               ORDER BY registry.skill_id""",
            (self._project_id,),
        ).fetchall()
        return [
            ProjectSkillVersion.model_validate(
                {**json.loads(row["skill_json"]), "status": ProjectSkillStatus.ENABLED.value}
            )
            for row in rows
        ]

    def list_all_versions(self) -> list[ProjectSkillVersion]:
        rows = self._registry.db.connect().execute(
            """SELECT skill_json FROM novel_project_skill_versions
               WHERE project_id = ? ORDER BY skill_id, version DESC""",
            (self._project_id,),
        ).fetchall()
        return [
            ProjectSkillVersion.model_validate(json.loads(row["skill_json"]))
            for row in rows
        ]

    def list_proposals(self) -> list[ProjectSkillProposal]:
        rows = self._registry.db.connect().execute(
            """SELECT proposal_json FROM novel_project_skill_proposals
               WHERE project_id = ? ORDER BY created_at DESC""",
            (self._project_id,),
        ).fetchall()
        return [
            ProjectSkillProposal.model_validate(json.loads(row["proposal_json"]))
            for row in rows
        ]

    def _load_version(self, skill_id: str, version: int) -> ProjectSkillVersion:
        row = self._registry.db.connect().execute(
            """SELECT skill_json FROM novel_project_skill_versions
               WHERE project_id = ? AND skill_id = ? AND version = ?""",
            (self._project_id, skill_id, version),
        ).fetchone()
        if row is None:
            raise FileNotFoundError("project skill version not found")
        return ProjectSkillVersion.model_validate(json.loads(row["skill_json"]))

    def _write_enabled_skill(self, skill: ProjectSkillVersion) -> None:
        path = self._root / "agent" / "skills" / skill.skill_id / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=".SKILL.", suffix=".tmp", dir=str(path.parent)
        )
        temporary_path = Path(temporary)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(skill.content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def _write_enabled_manifest(self) -> None:
        path = self._root / ".awp" / "enabled-project-skills.json"
        payload = {
            "project_id": self._project_id,
            "skills": [
                {"skill_id": skill.skill_id, "version": skill.version}
                for skill in self.list_enabled()
            ],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            prefix=".enabled-project-skills.", suffix=".tmp", dir=str(path.parent)
        )
        temporary_path = Path(temporary)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()


__all__ = ["NovelProjectSkillService"]
