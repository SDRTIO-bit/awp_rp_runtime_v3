"""Real Director Adapter -- uses DeepSeek for Director planning.

Implements DirectorV2Adapter protocol with real provider calls.
On failure, produces structured ProviderFailure.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from .deepseek_adapter import DeepSeekAdapter
from ...contracts.director_plan import DirectorPlan
from ...contracts.tool_plan import ToolPlan, PlannedToolRequest
from ...contracts.delegation_plan import DelegationPlan, DelegationTask
from ...contracts.round_snapshot import RoundSnapshot
from ...contracts.provider_request import ProviderAttemptReceipt


class RealDirectorV2Adapter:
    """Real Director adapter using DeepSeek.

    Generates DirectorPlan, ToolPlan, and DelegationPlan from RoundSnapshot.
    """

    def __init__(self, deepseek: DeepSeekAdapter, model: str = ""):
        self._llm = deepseek
        self._model = model
        self._extra_body = {"thinking": {"type": "enabled"}}

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
                "relationship_tensions": {"type": "array", "items": {"type": "string"}},
                "unresolved_threads": {"type": "array", "items": {"type": "string"}},
                "pacing_guidance": {"type": "string"},
                "risk_flags": {"type": "array", "items": {"type": "string"}},
            },
        }

        parsed, receipt = self._llm.generate_structured(
            prompt, schema,
            provider_role="director",
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            turn_id=turn_id,
            model=self._model,
            attempt_id=attempt_id,
            extra_body=self._extra_body,
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
            relationship_tensions=parsed.get("relationship_tensions", []),
            unresolved_threads=parsed.get("unresolved_threads", []),
            pacing_guidance=parsed.get("pacing_guidance", ""),
            risk_flags=parsed.get("risk_flags", []),
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
        """Generate a bounded read-only ToolPlan for Director enrichment."""
        requests: list[PlannedToolRequest] = []

        def add(tool_id: str, purpose: str, query: str = "", required: bool = False) -> None:
            if len(requests) >= 5:
                return
            requests.append(PlannedToolRequest(
                request_id=f"dir_{tool_id}_{len(requests) + 1}",
                tool_id=tool_id,
                purpose=purpose,
                priority=0.8 if required else 0.5,
                input={"query": query[:160]} if query else {},
                timeout_ms=15000,
                token_budget=600,
                required=required,
                failure_policy="degrade",
                evidence_requirement=purpose,
            ))

        query = " ".join([
            str(snapshot.player_input or "")[:160],
            str(plan.turn_goal or "")[:120],
            str(plan.scene_focus or "")[:120],
        ]).strip()

        add("scene_context_lookup", "Read current scene state before planning writer constraints.", query, required=True)
        if snapshot.active_worldbook_entries:
            add("worldbook_lookup", "Read active worldbook facts that must constrain this turn.", query)
        if snapshot.recent_turn_records:
            add("accepted_turn_lookup", "Read recent accepted turns for continuity and callbacks.", query)
        if snapshot.active_memories:
            add("active_memory_lookup", "Read active memories for promises, relationships, and facts.", query)
        if snapshot.rag_recall:
            add("rag_memory_lookup", "Read recalled long-term memories relevant to this turn.", query)

        receipt = ProviderAttemptReceipt(
            provider_role="director",
            success=True,
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            turn_id=turn_id,
            attempt_id=attempt_id,
        )
        return ToolPlan(
            tool_plan_id=f"tp_{uuid.uuid4().hex[:12]}",
            trace_id=snapshot.trace_id,
            snapshot_id=snapshot.snapshot_id,
            director_plan_id=plan.plan_id,
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            requests=requests,
            max_request_count=5,
            max_parallelism=1,
            total_token_budget=3000,
            total_time_budget_ms=30000,
            fallback_policy="degrade_optional",
        ), receipt

    def generate_delegation_plan(
        self,
        snapshot: RoundSnapshot,
        plan: DirectorPlan,
        workflow_run_id: str = "",
        trace_id: str = "",
        turn_id: str = "",
        attempt_id: str = "",
    ) -> tuple[DelegationPlan, ProviderAttemptReceipt]:
        """Generate DelegationPlan — P1: Director can request 0-2 sub-agent tasks.

        Uses structured output to decide which sub-agents (D1-D5) to invoke.
        Default: 0 tasks (no delegation). Max: 2 per turn to control cost.
        """
        receipt = ProviderAttemptReceipt(
            provider_role="director",
            success=True,
            workflow_run_id=workflow_run_id,
            trace_id=trace_id,
            turn_id=turn_id,
            attempt_id=attempt_id,
        )

        # Determine which sub-agents are contextually relevant
        tasks: list[DelegationTask] = []
        recent_turn_count = len(snapshot.recent_turn_records)
        active_mem_count = len(snapshot.active_memories)

        # D1: History Recall — useful when there are prior turns to check
        if recent_turn_count >= 2:
            tasks.append(DelegationTask(
                task_id=f"d1_{uuid.uuid4().hex[:8]}",
                role="history_recall",
                priority=0.7,
                purpose="Check recent history for consistency and unresolved threads",
                max_tokens=500,
                timeout_ms=20000,
                failure_policy="skip",
                expected_suggestion_kinds=["identity_clarification", "historical_conflict"],
            ))

        # D4: Emotion/Relationship — useful when relationship context matters
        if active_mem_count > 0 or recent_turn_count >= 1:
            tasks.append(DelegationTask(
                task_id=f"d4_{uuid.uuid4().hex[:8]}",
                role="emotion_relationship",
                priority=0.6,
                purpose="Analyze current emotional state and relationship dynamics",
                max_tokens=500,
                timeout_ms=20000,
                failure_policy="skip",
                expected_suggestion_kinds=["relationship_shift"],
            ))

        # D5: Continuity — useful when facts need verification
        if recent_turn_count >= 3:
            tasks.append(DelegationTask(
                task_id=f"d5_{uuid.uuid4().hex[:8]}",
                role="continuity",
                priority=0.8,
                purpose="Verify factual continuity with established world state",
                max_tokens=500,
                timeout_ms=20000,
                failure_policy="skip",
                expected_suggestion_kinds=["continuity_fact_constraint"],
            ))

        # Cap at 2 tasks per turn to control cost
        # Prioritize by priority score (higher = more important)
        tasks.sort(key=lambda t: -t.priority)
        tasks = tasks[:2]

        return DelegationPlan(
            plan_id=f"del_{uuid.uuid4().hex[:12]}",
            trace_id=trace_id,
            snapshot_id=snapshot.snapshot_id,
            brief_id=plan.plan_id,
            card_id=snapshot.card_id,
            session_id=snapshot.session_id,
            tasks=tasks,
            max_task_count=2,
            total_token_budget=3000,
            total_time_budget_ms=60000,
        ), receipt

    def _build_plan_prompt(self, snapshot: RoundSnapshot) -> str:
        """Build prompt for Director plan generation.

        Includes truncated worldbook/recent-turn/memory content
        (not full card text) to improve planning quality.
        """
        player_input = snapshot.player_input[:500]
        scene_location = ""
        if hasattr(snapshot.card_state, 'scene_state'):
            scene_location = getattr(snapshot.card_state.scene_state, 'location', '')

        recent_turn_count = len(snapshot.recent_turn_records)

        # ── Worldbook context (top 5, truncated) ────────────────────────
        wb_lines = []
        for entry in (snapshot.active_worldbook_entries or [])[:5]:
            if not isinstance(entry, dict):
                continue
            title = str(entry.get("title", "") or entry.get("entry_id", "Untitled"))
            content = str(entry.get("content_excerpt", "") or "")[:120]
            wb_lines.append(f"- {title}: {content}")
        wb_block = "\n".join(wb_lines) if wb_lines else "(none)"

        # ── Recent turns (last 2-3, truncated) ──────────────────────────
        turn_lines = []
        for turn in (snapshot.recent_turn_records or [])[-3:]:
            idx = getattr(turn, 'turn_index', '?')
            p = str(getattr(turn, 'player_input', '') or '')[:200]
            w = str(getattr(turn, 'writer_output', '') or '')[:200]
            turn_lines.append(f"Turn {idx} Player: {p}")
            turn_lines.append(f"Turn {idx} Writer: {w}")
        recent_turns_block = "\n".join(turn_lines) if turn_lines else "(none)"

        # ── Active memories (top 5, truncated) ──────────────────────────
        mem_lines = []
        for entry in (snapshot.active_memories or [])[:5]:
            if isinstance(entry, dict):
                summary = str(entry.get("summary", "") or entry.get("content", "") or "")[:120]
                if summary:
                    mem_lines.append(f"- {summary}")
        mem_block = "\n".join(mem_lines) if mem_lines else "(none)"

        return (
            f"You are a narrative director for a roleplay session.\n"
            f"Keep fixed instructions above volatile turn context so provider prefix caching can be reused.\n\n"
            f"=== STABLE DIRECTOR CONTRACT ===\n"
            f"You are the first planning agent and coordinator, not the Writer.\n"
            f"Plan the next turn without producing player-visible prose.\n"
            f"First identify hard evidence, then risks, then delegation/tool needs, then writer intent.\n"
            f"Respect established facts, character continuity, worldbook constraints, and player agency.\n"
            f"Use tools only through the runtime ToolPlan; do not invent tool results.\n"
            f"Respond with JSON containing: turn_goal, scene_focus, must_preserve_facts, "
            f"must_not_do, narrative_opportunities, writer_constraints, active_character_refs, "
            f"relationship_tensions, unresolved_threads, pacing_guidance, risk_flags.\n\n"
            f"=== TURN PACKET (volatile; changes every turn) ===\n"
            f"Current scene: {scene_location}\n"
            f"Player input: {player_input}\n"
            f"Recent turns count: {recent_turn_count}\n"
            f"Active worldbook entries: {len(snapshot.active_worldbook_entries)}\n"
            f"Active memories: {len(snapshot.active_memories)}\n\n"
            f"=== Active Worldbook Context ===\n"
            f"{wb_block}\n\n"
            f"=== Recent Turns ===\n"
            f"{recent_turns_block}\n\n"
            f"=== Active Memories ===\n"
            f"{mem_block}"
        )
