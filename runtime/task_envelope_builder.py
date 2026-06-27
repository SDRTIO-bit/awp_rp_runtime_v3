"""TaskEnvelopeBuilder — builds AgentTaskEnvelope from DelegationTask + RoundSnapshot.

Crops snapshot data to only the fields allowed by inputFieldAllowlist.
"""

from __future__ import annotations

import uuid
from typing import Any

from ..contracts.delegation_plan import DelegationTask
from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.agent_task_envelope import AgentTaskEnvelope, TaskBudget
from ..runtime.agent_runtime_registry import AgentRuntimeRegistry


class TaskEnvelopeBuilder:
    """Builds a strict AgentTaskEnvelope from a task and snapshot."""

    def __init__(self, registry: AgentRuntimeRegistry):
        self.registry = registry

    def build(
        self,
        task: DelegationTask,
        snapshot: RoundSnapshot,
        brief_id: str = "",
    ) -> AgentTaskEnvelope | None:
        """Build envelope. Returns None if role is not registered."""
        spec = self.registry.get_spec(task.role)
        if not spec:
            return None

        # Crop snapshot data based on allowlist
        allowed_data = self._crop_snapshot(snapshot, task.input_field_allowlist)

        return AgentTaskEnvelope(
            task_run_id=f"run_{uuid.uuid4().hex[:12]}",
            trace_id=snapshot.trace_id,
            task_id=task.task_id,
            role=task.role,
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            snapshot_id=snapshot.snapshot_id,
            brief_id=brief_id,
            allowed_snapshot_data=allowed_data,
            player_input=snapshot.player_input,
            allowed_tools=task.tool_allowlist,
            budget=TaskBudget(
                max_tokens=task.max_tokens,
                timeout_ms=task.timeout_ms,
                max_tool_calls=len(task.tool_allowlist),
            ),
            expected_suggestion_kinds=task.expected_suggestion_kinds,
        )

    def _crop_snapshot(
        self, snapshot: RoundSnapshot, allowlist: list[str]
    ) -> dict[str, Any]:
        """Crop snapshot to only allowed fields."""
        full = snapshot.to_dict()
        if not allowlist:
            return {}

        cropped: dict[str, Any] = {}
        for field_name in allowlist:
            if field_name in full:
                cropped[field_name] = full[field_name]
        return cropped
