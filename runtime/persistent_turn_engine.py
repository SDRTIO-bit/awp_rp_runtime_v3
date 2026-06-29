"""Persistent turn engine — shared execution core for the persistent nodes.

P1 canonical path:
  Director → SubAgent Triggers (D1-D5, rule-based) → FinalTurnBrief → Writer
  → QualityGate → TurnEvolutionCurator (real LLM) → CardState patch
  → CardStateCommit → TurnRecordCommit → MemoryCommit (active + RAG)

Replaces P0's fake D6 (empty patches + deterministic fake memory) with:
  - TurnEvolutionCurator: single LLM call producing real state proposals
    and memory candidates
  - Real state patches with actual operations (no more empty operations=[])
  - Curator-driven memory (no more FakeMemoryCandidateGenerator)
  - Sub-agent rule triggers (D1-D5, deterministic, merged into Writer guidance)
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from ..contracts.round_snapshot import RoundSnapshot
from ..contracts.card_state import CardState
from ..contracts.card_state_commit import (
    CardStateCommitRequest, CardStateCommitStatus,
)
from ..contracts.card_state_patch import (
    CardStatePatch, CardStatePatchOperation, PatchOpType,
    validate_patch_operations,
)
from ..contracts.turn_record import TurnRecord, TurnMode
from ..contracts.quality_decision import QualityDecision, QualityVerdict
from ..contracts.final_turn_brief import FinalTurnBrief
from ..contracts.writer_draft import WriterDraft
from ..contracts.writer_input_bundle import WriterInputBundle
from ..contracts.first_turn_receipt import FirstTurnReceipt
from ..contracts.first_turn_diagnostics import FirstTurnDiagnostics
from ..contracts.execution_trace import ExecutionTrace, TraceEvent
from ..contracts.memory_commit_plan import (
    MemoryCommitPlan, MemoryCommitRequest, MemoryCommitStatus,
)
from ..contracts.active_memory import ActiveMemoryRecord
from ..contracts.rag_memory import RagMemoryRecord
from ..contracts.curator_request import CuratorRequest
from ..contracts.turn_evolution_proposal import (
    TurnEvolutionProposal, MemoryCandidate,
)

from .provider_adapter_factory import (
    DirectorAdapterFactory, WriterAdapterFactory,
    run_director, run_writer, AdapterOutcome,
)
from .writer_input_bundle_v2_builder import WriterInputBundleV2Builder
from .turn_evolution_curator import TurnEvolutionCurator
from .active_memory_commit_runtime import ActiveMemoryCommitRuntime
from .rag_memory_commit_runtime import RagMemoryCommitRuntime
# (no additional imports needed for sub-agent merge — inline SuggestionMergeResult used)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


def _ms_since(start: float) -> int:
    import time
    return int((time.time() - start) * 1000)


def _add_trace_event(
    trace: ExecutionTrace,
    event_type: str,
    actor: str,
    success: bool,
    duration_ms: int = 0,
    details: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    trace.add_event(TraceEvent(
        event_id=f"evt_{uuid.uuid4().hex[:8]}",
        event_type=event_type,
        timestamp=_now(),
        actor=actor,
        duration_ms=duration_ms,
        details=details or {},
        success=success,
        error=error,
    ))


def _plan_hash(plan: Any) -> str:
    """Stable short hash of a DirectorPlan for trace evidence (no raw content)."""
    try:
        blob = plan.to_dict() if hasattr(plan, "to_dict") else str(plan)
    except Exception:
        blob = str(plan)
    return hashlib.sha256(str(blob).encode("utf-8")).hexdigest()[:16]


class PersistentTurnEngine:
    """Runs one accepted turn with full evidence capture.

    The caller provides a RoundSnapshot already assembled (by the node).
    Returns a populated (receipt, context, diagnostics, card_state,
    turn_record, round_snapshot) tuple, mirroring the node RETURN contract.
    """

    def __init__(self, registry, profile: str = "production"):
        self._registry = registry
        self._profile = profile

    def _run_sub_agent_triggers(
        self,
        snapshot: Any,
        director_plan: Any,
        binding: Any,
        turn_id: str,
        trace_id: str,
    ) -> tuple[list, list[str], list[dict[str, Any]]]:
        """Evaluate D1-D5 trigger policies and collect suggestions.

        Runs deterministic trigger rules (no LLM calls). Returns
        (agent_suggestions, triggered_agent_names, trigger_diagnostics).
        """
        import uuid as _uuid
        from ..contracts.agent_suggestion import AgentSuggestion, SuggestionKind

        suggestions: list = []
        triggered: list[str] = []
        trigger_diagnostics: list[dict[str, Any]] = []

        # ── D1: History Recall ─────────────────────────────────────────
        try:
            from ..runtime.history_recall_trigger_policy import HistoryRecallTriggerPolicy
            hr_trigger = HistoryRecallTriggerPolicy().evaluate(snapshot, director_plan)
            trigger_diagnostics.append({
                "agent": "d1_history_recall",
                "should_trigger": bool(hr_trigger.should_trigger),
                "reasons": list(getattr(hr_trigger, "trigger_reasons", []) or []),
                "error": "",
            })
            if hr_trigger.should_trigger:
                triggered.append("d1_history_recall")
                s = AgentSuggestion(
                    suggestion_id=f"d1_{_uuid.uuid4().hex[:8]}",
                    trace_id=trace_id,
                    task_run_id=f"d1_{turn_id}",
                    role="history_recall",
                    kind=SuggestionKind.HISTORICAL_CONFLICT if hr_trigger.risk_level.value in ("high",) else SuggestionKind.IDENTITY_CLARIFICATION,
                    priority=0.8,
                    confidence=0.7,
                    summary=f"[D1-History] {', '.join(hr_trigger.trigger_reasons[:3])}",
                    recommendations=hr_trigger.suggested_recall_kinds,
                    risk_flags=[hr_trigger.risk_level.value],
                )
                suggestions.append(s)
        except Exception as e:
            trigger_diagnostics.append({
                "agent": "d1_history_recall",
                "should_trigger": False,
                "reasons": [],
                "error": str(e)[:200],
            })

        # ── D2: Opportunity ───────────────────────────────────────────
        try:
            from ..runtime.opportunity_trigger_policy import OpportunityTriggerPolicy
            op_trigger = OpportunityTriggerPolicy().evaluate(snapshot, director_plan)
            trigger_diagnostics.append({
                "agent": "d2_opportunity",
                "should_trigger": bool(op_trigger.should_trigger),
                "reasons": list(getattr(op_trigger, "trigger_reasons", []) or []),
                "error": "",
            })
            if op_trigger.should_trigger:
                triggered.append("d2_opportunity")
                s = AgentSuggestion(
                    suggestion_id=f"d2_{_uuid.uuid4().hex[:8]}",
                    trace_id=trace_id,
                    task_run_id=f"d2_{turn_id}",
                    role="opportunity",
                    kind=SuggestionKind.NARRATIVE_OPPORTUNITY,
                    priority=0.6,
                    confidence=0.6,
                    summary=f"[D2-Opportunity] {', '.join(op_trigger.trigger_reasons[:3])}",
                )
                suggestions.append(s)
        except Exception as e:
            trigger_diagnostics.append({
                "agent": "d2_opportunity",
                "should_trigger": False,
                "reasons": [],
                "error": str(e)[:200],
            })

        # ── D3: World Life ────────────────────────────────────────────
        try:
            from ..runtime.world_life_trigger_policy import WorldLifeTriggerPolicy
            wl_trigger = WorldLifeTriggerPolicy().evaluate(snapshot, director_plan)
            trigger_diagnostics.append({
                "agent": "d3_world_life",
                "should_trigger": bool(wl_trigger.should_trigger),
                "reasons": list(getattr(wl_trigger, "trigger_reasons", []) or []),
                "error": "",
            })
            if wl_trigger.should_trigger:
                triggered.append("d3_world_life")
                s = AgentSuggestion(
                    suggestion_id=f"d3_{_uuid.uuid4().hex[:8]}",
                    trace_id=trace_id,
                    task_run_id=f"d3_{turn_id}",
                    role="world_life",
                    kind=SuggestionKind.WORLD_DETAIL,
                    priority=0.5,
                    confidence=0.5,
                    summary=f"[D3-WorldLife] {', '.join(wl_trigger.trigger_reasons[:3])}",
                )
                suggestions.append(s)
        except Exception as e:
            trigger_diagnostics.append({
                "agent": "d3_world_life",
                "should_trigger": False,
                "reasons": [],
                "error": str(e)[:200],
            })

        # ── D4: Emotion Relationship ──────────────────────────────────
        try:
            from ..runtime.emotion_relationship_trigger_policy import EmotionRelationshipTriggerPolicy
            er_trigger = EmotionRelationshipTriggerPolicy().evaluate(snapshot, director_plan)
            trigger_diagnostics.append({
                "agent": "d4_emotion_rel",
                "should_trigger": bool(er_trigger.should_trigger),
                "reasons": list(getattr(er_trigger, "trigger_reasons", []) or []),
                "error": "",
            })
            if er_trigger.should_trigger:
                triggered.append("d4_emotion_rel")
                s = AgentSuggestion(
                    suggestion_id=f"d4_{_uuid.uuid4().hex[:8]}",
                    trace_id=trace_id,
                    task_run_id=f"d4_{turn_id}",
                    role="emotion_relationship",
                    kind=SuggestionKind.RELATIONSHIP_SHIFT,
                    priority=0.7,
                    confidence=0.6,
                    summary=f"[D4-Emotion] {', '.join(er_trigger.trigger_reasons[:3])}",
                )
                suggestions.append(s)
        except Exception as e:
            trigger_diagnostics.append({
                "agent": "d4_emotion_rel",
                "should_trigger": False,
                "reasons": [],
                "error": str(e)[:200],
            })

        # ── D5: Continuity ────────────────────────────────────────────
        try:
            from ..runtime.continuity_trigger_policy import ContinuityTriggerPolicy
            ct_trigger = ContinuityTriggerPolicy().evaluate(snapshot, director_plan)
            trigger_diagnostics.append({
                "agent": "d5_continuity",
                "should_trigger": bool(ct_trigger.should_trigger),
                "reasons": list(getattr(ct_trigger, "trigger_reasons", []) or []),
                "error": "",
            })
            if ct_trigger.should_trigger:
                triggered.append("d5_continuity")
                s = AgentSuggestion(
                    suggestion_id=f"d5_{_uuid.uuid4().hex[:8]}",
                    trace_id=trace_id,
                    task_run_id=f"d5_{turn_id}",
                    role="continuity",
                    kind=SuggestionKind.CONTINUITY_FACT_CONSTRAINT,
                    priority=0.9,
                    confidence=0.8,
                    summary=f"[D5-Continuity] {', '.join(ct_trigger.trigger_reasons[:3])}",
                )
                suggestions.append(s)
        except Exception as e:
            trigger_diagnostics.append({
                "agent": "d5_continuity",
                "should_trigger": False,
                "reasons": [],
                "error": str(e)[:200],
            })

        return suggestions, triggered, trigger_diagnostics

    def execute(
        self,
        *,
        session_id: str,
        player_input: str,
        binding: Any,
        snapshot: RoundSnapshot,
        card_state: CardState,
        turn_id: str,
        attempt_id: str,
        request_id: str,
        workflow_run_id: str,
        trace_id: str,
        director_profile_id: str,
        writer_profile_id: str,
        turn_kind: str,
        writer_preset_path: str = "",
        opening_context: dict[str, Any] | None = None,
        worldbook_context: list[dict[str, Any]] | None = None,
    ) -> tuple[dict, dict, dict, dict, dict, dict]:
        import time
        now = _now()
        t_start = time.time()

        diag = FirstTurnDiagnostics(
            diagnostics_id=_id("ptd", request_id),
            request_id=request_id, trace_id=trace_id,
            session_id=session_id,
            director_profile_id=director_profile_id,
            writer_profile_id=writer_profile_id,
        )

        trace = ExecutionTrace(
            trace_id=trace_id, turn_id=turn_id,
            card_id=binding.logical_card_id, session_id=session_id,
        )

        # Effects tracking (for TurnResultProjection)
        effects: dict[str, Any] = {
            "state_effects": {
                "status": "no_state_change",
                "changed_paths": [],
                "event_ids": [],
                "relationship_changes": [],
            },
            "memory_effects": {
                "active_added": 0,
                "active_evicted": 0,
                "rag_added": 0,
            },
            "delegation": {
                "requested": [],
                "executed": [],
                "trigger_diagnostics": [],
            },
        }

        # ── Capture memory-use evidence from the snapshot ───────────────
        diag.round_snapshot_id = snapshot.snapshot_id
        diag.l1_turn_ids_recalled = [t.turn_id for t in snapshot.recent_turn_records]
        diag.l2_memory_ids_recalled = [
            m.get("memory_id", "") for m in snapshot.active_memories if m.get("memory_id")
        ]
        diag.l3_memory_ids_recalled = [
            r.get("memory_id", "") for r in snapshot.rag_recall if r.get("memory_id")
        ]
        diag.worldbook_entry_ids_considered = [
            e.get("entry_id", e.get("id", "")) for e in snapshot.active_worldbook_entries
            if e.get("entry_id") or e.get("id")
        ]
        diag.worldbook_entry_ids_activated = list(diag.worldbook_entry_ids_considered)
        diag.worldbook_candidate_count = len(worldbook_context or snapshot.active_worldbook_entries)
        diag.worldbook_activated_count = len(snapshot.active_worldbook_entries)
        diag.card_state_revision_before = card_state.revision

        _add_trace_event(trace, "round_snapshot", "round_snapshot_builder",
                         success=True, details={
                             "snapshot_id": snapshot.snapshot_id,
                             "l1_turn_ids_recalled": diag.l1_turn_ids_recalled,
                             "l2_memory_ids_recalled": diag.l2_memory_ids_recalled,
                             "l3_memory_ids_recalled": diag.l3_memory_ids_recalled,
                             "worldbook_entry_ids_activated": diag.worldbook_entry_ids_activated,
                         })
        diag.steps_completed.append("round_snapshot")

        # ── Director ─────────────────────────────────────────────────────
        step_start = time.time()
        dir_adapter, dir_outcome = DirectorAdapterFactory.build(director_profile_id)
        diag.director_provider_type = dir_outcome.provider
        diag.director_model = dir_outcome.model

        if not dir_outcome.built:
            diag.director_failure_code = dir_outcome.failure_code
            diag.steps_failed.append("director")
            diag.outcome = "failure"
            diag.failure_code = "DIRECTOR_" + dir_outcome.failure_code
            diag.failure_message = dir_outcome.failure_message
            _add_trace_event(trace, "director", "director", success=False,
                             duration_ms=_ms_since(step_start),
                             error=dir_outcome.failure_message,
                             details={"failure_code": dir_outcome.failure_code,
                                      "profile_id": director_profile_id,
                                      "provider": dir_outcome.provider})
            self._persist_trace(trace, diag)
            return self._failure_return(diag, trace, card_state, snapshot, effects)

        director_plan, dir_receipt = run_director(
            dir_adapter, dir_outcome, snapshot,
            workflow_run_id, trace_id, turn_id, attempt_id,
        )
        if director_plan is None:
            fc = dir_receipt.get("failure_code", "DIRECTOR_FAILED")
            diag.director_failure_code = fc
            diag.director_call_success = False
            diag.steps_failed.append("director")
            diag.outcome = "failure"
            diag.failure_code = "DIRECTOR_" + fc
            diag.failure_message = dir_receipt.get("failure_message", "director failed")
            _add_trace_event(trace, "director", "director", success=False,
                             duration_ms=_ms_since(step_start),
                             error=diag.failure_message,
                             details={"failure_code": fc, "provider": dir_outcome.provider})
            self._persist_trace(trace, diag)
            return self._failure_return(diag, trace, card_state, snapshot, effects)

        director_plan.plan_id = getattr(director_plan, "plan_id", "") or _id("dp", turn_id)
        director_plan.trace_id = trace_id
        director_plan.snapshot_id = snapshot.snapshot_id
        director_plan.card_id = binding.logical_card_id
        director_plan.session_id = session_id
        director_plan.base_card_state_revision = snapshot.base_card_state_revision

        diag.director_call_success = True
        diag.director_plan_ref = getattr(director_plan, "plan_id", "") or _plan_hash(director_plan)
        brief = FinalTurnBrief(
            brief_id=_id("ftb", turn_id),
            trace_id=trace_id, snapshot_id=snapshot.snapshot_id,
            card_id=binding.logical_card_id, session_id=session_id,
            base_card_state_revision=snapshot.base_card_state_revision,
            turn_goal=director_plan.turn_goal,
            scene_focus=director_plan.scene_focus,
            must_preserve_facts=director_plan.must_preserve_facts,
            must_not_do=director_plan.must_not_do,
            writer_constraints=director_plan.writer_constraints,
            active_character_refs=director_plan.active_character_refs,
            narrative_opportunities=director_plan.narrative_opportunities,
        )

        # Director read-only tools: bounded ToolPlan -> ToolGateway -> FinalTurnBrief.
        # This keeps tool execution deterministic and auditable while giving the
        # first planning agent real context enrichment before Writer runs.
        try:
            try:
                raw_tool_plan = dir_adapter.generate_tool_plan(
                    snapshot, director_plan,
                    workflow_run_id=workflow_run_id,
                    trace_id=trace_id,
                    turn_id=turn_id,
                    attempt_id=attempt_id,
                )
            except TypeError:
                raw_tool_plan = dir_adapter.generate_tool_plan(snapshot, director_plan)

            tool_plan = raw_tool_plan[0] if isinstance(raw_tool_plan, tuple) else raw_tool_plan
            if tool_plan and getattr(tool_plan, "requests", None):
                from .tool_registry import ToolRegistry
                from .tool_permission_policy import ToolPermissionPolicy
                from .tool_budget_runtime import ToolBudgetRuntime
                from .tool_gateway import ToolGateway
                from .snapshot_tool_runner import SnapshotToolRunner
                from .enrichment_merger import EnrichmentMerger
                from .final_turn_brief_runtime import FinalTurnBriefRuntime

                tool_plan.tool_plan_id = tool_plan.tool_plan_id or _id("tp", turn_id)
                tool_plan.trace_id = trace_id
                tool_plan.snapshot_id = snapshot.snapshot_id
                tool_plan.director_plan_id = director_plan.plan_id
                tool_plan.card_id = binding.logical_card_id
                tool_plan.session_id = session_id
                director_plan.tool_plan_ref = tool_plan.tool_plan_id

                registry = ToolRegistry()
                gateway = ToolGateway(
                    registry,
                    ToolPermissionPolicy(registry),
                    ToolBudgetRuntime(),
                    SnapshotToolRunner(),
                )
                tool_bundle = gateway.execute(tool_plan, snapshot, trace)
                enrichment = EnrichmentMerger().merge(tool_bundle)
                brief = FinalTurnBriefRuntime().produce(director_plan, enrichment, snapshot)
                diag.steps_completed.append("director_tools")
                effects["delegation"]["director_tools"] = {
                    "requested": [req.tool_id for req in tool_plan.requests],
                    "successful": list(tool_bundle.successful_request_ids),
                    "degraded": list(tool_bundle.degraded_request_ids),
                    "failed": list(tool_bundle.failed_request_ids),
                }
        except Exception as e:
            _add_trace_event(trace, "director_tools", "tool_gateway",
                             success=False, error=str(e)[:200])
        _add_trace_event(trace, "director", "director", success=True,
                         duration_ms=_ms_since(step_start),
                         details={"plan_ref": diag.director_plan_ref,
                                  "provider": dir_outcome.provider,
                                  "model": dir_outcome.model})
        diag.steps_completed.append("director")

        # ── Sub-Agent rule triggers (D1-D5, deterministic) ───────────────
        agent_suggestions: list = []
        agent_triggers: list[str] = []
        agent_trigger_diagnostics: list[dict[str, Any]] = []

        # Evaluate D1-D5 trigger policies — these are pure rules, no LLM calls.
        # Produced AgentSuggestion.summary is merged into Writer guidance below.
        try:
            agent_suggestions, agent_triggers, agent_trigger_diagnostics = self._run_sub_agent_triggers(
                snapshot, director_plan, binding, turn_id, trace_id
            )
        except Exception as e:
            _add_trace_event(trace, "sub_agents", "trigger_policies",
                             success=False, error=str(e)[:200])
            agent_trigger_diagnostics.append({
                "agent": "trigger_policies",
                "should_trigger": False,
                "reasons": [],
                "error": str(e)[:200],
            })

        # ── Deepen triggered sub-agent summaries with cheap LLM calls ─────
        # Each triggered agent gets one DeepSeek Flash call (thinking disabled)
        # to produce concrete, context-specific analysis.
        if agent_suggestions and dir_outcome.is_real:
            try:
                from ..adapters.llm.deepseek_adapter import DeepSeekAdapter
                from ..adapters.llm.model_profile_registry import ModelProfileRegistry
                from .sub_agent_llm_runner import run_sub_agent_llm
                import os as _os

                # Build a flash-adapter for sub-agent LLM calls
                flash_model = "deepseek-v4-flash"
                try:
                    flash_profile = ModelProfileRegistry.resolve("deepseek-v4-flash-writer")
                    api_key_env = flash_profile.api_key_env or "DEEPSEEK_API_KEY"
                    if _os.environ.get(api_key_env, ""):
                        flash_adapter = DeepSeekAdapter(
                            model=flash_model,
                            default_max_tokens=500,
                            timeout_seconds=60,
                            max_retries=2,
                        )
                        for sug in agent_suggestions:
                            role = getattr(sug, "role", "") or ""
                            llm_text = run_sub_agent_llm(
                                role, snapshot, flash_adapter,
                                trace_id=trace_id, turn_id=turn_id,
                                attempt_id=attempt_id,
                            )
                            if llm_text:
                                sug.summary = f"[{role}] {llm_text}"
                except Exception:
                    # If flash adapter fails, keep the rule-generated summary
                    pass
            except ImportError:
                pass

        # Record triggered sub-agents in effects and trace
        if agent_suggestions:
            effects["delegation"]["executed"] = agent_triggers
            effects["delegation"]["requested"] = agent_triggers
            effects["delegation"]["trigger_diagnostics"] = agent_trigger_diagnostics
            diag.steps_completed.append(f"agents:{','.join(agent_triggers)}")
            _add_trace_event(trace, "sub_agents", "trigger_policies",
                             success=True,
                             details={"triggered": agent_triggers,
                                       "suggestions": len(agent_suggestions)})
        else:
            effects["delegation"]["trigger_diagnostics"] = agent_trigger_diagnostics

        # Build merge result from agent suggestions
        merge_result = None
        if agent_suggestions:
            from ..contracts.suggestion_merge_result import (
                SuggestionMergeResult, MergeItem, MergeDecision,
            )
            merge_result = SuggestionMergeResult(
                merge_id=_id("sm", turn_id),
                trace_id=trace_id,
                adopted=[MergeItem(suggestion_id=s.suggestion_id, task_id=s.task_id,
                                   role=s.role, decision=MergeDecision.ADOPTED,
                                   reason="trigger_policy", suggestion=s)
                         for s in agent_suggestions],
                ignored=[],
                conflicts=[],
                writer_guidance=[s.summary for s in agent_suggestions if s.summary],
                state_proposal_hints=[],
                memory_proposal_hints=[],
            )

        # ── Writer ───────────────────────────────────────────────────────
        step_start = time.time()
        writer_preset_text = ""
        if writer_preset_path:
            try:
                from ..presets.writer_preset_loader import load_writer_preset
                preset_name = writer_preset_path
                import os as _os
                if _os.path.sep in preset_name:
                    preset_name = _os.path.splitext(_os.path.basename(preset_name))[0]
                writer_preset_text = load_writer_preset(preset_name)
            except ImportError:
                pass

        wrt_adapter, wrt_outcome = WriterAdapterFactory.build(writer_profile_id, writer_preset_text)
        diag.writer_provider_type = wrt_outcome.provider
        diag.writer_model = wrt_outcome.model

        if not wrt_outcome.built:
            diag.writer_failure_code = wrt_outcome.failure_code
            diag.steps_failed.append("writer")
            diag.outcome = "failure"
            diag.failure_code = "WRITER_" + wrt_outcome.failure_code
            diag.failure_message = wrt_outcome.failure_message
            _add_trace_event(trace, "writer", "writer", success=False,
                             duration_ms=_ms_since(step_start),
                             error=wrt_outcome.failure_message,
                             details={"failure_code": wrt_outcome.failure_code})
            self._persist_trace(trace, diag)
            return self._failure_return(diag, trace, card_state, snapshot, effects)

        bundle = WriterInputBundleV2Builder().build(
            snapshot,
            brief,
            merge_result,
            opening_context=opening_context,
            worldbook_context=worldbook_context,
        )
        candidate_text, wrt_receipt = run_writer(
            wrt_adapter, wrt_outcome, bundle,
            workflow_run_id, trace_id, turn_id, attempt_id,
            snapshot=snapshot,
        )
        if not candidate_text.strip():
            fc = wrt_receipt.get("failure_code", "WRITER_FAILED")
            diag.writer_failure_code = fc
            diag.writer_call_success = False
            diag.steps_failed.append("writer")
            diag.outcome = "failure"
            diag.failure_code = "WRITER_" + fc
            diag.failure_message = wrt_receipt.get("failure_message", "writer produced empty text")
            _add_trace_event(trace, "writer", "writer", success=False,
                             duration_ms=_ms_since(step_start),
                             error=diag.failure_message,
                             details={"failure_code": fc})
            self._persist_trace(trace, diag)
            return self._failure_return(diag, trace, card_state, snapshot, effects)

        diag.writer_call_success = True
        _add_trace_event(trace, "writer", "writer", success=True,
                         duration_ms=_ms_since(step_start),
                         details={"text_length": len(candidate_text),
                                  "provider": wrt_outcome.provider,
                                  "model": wrt_outcome.model})
        diag.steps_completed.append("writer")

        # ── Quality Gate (deterministic, non-LLM) ────────────────────────
        step_start = time.time()
        quality_decision = self._quality_check(candidate_text, snapshot, trace_id)
        diag.quality_verdict = quality_decision.verdict.value
        diag.quality_blocking_reasons = list(quality_decision.blocking_reasons)
        _add_trace_event(trace, "quality_gate", "quality_pipeline", success=True,
                         duration_ms=_ms_since(step_start),
                         details={"verdict": quality_decision.verdict.value,
                                  "overall_score": quality_decision.overall_score,
                                  "blocking_reasons": quality_decision.blocking_reasons})
        diag.steps_completed.append("quality_gate")

        if not quality_decision.allows_side_effects():
            diag.steps_failed.append("quality_gate")
            diag.outcome = "quality_rejected"
            diag.failure_message = f"Quality gate rejected: {quality_decision.blocking_reasons}"
            receipt = FirstTurnReceipt(
                receipt_id=_id("ptr", request_id),
                request_id=request_id, workflow_run_id=workflow_run_id,
                trace_id=trace_id, turn_id=turn_id, attempt_id=attempt_id,
                session_id=session_id,
                logical_card_id=binding.logical_card_id,
                card_version=binding.card_version,
                source_hash=binding.source_hash,
                quality_verdict="reject", idempotency_status="new",
                created_at=now,
            )
            self._persist_trace(trace, diag)
            return (receipt.to_dict(), {}, diag.to_dict(),
                    card_state.to_dict(), {}, snapshot.to_dict())

        # ── TurnEvolutionCurator (P1: real LLM state + memory) ───────────
        step_start = time.time()
        curator_adapter = self._build_curator_adapter(dir_outcome)
        curator = TurnEvolutionCurator(llm_adapter=curator_adapter)

        curator_request = CuratorRequest(
            request_id=_id("cr", request_id),
            turn_id=turn_id, session_id=session_id, trace_id=trace_id,
            player_input=player_input,
            accepted_writer_output=candidate_text,
            pre_turn_card_state=card_state.to_dict(),
            final_turn_brief=brief.to_dict(),
            recent_turns=[
                {"turn_id": t.turn_id, "turn_index": t.turn_index,
                 "player_input": t.player_input, "writer_output": t.writer_output}
                for t in snapshot.recent_turn_records[:5]
            ],
            active_memory=list(snapshot.active_memories),
            resolved_worldbook_context=list(
                worldbook_context if worldbook_context is not None
                else snapshot.active_worldbook_entries
            ),
            agent_suggestions=[s.to_dict() for s in agent_suggestions],
            turn_kind=turn_kind,
            base_card_state_revision=card_state.revision,
        )

        curator_proposal = curator.curate(curator_request, trace=trace)

        _add_trace_event(trace, "turn_evolution_curator", "turn_evolution_curator",
                         success=True, duration_ms=_ms_since(step_start),
                         details={
                             "is_no_state_change": curator_proposal.is_no_state_change,
                             "op_count": len(curator_proposal.state_update_proposal.operations),
                             "active_candidates": len(curator_proposal.memory_candidates_active),
                             "rag_candidates": len(curator_proposal.memory_candidates_rag),
                             "curator_confidence": curator_proposal.curator_confidence,
                         })
        diag.steps_completed.append("turn_evolution_curator")

        # ── CardState Commit (P1: real patch from curator) ───────────────
        step_start = time.time()
        base_revision = card_state.revision
        operations = curator_proposal.state_update_proposal.operations

        if curator_proposal.is_no_state_change or not operations:
            # No real state change: do NOT increment revision
            result_revision = base_revision
            new_state = card_state
            patch = CardStatePatch(
                patch_id=_id("patch", turn_id),
                card_id=binding.logical_card_id, session_id=session_id,
                trace_id=trace_id, operations=[],
            )
            diag.card_state_commit_status = "no_state_change"
            effects["state_effects"]["status"] = "no_state_change"
            _add_trace_event(trace, "card_state_commit", "card_state_store",
                             success=True, duration_ms=_ms_since(step_start),
                             details={"status": "no_state_change",
                                      "from_revision": base_revision,
                                      "to_revision": base_revision})
        else:
            # Build real CardStatePatch from curator operations
            patch_ops = []
            changed_paths = []
            for op in operations:
                try:
                    op_type = PatchOpType(op["op"])
                except (ValueError, KeyError):
                    continue
                patch_ops.append(CardStatePatchOperation(
                    op=op_type, path=op["path"],
                    value=op.get("value"),
                    reason=op.get("reason", ""),
                ))
                changed_paths.append(op["path"])

            patch = CardStatePatch(
                patch_id=_id("patch", turn_id),
                card_id=binding.logical_card_id, session_id=session_id,
                trace_id=trace_id, operations=patch_ops,
                source="turn_evolution_curator",
            )

            # Apply operations to produce new state
            new_card_state_dict = card_state.to_dict()
            for pop in patch_ops:
                parts = pop.path.split(".")
                prefix = parts[0]
                key = parts[1] if len(parts) > 1 else ""

                if pop.op == PatchOpType.SET and prefix == "variables":
                    new_card_state_dict.setdefault("variables", {})[key] = {
                        "name": key, "value": pop.value,
                        "var_type": type(pop.value).__name__ if pop.value is not None else "string",
                        "description": "", "last_updated_turn": None,
                    }
                elif pop.op == PatchOpType.INCREMENT and prefix == "variables":
                    vars_dict = new_card_state_dict.setdefault("variables", {})
                    if key in vars_dict:
                        delta = pop.value if pop.value is not None else 1
                        vars_dict[key]["value"] = vars_dict[key].get("value", 0) + delta
                elif pop.op == PatchOpType.SET_FLAG and prefix == "event_flags":
                    new_card_state_dict.setdefault("event_flags", {})[key] = {
                        "event_id": key, "fired": True,
                        "fired_at_turn": None,
                        "metadata": pop.value if isinstance(pop.value, dict) else {},
                    }
                elif pop.op == PatchOpType.SET_SCENE_FIELD and prefix == "scene_state":
                    new_card_state_dict.setdefault("scene_state", {})[key] = pop.value

            new_state = CardState.from_dict(new_card_state_dict)
            new_state = CardState(
                card_id=new_state.card_id, session_id=new_state.session_id,
                revision=card_state.revision + 1,
                variables=new_state.variables,
                event_flags=new_state.event_flags,
                active_stage_ids=new_state.active_stage_ids,
                scene_state=new_state.scene_state,
                diagnostics=new_state.diagnostics,
                created_at=new_state.created_at, updated_at=now,
                last_accepted_turn_id=new_state.last_accepted_turn_id,
            )

            commit_request = CardStateCommitRequest(
                expected_revision=card_state.revision, patch=patch,
            )
            state_result = self._registry.card_state_store.commit(commit_request, new_state)
            diag.card_state_commit_status = state_result.status.value

            _add_trace_event(trace, "card_state_commit", "card_state_store",
                             success=(state_result.status == CardStateCommitStatus.ACCEPTED),
                             duration_ms=_ms_since(step_start),
                             details={"status": state_result.status.value,
                                      "from_revision": card_state.revision,
                                      "to_revision": state_result.to_revision,
                                      "op_count": len(patch_ops),
                                      "changed_paths": changed_paths})

            if state_result.status != CardStateCommitStatus.ACCEPTED:
                diag.steps_failed.append("state_commit")
                diag.outcome = "failure"
                diag.failure_message = f"CardState commit failed: {state_result.error_message}"
                effects["state_effects"]["status"] = "rejected"
                self._persist_trace(trace, diag)
                return self._failure_return(diag, trace, card_state, snapshot, effects)

            result_revision = state_result.to_revision
            effects["state_effects"]["status"] = "committed"
            effects["state_effects"]["changed_paths"] = changed_paths

            # Extract event_ids and relationship changes from proposal
            for evt in curator_proposal.event_summary:
                eid = evt.get("event_id", "")
                if eid:
                    effects["state_effects"]["event_ids"].append(eid)
            effects["state_effects"]["relationship_changes"] = [
                r for r in curator_proposal.relationship_summary
            ]

        diag.steps_completed.append("state_commit")
        diag.card_state_revision_after = result_revision

        # ── TurnRecord Commit ────────────────────────────────────────────
        step_start = time.time()
        next_turn_index = self._registry.turn_record_store.get_next_turn_index(
            binding.logical_card_id, session_id
        )
        turn_record = TurnRecord(
            turn_id=turn_id, trace_id=trace_id,
            session_id=session_id, card_id=binding.logical_card_id,
            turn_index=next_turn_index,
            player_input=player_input, writer_output=candidate_text,
            mode=TurnMode.NORMAL,
            base_card_state_revision=base_revision,
            result_card_state_revision=result_revision,
            quality_decision_ref=turn_id,
            round_snapshot_ref=snapshot.snapshot_id,
            state_commit_ref=patch.patch_id,
            created_at=now, accepted_at=now,
        )
        try:
            self._registry.turn_record_store.save(turn_record)
            diag.turn_record_commit_status = "committed"
            diag.turn_record_id = turn_id
        except Exception as e:
            from ..storage.interfaces import DuplicateTurnError
            if isinstance(e, DuplicateTurnError):
                diag.turn_record_commit_status = "failed"
                diag.steps_failed.append("turn_commit")
                diag.outcome = "failure"
                diag.failure_message = f"Duplicate turn: {e}"
                self._persist_trace(trace, diag)
                return self._failure_return(diag, trace, new_state, snapshot, effects)
            diag.turn_record_commit_status = "failed"
            diag.steps_failed.append("turn_commit")
            diag.outcome = "failure"
            diag.failure_message = f"TurnRecord commit failed: {e}"
            self._persist_trace(trace, diag)
            return self._failure_return(diag, trace, new_state, snapshot, effects)

        _add_trace_event(trace, "turn_record_commit", "turn_record_store",
                         success=True, duration_ms=_ms_since(step_start),
                         details={"turn_id": turn_id, "turn_index": next_turn_index,
                                  "base_revision": base_revision,
                                  "result_revision": result_revision})
        diag.steps_completed.append("turn_commit")

        # ── Memory Commit (P1: from curator proposal, not fake D6) ───────
        memory_status, active_ids, rag_ids, commit_ids = self._run_memory_commit(
            curator_proposal, turn_record, snapshot, quality_decision,
            result_revision, trace_id, turn_id, binding, trace, now,
        )
        diag.memory_curation_status = memory_status
        diag.active_memory_committed_ids = active_ids
        diag.rag_memory_committed_ids = rag_ids
        diag.memory_commit_ids = commit_ids
        diag.steps_completed.append("memory_curator")
        effects["memory_effects"]["active_added"] = len(active_ids)
        effects["memory_effects"]["rag_added"] = len(rag_ids)

        # ── Persist trace ────────────────────────────────────────────────
        diag.outcome = "success"
        self._persist_trace(trace, diag)

        receipt = FirstTurnReceipt(
            receipt_id=_id("ptr", request_id),
            request_id=request_id, workflow_run_id=workflow_run_id,
            trace_id=trace_id, turn_id=turn_id, attempt_id=attempt_id,
            session_id=session_id,
            logical_card_id=binding.logical_card_id,
            card_version=binding.card_version,
            source_hash=binding.source_hash,
            accepted_text=candidate_text[:200],
            quality_verdict="accept",
            base_card_state_revision=base_revision,
            result_card_state_revision=result_revision,
            card_state_commit_status="accepted",
            turn_record_id=turn_record.turn_id,
            turn_index=turn_record.turn_index,
            turn_record_commit_status="committed",
            memory_curation_status=memory_status,
            active_memory_write_count=len(active_ids),
            rag_memory_write_count=len(rag_ids),
            idempotency_status="fresh",
            created_at=now,
        )

        ctx = {
            "turn_id": turn_id,
            "turn_index": next_turn_index,
            "turn_kind": turn_kind,
            "session_id": session_id,
            "logical_card_id": binding.logical_card_id,
            "recent_accepted_turn_count": len(snapshot.recent_turn_records),
            "active_memory_count": len(snapshot.active_memories),
            "rag_recall_count": len(snapshot.rag_recall),
            "base_card_state_revision": base_revision,
            "result_card_state_revision": result_revision,
            "workflow_run_id": workflow_run_id,
            "trace_id": trace_id,
            "idempotency_status": "fresh",
            "director_provider": diag.director_provider_type,
            "writer_provider": diag.writer_provider_type,
            "created_at": now,
            "effects": effects,
        }

        return (
            receipt.to_dict(), ctx, diag.to_dict(),
            new_state.to_dict(), turn_record.to_dict(), snapshot.to_dict(),
        )

    # ── Quality gate (deterministic, existing rules) ────────────────────
    def _quality_check(
        self, candidate_text: str, snapshot: RoundSnapshot, trace_id: str,
    ) -> QualityDecision:
        from .quality_pipeline_runtime import QualityPipelineRuntime
        from ..contracts.writer_draft import WriterDraft
        draft = WriterDraft(
            draft_id=f"qd_{uuid.uuid4().hex[:8]}",
            trace_id=trace_id, snapshot_id=snapshot.snapshot_id,
            text=candidate_text,
        )
        pipeline = QualityPipelineRuntime()
        decision = pipeline.check(draft, snapshot)

        # ── Word count diagnostic gate (diagnostic only, NEVER blocks turn) ──
        MIN_CHARS = 1000
        text_len = len(candidate_text.strip()) if candidate_text else 0
        word_count_passed = text_len >= MIN_CHARS
        word_count_grade = "pass" if word_count_passed else (
            "fail" if text_len < 500 else "marginal"
        )
        decision.checks.append({
            "check": "word_count",
            "actual": text_len,
            "required": MIN_CHARS,
            "passed": word_count_passed,
            "grade": word_count_grade,
        })

        if text_len < MIN_CHARS:
            if text_len < 100:
                reason = f"CRITICAL: {text_len} chars — near-empty output"
                decision.warnings.append(reason)
            elif text_len < 500:
                reason = f"SEVERE: {text_len} chars — model returned short output"
                decision.warnings.append(reason)
            elif text_len < 800:
                reason = f"MODERATE: {text_len} chars — below 1000-char target"
                decision.warnings.append(reason)
            else:
                reason = f"CLOSE: {text_len} chars — near 1000 minimum"
                decision.warnings.append(reason)

            decision.acceptance_notes.append(
                f"word_count_diagnostic: {text_len}/{MIN_CHARS} grade={word_count_grade} — {reason}"
            )

        return decision

    # ── Curator adapter builder ─────────────────────────────────────────
    def _build_curator_adapter(self, dir_outcome: Any) -> Any:
        """Build an LLM adapter for the TurnEvolutionCurator.

        If the Director uses a real provider, reuse the same provider for
        the curator (same DeepSeek adapter). If the Director is fake,
        return None (deterministic curator fallback).
        """
        if not dir_outcome.is_real:
            return None

        try:
            from ..adapters.llm.deepseek_adapter import DeepSeekAdapter
            from ..adapters.llm.model_profile_registry import ModelProfileRegistry
            import os

            profile = ModelProfileRegistry.resolve(
                getattr(dir_outcome, 'profile_id', '')
            )
            api_key_env = profile.api_key_env or "DEEPSEEK_API_KEY"
            if not os.environ.get(api_key_env, ""):
                return None

            return DeepSeekAdapter(
                model=profile.model,
                default_max_tokens=profile.default_max_tokens,
                timeout_seconds=profile.timeout_seconds,
                max_retries=profile.max_retries,
            )
        except Exception:
            return None

    # ── P1 memory commit from TurnEvolutionProposal ─────────────────────
    def _run_memory_commit(
        self,
        proposal: TurnEvolutionProposal,
        turn_record: TurnRecord,
        snapshot: RoundSnapshot,
        quality_decision: QualityDecision,
        result_revision: int,
        trace_id: str,
        turn_id: str,
        binding: Any,
        trace: ExecutionTrace,
        now: str,
    ) -> tuple[str, list[str], list[str], list[str]]:
        """Commit memory candidates from the TurnEvolutionProposal.

        Compiles curator MemoryCandidates into MemoryCommitPlan and
        commits via ActiveMemoryCommitRuntime / RagMemoryCommitRuntime.
        """
        import time
        step_start = time.time()
        active_ids: list[str] = []
        rag_ids: list[str] = []
        commit_ids: list[str] = []
        memory_status = "noop"

        active_candidates = proposal.memory_candidates_active
        rag_candidates = proposal.memory_candidates_rag

        if not active_candidates and not rag_candidates:
            _add_trace_event(trace, "memory_curator", "turn_evolution_curator",
                             success=True, duration_ms=_ms_since(step_start),
                             details={"status": "noop",
                                      "skip_reason": "no_memory_candidates"})
            return "noop", active_ids, rag_ids, commit_ids

        # Compile curator candidates into MemoryCommitPlan
        new_active_entries: list[ActiveMemoryRecord] = []
        new_rag_entries: list[RagMemoryRecord] = []

        for cand in active_candidates[:5]:  # Max 5 active per turn
            content = cand.content[:80]
            if not content:
                continue
            kind = cand.kind or "scene_pressure"
            new_active_entries.append(ActiveMemoryRecord(
                memory_id=f"am_{turn_id}_{hashlib.sha256(content.encode()).hexdigest()[:8]}",
                card_id=binding.logical_card_id,
                session_id=turn_record.session_id,
                summary=content,
                kind=kind,
                entity_refs=list(cand.entity_refs),
                source_turn_ids=[turn_id],
                source_card_state_revision=result_revision,
                importance=cand.importance,
                confidence=proposal.curator_confidence or 0.6,
                status="active",
                retention_reason=cand.reason,
                created_at=now,
            ))

        for cand in rag_candidates[:3]:  # Max 3 rag per turn
            content = cand.content[:200]
            if not content:
                continue
            new_rag_entries.append(RagMemoryRecord(
                memory_id=f"rag_{turn_id}_{hashlib.sha256(content.encode()).hexdigest()[:8]}",
                card_id=binding.logical_card_id,
                session_id=turn_record.session_id,
                scope="session",
                content=content,
                summary=content[:80],
                source_turn_ids=[turn_id],
                source_card_state_revision=result_revision,
                importance=cand.importance,
                confidence=proposal.curator_confidence or 0.6,
                provenance=f"curator:{turn_id}",
                event_tags=list(cand.tags),
            ))

        if not new_active_entries and not new_rag_entries:
            _add_trace_event(trace, "memory_curator", "turn_evolution_curator",
                             success=True, duration_ms=_ms_since(step_start),
                             details={"status": "noop",
                                      "skip_reason": "empty_candidates_after_compile"})
            return "noop", active_ids, rag_ids, commit_ids

        # Build plan
        memory_commit_id = f"mc_{uuid.uuid4().hex[:12]}"
        idempotency_key = f"{turn_id}:{memory_commit_id}"

        plan = MemoryCommitPlan(
            turn_id=turn_id,
            card_id=binding.logical_card_id,
            session_id=turn_record.session_id,
            trace_id=trace_id,
            expected_card_state_revision=result_revision,
            memory_commit_id=memory_commit_id,
            idempotency_key=idempotency_key,
            quality_decision_ref=turn_id,
            new_active_entries=new_active_entries,
            new_rag_entries=new_rag_entries,
            write_reasons=["turn_evolution_curator"],
        )

        # Commit active memories
        if new_active_entries:
            active_runtime = ActiveMemoryCommitRuntime(self._registry.active_memory_store)
            mem_request = MemoryCommitRequest(
                plan=plan,
                card_id=binding.logical_card_id, session_id=turn_record.session_id,
                turn_id=turn_id, trace_id=trace_id,
                memory_commit_id=plan.memory_commit_id,
                idempotency_key=plan.idempotency_key,
                quality_decision_ref=turn_id,
                expected_card_state_revision=result_revision,
                card_state_commit_success=True,
                turn_record_commit_success=True,
            )
            try:
                mem_result = active_runtime.commit_request(mem_request, quality_decision)
                if mem_result.status == MemoryCommitStatus.COMMITTED and mem_result.receipt:
                    active_ids = list(mem_result.receipt.committed_active_ids)
                    commit_ids.append(plan.memory_commit_id)
                    memory_status = "curated_active"
                elif mem_result.status == MemoryCommitStatus.IDEMPOTENT_REPLAY and mem_result.receipt:
                    active_ids = list(mem_result.receipt.committed_active_ids)
                    memory_status = "curated_active_replay"
                else:
                    memory_status = f"active_blocked:{mem_result.status}"
            except Exception as e:
                memory_status = "failed"
                _add_trace_event(trace, "active_memory_commit", "active_memory_store",
                                 success=False, error=str(e)[:200])
                return memory_status, active_ids, rag_ids, commit_ids

        # Commit RAG memories
        if new_rag_entries:
            rag_runtime = RagMemoryCommitRuntime(self._registry.rag_memory_store)
            rag_request = MemoryCommitRequest(
                plan=plan,
                card_id=binding.logical_card_id, session_id=turn_record.session_id,
                turn_id=turn_id, trace_id=trace_id,
                memory_commit_id=f"rag_{plan.memory_commit_id}",
                idempotency_key=f"rag:{plan.idempotency_key}",
                quality_decision_ref=turn_id,
                expected_card_state_revision=result_revision,
                card_state_commit_success=True,
                turn_record_commit_success=True,
            )
            try:
                rag_result = rag_runtime.commit_request(rag_request, quality_decision)
                if rag_result.status == MemoryCommitStatus.COMMITTED and rag_result.receipt:
                    rag_ids = list(rag_result.receipt.committed_rag_ids)
                    commit_ids.append(f"rag_{plan.memory_commit_id}")
                    if memory_status in ("noop", "curated_active", "curated_active_replay"):
                        memory_status = "curated_both" if active_ids else "curated_rag"
                elif rag_result.status == MemoryCommitStatus.IDEMPOTENT_REPLAY and rag_result.receipt:
                    rag_ids = list(rag_result.receipt.committed_rag_ids)
                    if memory_status in ("noop", "curated_active", "curated_active_replay"):
                        memory_status = "curated_both_replay" if active_ids else "curated_rag_replay"
                else:
                    if not memory_status.startswith("failed"):
                        memory_status = f"rag_blocked:{rag_result.status}"
            except Exception as e:
                memory_status = "failed"
                _add_trace_event(trace, "rag_memory_commit", "rag_memory_store",
                                 success=False, error=str(e)[:200])
                return memory_status, active_ids, rag_ids, commit_ids

        _add_trace_event(trace, "memory_curator", "turn_evolution_curator",
                         success=(memory_status != "failed"),
                         duration_ms=_ms_since(step_start),
                         details={
                             "status": memory_status,
                             "active_committed_ids": active_ids,
                             "rag_committed_ids": rag_ids,
                             "commit_ids": commit_ids,
                             "active_candidates": len(active_candidates),
                             "rag_candidates": len(rag_candidates),
                         })
        return memory_status, active_ids, rag_ids, commit_ids

    def _persist_trace(self, trace: ExecutionTrace, diag: FirstTurnDiagnostics) -> None:
        try:
            trace.total_duration_ms = sum(
                (e.duration_ms or 0) for e in trace.events
            )
            self._registry.trace_store.save(trace)
            diag.trace_persisted = True
        except Exception:
            diag.trace_persisted = False

    def _failure_return(
        self, diag: FirstTurnDiagnostics, trace: ExecutionTrace,
        card_state: CardState, snapshot: RoundSnapshot,
        effects: dict[str, Any] | None = None,
    ) -> tuple[dict, dict, dict, dict, dict, dict]:
        return ({}, {}, diag.to_dict(),
                card_state.to_dict() if card_state else {}, {}, snapshot.to_dict())
