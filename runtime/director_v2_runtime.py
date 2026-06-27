"""DirectorV2Runtime — upgraded Director for C1.

Director reads RoundSnapshot and produces:
- DirectorPlan (narrative decisions)
- ToolPlan (tool calls needed)
- DelegationPlan (future sub-agent needs, no execution in C1)

After tool execution, Director produces FinalTurnBrief.
Director does NOT produce player-visible text, write state, or write memory.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.director_plan import DirectorPlan
from ..contracts.tool_plan import ToolPlan, PlannedToolRequest
from ..contracts.delegation_plan import DelegationPlan
from ..contracts.enrichment_bundle import EnrichmentBundle
from ..contracts.final_turn_brief import FinalTurnBrief
from .final_turn_brief_runtime import FinalTurnBriefRuntime


class DirectorV2Adapter(Protocol):
    """Protocol for Director V2 adapters (fake or real LLM)."""
    def generate_plan(self, snapshot: RoundSnapshot) -> DirectorPlan:
        ...

    def generate_tool_plan(self, snapshot: RoundSnapshot, plan: DirectorPlan) -> ToolPlan:
        ...

    def generate_delegation_plan(self, snapshot: RoundSnapshot, plan: DirectorPlan) -> DelegationPlan:
        ...


class FakeDirectorV2Adapter:
    """Fake Director V2 for testing. Returns deterministic results."""

    def __init__(self):
        self._custom_plan: DirectorPlan | None = None
        self._custom_tool_plan: ToolPlan | None = None
        self._custom_delegation_plan: DelegationPlan | None = None

    def set_plan(self, plan: DirectorPlan):
        self._custom_plan = plan

    def set_tool_plan(self, plan: ToolPlan):
        self._custom_tool_plan = plan

    def set_delegation_plan(self, plan: DelegationPlan):
        self._custom_delegation_plan = plan

    def generate_plan(self, snapshot: RoundSnapshot) -> DirectorPlan:
        if self._custom_plan:
            return self._custom_plan
        return DirectorPlan(
            plan_id=f"dp_{uuid.uuid4().hex[:12]}",
            trace_id=snapshot.trace_id,
            snapshot_id=snapshot.snapshot_id,
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            player_intent=snapshot.player_input[:100],
            turn_goal="Continue the narrative naturally",
            scene_focus=snapshot.card_state.scene_state.location or "Unknown scene",
            active_character_refs=list(snapshot.card_state.variables.keys())[:5],
            must_preserve_facts=["Current scene state", "Character identities"],
            must_not_do=["Contradict established facts", "Override player agency"],
            narrative_opportunities=["Add environmental detail"],
            writer_constraints=["Maintain character consistency", "Stay in scene"],
            base_card_state_revision=snapshot.base_card_state_revision,
        )

    def generate_tool_plan(self, snapshot: RoundSnapshot, plan: DirectorPlan) -> ToolPlan:
        if self._custom_tool_plan:
            return self._custom_tool_plan
        return ToolPlan(
            tool_plan_id=f"tp_{uuid.uuid4().hex[:12]}",
            trace_id=snapshot.trace_id,
            snapshot_id=snapshot.snapshot_id,
            director_plan_id=plan.plan_id,
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            requests=[],
            max_request_count=5,
            total_token_budget=5000,
            total_time_budget_ms=60000,
        )

    def generate_delegation_plan(self, snapshot: RoundSnapshot, plan: DirectorPlan) -> DelegationPlan:
        if self._custom_delegation_plan:
            return self._custom_delegation_plan
        return DelegationPlan(tasks=[])


class DirectorV2Runtime:
    """Runtime for the Director V2 agent.

    Director produces structured plans, not free text.
    Director does NOT produce player-visible text, write state, or write memory.
    """

    def __init__(self, adapter: DirectorV2Adapter):
        self.adapter = adapter
        self._brief_runtime = FinalTurnBriefRuntime()

    def plan(self, snapshot: RoundSnapshot) -> tuple[DirectorPlan, ToolPlan, DelegationPlan]:
        """Run Director to produce DirectorPlan + ToolPlan + DelegationPlan."""
        now = datetime.now(timezone.utc).isoformat()

        # Generate DirectorPlan
        director_plan = self.adapter.generate_plan(snapshot)
        director_plan.plan_id = director_plan.plan_id or f"dp_{uuid.uuid4().hex[:12]}"
        director_plan.trace_id = snapshot.trace_id
        director_plan.snapshot_id = snapshot.snapshot_id
        director_plan.card_id = snapshot.card_id
        director_plan.session_id = snapshot.session_id
        director_plan.base_card_state_revision = snapshot.base_card_state_revision
        director_plan.created_at = director_plan.created_at or now

        # Generate ToolPlan
        tool_plan = self.adapter.generate_tool_plan(snapshot, director_plan)
        tool_plan.tool_plan_id = tool_plan.tool_plan_id or f"tp_{uuid.uuid4().hex[:12]}"
        tool_plan.trace_id = snapshot.trace_id
        tool_plan.snapshot_id = snapshot.snapshot_id
        tool_plan.director_plan_id = director_plan.plan_id
        tool_plan.card_id = snapshot.card_id
        tool_plan.session_id = snapshot.session_id
        tool_plan.created_at = tool_plan.created_at or now

        # Generate DelegationPlan
        delegation_plan = self.adapter.generate_delegation_plan(snapshot, director_plan)
        delegation_plan.plan_id = delegation_plan.plan_id or f"del_{uuid.uuid4().hex[:12]}"
        delegation_plan.trace_id = snapshot.trace_id
        delegation_plan.snapshot_id = snapshot.snapshot_id
        delegation_plan.brief_id = director_plan.plan_id
        delegation_plan.card_id = snapshot.card_id
        delegation_plan.session_id = snapshot.session_id
        delegation_plan.created_at = delegation_plan.created_at or now

        # Link back
        director_plan.tool_plan_ref = tool_plan.tool_plan_id
        director_plan.delegation_plan_ref = delegation_plan.plan_id

        return director_plan, tool_plan, delegation_plan

    def produce_final_brief(
        self,
        director_plan: DirectorPlan,
        enrichment: EnrichmentBundle,
        snapshot: RoundSnapshot,
    ) -> FinalTurnBrief:
        """Produce FinalTurnBrief after tool execution."""
        return self._brief_runtime.produce(director_plan, enrichment, snapshot)
