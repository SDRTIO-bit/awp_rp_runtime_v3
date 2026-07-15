"""Pi-backed private NPC agenda proposal adapter."""

from __future__ import annotations

import json
import uuid

from ..contracts.novel_npc_agenda import NpcAgenda
from ..contracts.novel_pi_role_protocol import NovelPiRoleTask
from .novel_role_context import get_novel_role_context
from .novel_role_runtime import get_novel_role_runtime


class NovelNpcAgendaAdapter:
    def propose(self, project_id, chapter_plan, candidates, active_agendas, profile_context):
        context = get_novel_role_context()
        payload = {
            "chapter_plan": chapter_plan.to_dict(),
            "candidates": [c.to_dict() for c in candidates],
            "active_agendas": [a.model_dump(mode="json") for a in active_agendas],
            "profile": profile_context,
        }
        result = get_novel_role_runtime().run(NovelPiRoleTask(
            role="npc_planner", project_id=project_id, chapter_index=chapter_plan.chapter_index,
            revision=context.revision, phase="npc_agenda", session_key=f"task:{uuid.uuid4().hex}",
            task_contract="Return only {\"agendas\":[...]}; each agenda must satisfy the supplied schema.",
            input_payload={"prompt": json.dumps(payload, ensure_ascii=False), "response_format": "npc_agenda_json"},
        ), context=context)
        try:
            data = json.loads(result.text)
        except json.JSONDecodeError:
            return ()
        agendas = []
        for item in data.get("agendas", []):
            try:
                agendas.append(NpcAgenda.model_validate(item))
            except ValueError:
                continue
        return tuple(agendas[:5])
