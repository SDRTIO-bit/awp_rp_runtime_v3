"""DirectorRuntime — runs the Director agent.

Director reads RoundSnapshot and produces TurnBrief + DelegationPlan.
Director does NOT produce player-visible text, write state, or write memory.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.turn_brief import TurnBrief
from ..contracts.delegation_plan import DelegationPlan


class DirectorAdapter(Protocol):
    """Protocol for Director adapters (fake or real LLM)."""
    def generate(
        self, snapshot: RoundSnapshot
    ) -> tuple[TurnBrief, DelegationPlan]:
        ...


class DirectorRuntime:
    """Runtime for the Director agent."""

    def __init__(self, adapter: DirectorAdapter):
        self.adapter = adapter

    def run(self, snapshot: RoundSnapshot) -> tuple[TurnBrief, DelegationPlan]:
        """Run Director on the snapshot."""
        brief, plan = self.adapter.generate(snapshot)

        # Ensure identity fields
        now = datetime.now(timezone.utc).isoformat()
        brief.brief_id = brief.brief_id or f"brief_{uuid.uuid4().hex[:12]}"
        brief.trace_id = snapshot.trace_id
        brief.snapshot_id = snapshot.snapshot_id
        brief.card_id = snapshot.card_id
        brief.session_id = snapshot.session_id
        brief.base_card_state_revision = snapshot.base_card_state_revision
        brief.created_at = brief.created_at or now

        plan.plan_id = plan.plan_id or f"plan_{uuid.uuid4().hex[:12]}"
        plan.trace_id = snapshot.trace_id
        plan.snapshot_id = snapshot.snapshot_id
        plan.brief_id = brief.brief_id
        plan.card_id = snapshot.card_id
        plan.session_id = snapshot.session_id
        plan.created_at = plan.created_at or now

        return brief, plan


class FakeDirectorAdapter:
    """Fake Director for testing. Returns deterministic results."""

    def __init__(self):
        self._custom_brief: TurnBrief | None = None
        self._custom_plan: DelegationPlan | None = None

    def set_brief(self, brief: TurnBrief):
        self._custom_brief = brief

    def set_plan(self, plan: DelegationPlan):
        self._custom_plan = plan

    def generate(
        self, snapshot: RoundSnapshot
    ) -> tuple[TurnBrief, DelegationPlan]:
        brief = self._custom_brief or TurnBrief(
            turn_goal="Continue the narrative naturally",
            player_intent=snapshot.player_input[:100],
            scene_summary=snapshot.card_state.scene_state.location or "Unknown scene",
            active_characters=list(snapshot.card_state.variables.keys())[:5],
            known_facts=[f"Revision: {snapshot.base_card_state_revision}"],
            must_preserve_facts=["Current scene state", "Character identities"],
            must_not_do=["Contradict established facts"],
            narrative_opportunities=["Add environmental detail"],
            suggested_focus="Atmosphere and character",
        )

        plan = self._custom_plan or DelegationPlan(tasks=[])

        return brief, plan
