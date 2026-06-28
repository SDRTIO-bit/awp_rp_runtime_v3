"""Real Director Adapter -- uses DeepSeek for Director planning.

Implements DirectorV2Adapter protocol with real provider calls.
On failure, produces structured ProviderFailure.
"""

from __future__ import annotations

import json
from typing import Any

from .deepseek_adapter import DeepSeekAdapter
from ...contracts.director_plan import DirectorPlan
from ...contracts.tool_plan import ToolPlan
from ...contracts.delegation_plan import DelegationPlan, DelegationTask
from ...contracts.round_snapshot import RoundSnapshot
from ...contracts.provider_request import ProviderAttemptReceipt


class RealDirectorV2Adapter:
    """Real Director adapter using DeepSeek.

    Generates DirectorPlan, ToolPlan, and DelegationPlan from RoundSnapshot.
    """

    def __init__(self, deepseek: DeepSeekAdapter):
        self._llm = deepseek

    def generate_plan(
        self,
        snapshot: RoundSnapshot,
        workflow_run_id: str = "",
        trace_id: str = "",
        turn_id: str = "",
        attempt_id: str = "",
    ) -> tuple[DirectorPlan, ProviderAttemptReceipt]:
        """Generate DirectorPlan from snapshot."""
        prompt = self._build_plan_prompt(snapshot)
        schema = {
            "type": "object",
            "required": ["turn_goal", "scene_focus"],
            "properties": {
                "turn_goal": {"type": "string"},
                "scene_focus": {"type": "string"},
                "must_preserve_facts": {"type": "array", "items": {"type": "string"}},
                "must_not_do": {"type": "array", "items": {"type": "string"}},
                "narrative_opportunities": {"type": "array", "items": {"type": "string"}},
                "writer_constraints": {"type": "array", "items": {"type": "string"}},
                "active_character_refs": {"type": "array", "items": {"type": "string"}},
            },
        }

        parsed, receipt = self._llm.generate_structured(
            prompt, schema,
            provider_role="director",
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            turn_id=turn_id,
            attempt_id=attempt_id,
        )

        if not receipt.success:
            return DirectorPlan(), receipt

        plan = DirectorPlan(
            turn_goal=parsed.get("turn_goal", ""),
            scene_focus=parsed.get("scene_focus", ""),
            must_preserve_facts=parsed.get("must_preserve_facts", []),
            must_not_do=parsed.get("must_not_do", []),
            narrative_opportunities=parsed.get("narrative_opportunities", []),
            writer_constraints=parsed.get("writer_constraints", []),
            active_character_refs=parsed.get("active_character_refs", []),
        )
        return plan, receipt

    def generate_tool_plan(
        self,
        snapshot: RoundSnapshot,
        plan: DirectorPlan,
        workflow_run_id: str = "",
        trace_id: str = "",
        turn_id: str = "",
        attempt_id: str = "",
    ) -> tuple[ToolPlan, ProviderAttemptReceipt]:
        """Generate ToolPlan (simplified for this phase)."""
        # For this phase, return an empty tool plan
        receipt = ProviderAttemptReceipt(
            provider_role="director",
            success=True,
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            turn_id=turn_id,
            attempt_id=attempt_id,
        )
        return ToolPlan(), receipt

    def generate_delegation_plan(
        self,
        snapshot: RoundSnapshot,
        plan: DirectorPlan,
        workflow_run_id: str = "",
        trace_id: str = "",
        turn_id: str = "",
        attempt_id: str = "",
    ) -> tuple[DelegationPlan, ProviderAttemptReceipt]:
        """Generate DelegationPlan (simplified for this phase)."""
        receipt = ProviderAttemptReceipt(
            provider_role="director",
            success=True,
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            turn_id=turn_id,
            attempt_id=attempt_id,
        )
        return DelegationPlan(tasks=[]), receipt

    def _build_plan_prompt(self, snapshot: RoundSnapshot) -> str:
        """Build prompt for Director plan generation.

        Contains only safe summary data, never full card text.
        """
        player_input = snapshot.player_input[:500]  # Truncate
        scene_location = ""
        if hasattr(snapshot.card_state, 'scene_state'):
            scene_location = getattr(snapshot.card_state.scene_state, 'location', '')

        recent_turn_count = len(snapshot.recent_turn_records)

        return (
            f"You are a narrative director for a roleplay session.\n\n"
            f"Current scene: {scene_location}\n"
            f"Player input: {player_input}\n"
            f"Recent turns: {recent_turn_count}\n"
            f"Active worldbook entries: {len(snapshot.active_worldbook_entries)}\n"
            f"Active memories: {len(snapshot.active_memories)}\n\n"
            f"Please generate a plan for the next turn. "
            f"Respond with JSON containing: turn_goal, scene_focus, "
            f"must_preserve_facts, must_not_do, narrative_opportunities, "
            f"writer_constraints, active_character_refs."
        )
