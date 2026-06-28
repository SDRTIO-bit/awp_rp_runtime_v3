"""User simulation harness — long-session persistent real-runtime driver.

Independent CLI. Drives a multi-turn RP session through the persistent nodes
(AWPV2PersistentBootstrap → AWPV2PersistentFirstTurn →
AWPV2PersistentContinuationTurn) with a simulated player generating each
player input. Captures per-turn auditable artifacts and a final report.

Usage (real model):
  $env:AWP_REAL_LLM_E2E = "1"
  $env:DEEPSEEK_API_KEY = "..."
  $env:AWP_ALLOW_EXTERNAL_CARD_CONTENT = "1"
  python -m awp_rp_runtime_v2.testing.user_simulation_harness \
      --card-path "<card.json>" --turns 10 \
      --director-profile-id "deepseek-v4-pro-director" \
      --writer-profile-id "deepseek-v4-flash-writer" \
      --player-profile-id "simulated-player-v1" \
      --mode "debug-full" --restart-after-turn 5 --save-artifacts

Offline (fake profiles) works without any API key and is the default for CI.
Real-model execution requires explicit opt-in via AWP_REAL_LLM_E2E=1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .simulated_player_agent import (
    SimulatedPlayerAgent, PlayerSimulatorInput, build_debug_context,
)
from .quality_observer import QualityObserver


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


@dataclass
class ScenarioSpec:
    scenario_id: str = ""
    description: str = ""
    player_persona: str = ""
    global_goal: str = ""
    initial_action: str = ""
    planned_checkpoints: list[str] = field(default_factory=list)
    memory_probe_turns: list[int] = field(default_factory=list)
    required_facts: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ScenarioSpec":
        return cls(
            scenario_id=d.get("scenario_id", ""),
            description=d.get("description", ""),
            player_persona=d.get("player_persona", ""),
            global_goal=d.get("global_goal", ""),
            initial_action=d.get("initial_action", ""),
            planned_checkpoints=d.get("planned_checkpoints", []),
            memory_probe_turns=d.get("memory_probe_turns", []),
            required_facts=d.get("required_facts", []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "description": self.description,
            "player_persona": self.player_persona,
            "global_goal": self.global_goal,
            "initial_action": self.initial_action,
            "planned_checkpoints": self.planned_checkpoints,
            "memory_probe_turns": self.memory_probe_turns,
            "required_facts": self.required_facts,
        }


def load_scenario(name_or_path: str) -> ScenarioSpec:
    """Load a scenario by name from testing/scenarios/ or by absolute path."""
    p = Path(name_or_path)
    if not p.is_absolute():
        here = Path(__file__).parent / "scenarios" / f"{name_or_path}.json"
        if here.exists():
            p = here
        else:
            # treat as relative to cwd
            p = Path(name_or_path)
    if not p.exists():
        raise FileNotFoundError(f"Scenario not found: {name_or_path}")
    return ScenarioSpec.from_dict(json.loads(p.read_text(encoding="utf-8")))


def _is_real_run(director_profile_id: str, writer_profile_id: str,
                 player_profile_id: str) -> bool:
    """A run is 'real' if any profile is non-fake."""
    from ..adapters.llm.model_profile_registry import ModelProfileRegistry
    for pid in (director_profile_id, writer_profile_id, player_profile_id):
        try:
            if ModelProfileRegistry.resolve(pid).provider != "fake":
                return True
        except ValueError:
            pass
    return False


def _require_real_env() -> None:
    """Double-opt-in guard for real model runs. Exits if not configured."""
    if os.environ.get("AWP_REAL_LLM_E2E") != "1":
        print("REJECTED: AWP_REAL_LLM_E2E is not '1'. Real model runs require explicit opt-in.")
        sys.exit(2)
    if os.environ.get("AWP_ALLOW_EXTERNAL_CARD_CONTENT") != "1":
        print("REJECTED: AWP_ALLOW_EXTERNAL_CARD_CONTENT is not '1'.")
        sys.exit(2)
    if not os.environ.get("DEEPSEEK_API_KEY", ""):
        print("REJECTED: DEEPSEEK_API_KEY is not set.")
        sys.exit(2)


def _seed_session_from_card(registry, session_id: str, card_path: str) -> str:
    """Bootstrap a session via AWPV2PersistentBootstrap using a real card file.

    Returns the logical_card_id.
    """
    from ..nodes.persistent_bootstrap_node import AWPV2PersistentBootstrap
    node = AWPV2PersistentBootstrap()
    binding_dict, opening_dict, wb_dict, receipt_dict, diag_dict = node.execute(
        source_path=card_path,
        session_id=session_id,
        greeting_id="g0",
        request_id=_id("bsr", session_id),
    )
    if not binding_dict:
        raise RuntimeError(
            f"Bootstrap failed: {diag_dict.get('failure_code','')} "
            f"{diag_dict.get('failure_message','')}"
        )
    return binding_dict.get("logical_card_id", "")


def _seed_session_synthetic(registry, session_id: str) -> str:
    """Seed a minimal session without a real card (offline/demo).

    Uses a synthetic opening so the harness can run fully offline with fake
    profiles. Real-model runs should use --card-path + _seed_session_from_card.
    """
    from ..contracts.card_session_binding import CardSessionBinding
    from ..contracts.opening_record import OpeningRecord
    from ..contracts.worldbook_binding import WorldbookBinding
    now = _now()
    card_id = f"card_{_id('c', session_id)[:12]}"
    binding = CardSessionBinding(
        session_id=session_id, logical_card_id=card_id, card_version=1,
        source_hash="synthetic", selected_greeting_id="g0",
        opening_record_id=f"op_{session_id}",
        worldbook_binding_id=f"wb_{session_id}",
        status="ready", created_at=now,
    )
    registry.card_session_binding_store.save(binding)
    registry.opening_record_store.save(OpeningRecord(
        opening_record_id=f"op_{session_id}", session_id=session_id,
        logical_card_id=card_id, card_version=1, greeting_id="g0",
        safe_display_content="你来到一个陌生的村落，村口的老者向你点头致意。",
        created_at=now,
    ))
    registry.worldbook_binding_store.save(WorldbookBinding(
        worldbook_binding_id=f"wb_{session_id}", session_id=session_id,
        logical_card_id=card_id, card_version=1, source_hash="synthetic",
        created_at=now,
    ))
    registry.card_state_store.initialize(card_id, session_id)
    return card_id


def run_harness(
    *,
    card_path: str = "",
    turns: int = 10,
    director_profile_id: str = "fake-director",
    writer_profile_id: str = "fake-writer",
    player_profile_id: str = "fake-player",
    mode: str = "debug-full",
    restart_after_turn: int = 0,
    save_artifacts: bool = False,
    scenario: ScenarioSpec | None = None,
    artifact_root: str = "artifacts/long-session-runs",
) -> dict[str, Any]:
    """Run the long-session harness. Returns the final report dict."""

    real_run = _is_real_run(director_profile_id, writer_profile_id, player_profile_id)
    if real_run:
        _require_real_env()
        if not card_path or not Path(card_path).exists():
            print(f"REJECTED: real run requires --card-path pointing to an existing card: {card_path}")
            sys.exit(2)

    if scenario is None:
        scenario = load_scenario("demo_long_session_v1")

    run_id = _id("run", f"{_now()}:{card_path}:{turns}")
    session_id = _id("sess", run_id)
    store_root = os.environ.get("AWP_TEST_STORE_ROOT") or os.path.join(
        tempfile.gettempdir(), f"awp-longsession-{int(time.time())}"
    )
    os.makedirs(store_root, exist_ok=True)

    # Test profile + namespace so each run is isolated. Real runs ALSO use the
    # test profile namespace (the profile only controls store path, not model).
    os.environ["AWP_RUNTIME_PROFILE"] = os.environ.get("AWP_RUNTIME_PROFILE", "test")
    os.environ["AWP_TEST_STORE_ROOT"] = store_root
    os.environ["AWP_TEST_RUNTIME_NAMESPACE"] = run_id

    from ..runtime.runtime_store_factory import RuntimeStoreFactory, clear_registry_cache
    clear_registry_cache()

    artifact_dir: Path | None = None
    if save_artifacts:
        artifact_dir = Path(artifact_root) / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "scenario.json").write_text(
            json.dumps(scenario.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print("=" * 64)
    print(f"AWP RP Runtime V2 — Long-Session Harness ({'REAL' if real_run else 'FAKE'})")
    print("=" * 64)
    print(f"  run_id: {run_id}")
    print(f"  session_id: {session_id}")
    print(f"  turns: {turns}")
    print(f"  director: {director_profile_id}")
    print(f"  writer: {writer_profile_id}")
    print(f"  player: {player_profile_id}")
    print(f"  mode: {mode}")
    print(f"  restart_after_turn: {restart_after_turn}")
    print(f"  scenario: {scenario.scenario_id}")
    print("=" * 64)

    factory = RuntimeStoreFactory.from_env()
    registry = factory.registry

    # ── Bootstrap ────────────────────────────────────────────────────────
    if card_path:
        card_id = _seed_session_from_card(registry, session_id, card_path)
    else:
        card_id = _seed_session_synthetic(registry, session_id)
    print(f"  bootstrapped card_id: {card_id}")

    player_agent = SimulatedPlayerAgent(player_profile_id, mode=mode)
    observer = QualityObserver()

    turn_results: list[dict[str, Any]] = []
    own_history: list[str] = []
    previous_outputs: list[str] = []
    last_diag: dict[str, Any] = {}
    last_snapshot_dict: dict[str, Any] = {}
    restart_done = False
    total_provider_calls = 0
    real_director_calls = 0
    real_writer_calls = 0
    real_d6_commits = 0
    l2_or_l3_recalled = False

    aborted = False
    abort_reason = ""

    for turn_index in range(1, turns + 1):
        # ── Restart simulation ──────────────────────────────────────────
        if (restart_after_turn and turn_index == restart_after_turn + 1
                and not restart_done):
            print(f"\n--- Restart simulation after turn {restart_after_turn} ---")
            clear_registry_cache()
            factory = RuntimeStoreFactory.from_env()
            registry = factory.registry
            # Verify prior turns survived
            prior_recent = registry.turn_record_store.get_recent(card_id, session_id, limit=100)
            print(f"  restart: {len(prior_recent)} prior turn records survived")
            restart_done = True

        print(f"\n--- Turn {turn_index} ---")

        # ── Player simulator ────────────────────────────────────────────
        if turn_index == 1:
            player_input = scenario.initial_action or "你好，请带我看看这里。"
            psout = None
        else:
            psin = PlayerSimulatorInput(
                turn_index=turn_index,
                persona=scenario.player_persona,
                goal=scenario.global_goal,
                last_writer_output=previous_outputs[-1] if previous_outputs else "",
                own_history=list(own_history),
                planned_checkpoints=scenario.planned_checkpoints,
                required_facts=scenario.required_facts,
                debug_context=(build_debug_context(
                    registry, card_id, session_id, last_diag, last_snapshot_dict
                ) if mode == "debug-full" else {}),
            )
            psout = player_agent.run(psin)
            if not psout.success:
                print(f"  player simulator FAILED: {psout.failure_code} {psout.failure_message}")
                turn_results.append({
                    "turn_index": turn_index, "turn_id": "",
                    "status": "player_simulator_failed",
                    "player_simulator": {
                        "profile_id": player_profile_id, "mode": mode,
                        "failure_code": psout.failure_code,
                        "failure_message": psout.failure_message,
                    },
                })
                aborted = True
                abort_reason = f"player_simulator:{psout.failure_code}"
                break
            player_input = psout.player_input
            if real_run and player_agent.is_real:
                total_provider_calls += 1

        print(f"  player: {player_input[:80]}")
        own_history.append(player_input)

        # ── Execute turn via persistent node ────────────────────────────
        turn_id = _id("turn", f"{run_id}:t{turn_index}")
        request_id = _id("req", f"{run_id}:t{turn_index}")
        workflow_run_id = _id("wfr", f"{run_id}:t{turn_index}")
        trace_id = _id("trc", f"{run_id}:t{turn_index}")

        if turn_index == 1:
            from ..nodes.persistent_first_turn_node import AWPV2PersistentFirstTurn
            node = AWPV2PersistentFirstTurn()
            result = node.execute(
                session_id=session_id, player_input=player_input,
                turn_id=turn_id, request_id=request_id,
                workflow_run_id=workflow_run_id, trace_id=trace_id,
                director_profile_id=director_profile_id,
                writer_profile_id=writer_profile_id,
            )
        else:
            from ..nodes.persistent_continuation_turn_node import AWPV2PersistentContinuationTurn
            node = AWPV2PersistentContinuationTurn()
            result = node.execute(
                session_id=session_id, player_input=player_input,
                turn_id=turn_id, request_id=request_id,
                workflow_run_id=workflow_run_id, trace_id=trace_id,
                director_profile_id=director_profile_id,
                writer_profile_id=writer_profile_id,
            )

        receipt, ctx, diag = result[0], result[1], result[2]
        card_state_dict, turn_record_dict, snapshot_dict = result[3], result[4], result[5]
        last_diag = diag
        last_snapshot_dict = snapshot_dict if isinstance(snapshot_dict, dict) else {}

        if diag.get("outcome") != "success":
            print(f"  turn FAILED: {diag.get('failure_code','')} {diag.get('failure_message','')}")
            turn_results.append({
                "turn_index": turn_index, "turn_id": turn_id,
                "status": "failed",
                "failure_code": diag.get("failure_code", ""),
                "failure_message": diag.get("failure_message", ""),
                "diagnostics_summary": _summarize_diag(diag),
                "player_input": player_input,
                "player_simulator": _psout_dict(psout) if psout else None,
            })
            aborted = True
            abort_reason = f"turn:{diag.get('failure_code','failed')}"
            break

        writer_output = turn_record_dict.get("writer_output", "")
        previous_outputs.append(writer_output)

        # Track real-call evidence
        if diag.get("director_provider_type") != "fake" and diag.get("director_call_success"):
            real_director_calls += 1
            total_provider_calls += 1
        if diag.get("writer_provider_type") != "fake" and diag.get("writer_call_success"):
            real_writer_calls += 1
            total_provider_calls += 1
        if diag.get("memory_curation_status", "").startswith("curated"):
            real_d6_commits += 1
        if diag.get("l2_memory_ids_recalled") or diag.get("l3_memory_ids_recalled"):
            l2_or_l3_recalled = True

        # ── Quality observer (non-blocking) ─────────────────────────────
        qobs = observer.observe(
            turn_index=turn_index, turn_id=turn_id,
            player_input=player_input, writer_output=writer_output,
            diag=diag, previous_outputs=previous_outputs[:-1],
            scenario_required_facts=scenario.required_facts,
        )

        # ── Trace from store ────────────────────────────────────────────
        trace_summary: dict[str, Any] = {}
        try:
            tr = registry.trace_store.get_by_turn(turn_id)
            if tr:
                trace_summary = {
                    "trace_id": tr.trace_id,
                    "events": [
                        {"type": e.event_type, "success": e.success,
                         "duration_ms": e.duration_ms}
                        for e in tr.events
                    ],
                    "total_duration_ms": tr.total_duration_ms,
                }
        except Exception:
            pass

        turn_artifact = {
            "run_id": run_id,
            "session_id": session_id,
            "turn_id": turn_id,
            "turn_index": turn_index,
            "player_input": player_input,
            "player_intent": (psout.action_intent if psout else "initial"),
            "writer_output": writer_output,
            "receipt_summary": {
                "turn_id": receipt.get("turn_id", turn_id),
                "quality_verdict": receipt.get("quality_verdict", ""),
                "card_state_revision_before": receipt.get("base_card_state_revision", 0),
                "card_state_revision_after": receipt.get("result_card_state_revision", 0),
                "memory_curation_status": receipt.get("memory_curation_status", ""),
                "idempotency_status": receipt.get("idempotency_status", ""),
                "turn_record_id": receipt.get("turn_record_id", ""),
            },
            "diagnostics_summary": _summarize_diag(diag),
            "trace_id": trace_id,
            "trace_summary": trace_summary,
            "l1_turn_ids_recalled": diag.get("l1_turn_ids_recalled", []),
            "l2_memory_ids_recalled": diag.get("l2_memory_ids_recalled", []),
            "l3_memory_ids_recalled": diag.get("l3_memory_ids_recalled", []),
            "worldbook_entry_ids": diag.get("worldbook_entry_ids_activated", []),
            "card_state_revision_before": diag.get("card_state_revision_before", 0),
            "card_state_revision_after": diag.get("card_state_revision_after", 0),
            "memory_curation_status": diag.get("memory_curation_status", ""),
            "memory_commit_ids": diag.get("memory_commit_ids", []),
            "quality_observer": qobs.to_dict(),
            "player_simulator": _psout_dict(psout) if psout else {
                "profile_id": player_profile_id, "mode": mode,
                "latency_ms": 0, "source": "initial_action",
            },
        }
        turn_results.append(turn_artifact)

        if save_artifacts and artifact_dir:
            tf = artifact_dir / "turns" / f"turn-{turn_index:03d}.json"
            tf.parent.mkdir(parents=True, exist_ok=True)
            tf.write_text(
                json.dumps(turn_artifact, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        print(f"  writer: {writer_output[:80]}...")
        print(f"  rev {diag.get('card_state_revision_before',0)}→{diag.get('card_state_revision_after',0)}, "
              f"memory={diag.get('memory_curation_status','')}, "
              f"l1={len(diag.get('l1_turn_ids_recalled',[]))} "
              f"l2={len(diag.get('l2_memory_ids_recalled',[]))} "
              f"l3={len(diag.get('l3_memory_ids_recalled',[]))}")

    # ── Final report ─────────────────────────────────────────────────────
    success_count = sum(1 for t in turn_results if t.get("status") not in ("failed", "player_simulator_failed"))
    accepted_turn_records = len(registry.turn_record_store.get_recent(card_id, session_id, limit=200))
    traces_in_store = 0
    try:
        conn = registry.db.connect()
        row = conn.execute("SELECT COUNT(*) as c FROM execution_traces WHERE session_id=?", (session_id,)).fetchone()
        traces_in_store = row["c"] if row else 0
    except Exception:
        pass

    final_report = {
        "run_id": run_id,
        "session_id": session_id,
        "card_id": card_id,
        "card_path": card_path,
        "scenario_id": scenario.scenario_id,
        "real_run": real_run,
        "mode": mode,
        "profiles": {
            "director": director_profile_id,
            "writer": writer_profile_id,
            "player": player_profile_id,
        },
        "requested_turns": turns,
        "executed_turns": len(turn_results),
        "successful_turns": success_count,
        "accepted_turn_records": accepted_turn_records,
        "traces_in_store": traces_in_store,
        "total_provider_calls": total_provider_calls,
        "real_director_calls": real_director_calls,
        "real_writer_calls": real_writer_calls,
        "real_d6_commits": real_d6_commits,
        "l2_or_l3_recalled_at_least_once": l2_or_l3_recalled,
        "restart_simulated": restart_done,
        "restart_after_turn": restart_after_turn,
        "aborted": aborted,
        "abort_reason": abort_reason,
        "status": "pass" if (not aborted and success_count == turns
                             and accepted_turn_records == success_count) else "fail",
        "turn_results": turn_results,
        "generated_at": _now(),
    }

    if save_artifacts and artifact_dir:
        (artifact_dir / "run_manifest.json").write_text(
            json.dumps({k: v for k, v in final_report.items() if k != "turn_results"},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        (artifact_dir / "final_report.json").write_text(
            json.dumps(final_report, ensure_ascii=False, indent=2), encoding="utf-8")
        (artifact_dir / "final_report.md").write_text(
            _render_markdown(final_report), encoding="utf-8")
        print(f"\nArtifacts: {artifact_dir}")

    print("\n" + "=" * 64)
    print(f"STATUS: {final_report['status'].upper()}")
    print(f"turns executed: {final_report['executed_turns']}/{turns} "
          f"(success {success_count})")
    print(f"accepted TurnRecords: {accepted_turn_records}, traces: {traces_in_store}")
    print(f"real director calls: {real_director_calls}, writer: {real_writer_calls}, "
          f"d6 commits: {real_d6_commits}")
    print(f"l2/l3 recalled at least once: {l2_or_l3_recalled}")
    if aborted:
        print(f"ABORTED: {abort_reason}")
    print("=" * 64)

    return final_report


def _summarize_diag(diag: dict[str, Any]) -> dict[str, Any]:
    return {
        "outcome": diag.get("outcome", ""),
        "steps_completed": diag.get("steps_completed", []),
        "steps_failed": diag.get("steps_failed", []),
        "director_provider_type": diag.get("director_provider_type", ""),
        "writer_provider_type": diag.get("writer_provider_type", ""),
        "director_call_success": diag.get("director_call_success", False),
        "writer_call_success": diag.get("writer_call_success", False),
        "quality_verdict": diag.get("quality_verdict", ""),
        "card_state_commit_status": diag.get("card_state_commit_status", ""),
        "turn_record_commit_status": diag.get("turn_record_commit_status", ""),
        "memory_curation_status": diag.get("memory_curation_status", ""),
        "trace_persisted": diag.get("trace_persisted", False),
    }


def _psout_dict(psout) -> dict[str, Any]:
    return {
        "profile_id": psout.profile_id, "mode": "",
        "model": psout.model, "provider": psout.provider,
        "latency_ms": psout.latency_ms,
        "action_intent": psout.action_intent,
        "verify_tag": psout.verify_tag,
        "success": psout.success,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Long-Session Run Report — {report['run_id']}",
        "",
        f"- **Status**: {report['status']}",
        f"- **Real run**: {report['real_run']}",
        f"- **Session**: `{report['session_id']}`",
        f"- **Scenario**: `{report['scenario_id']}`",
        f"- **Turns**: {report['executed_turns']}/{report['requested_turns']} "
        f"(success {report['successful_turns']})",
        f"- **Accepted TurnRecords**: {report['accepted_turn_records']}",
        f"- **Traces in store**: {report['traces_in_store']}",
        f"- **Real Director calls**: {report['real_director_calls']}",
        f"- **Real Writer calls**: {report['real_writer_calls']}",
        f"- **D6 commits**: {report['real_d6_commits']}",
        f"- **L2/L3 recalled**: {report['l2_or_l3_recalled_at_least_once']}",
        f"- **Restart simulated**: {report['restart_simulated']} "
        f"(after turn {report['restart_after_turn']})",
        f"- **Aborted**: {report['aborted']} ({report['abort_reason']})",
        "",
        "## Per-turn summary",
        "",
        "| Turn | Status | Rev | Memory | L1/L2/L3 | Repetition | Notes |",
        "|------|--------|-----|--------|----------|------------|-------|",
    ]
    for t in report["turn_results"]:
        if t.get("status") in ("failed", "player_simulator_failed"):
            lines.append(f"| {t['turn_index']} | FAIL | - | - | - | - | {t.get('failure_code','')} |")
            continue
        qo = t.get("quality_observer", {})
        diag = t.get("diagnostics_summary", {})
        lines.append(
            f"| {t['turn_index']} | ok | {t['card_state_revision_before']}→{t['card_state_revision_after']} "
            f"| {t['memory_curation_status']} | "
            f"{len(t.get('l1_turn_ids_recalled',[]))}/{len(t.get('l2_memory_ids_recalled',[]))}/{len(t.get('l3_memory_ids_recalled',[]))} "
            f"| {qo.get('repetition_risk_score',0)} | {qo.get('short_rationale','')} |"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="AWP RP Runtime V2 long-session harness")
    parser.add_argument("--card-path", default="",
                        help="Path to card JSON. Required for real runs; optional for fake.")
    parser.add_argument("--turns", type=int, default=10)
    parser.add_argument("--director-profile-id", default="fake-director")
    parser.add_argument("--writer-profile-id", default="fake-writer")
    parser.add_argument("--player-profile-id", default="fake-player")
    parser.add_argument("--mode", choices=["visible", "debug-full"], default="debug-full")
    parser.add_argument("--restart-after-turn", type=int, default=0)
    parser.add_argument("--save-artifacts", action="store_true")
    parser.add_argument("--scenario", default="demo_long_session_v1",
                        help="Scenario name (in testing/scenarios/) or path.")
    parser.add_argument("--artifact-root", default="artifacts/long-session-runs")
    args = parser.parse_args()

    scenario = load_scenario(args.scenario)
    report = run_harness(
        card_path=args.card_path,
        turns=args.turns,
        director_profile_id=args.director_profile_id,
        writer_profile_id=args.writer_profile_id,
        player_profile_id=args.player_profile_id,
        mode=args.mode,
        restart_after_turn=args.restart_after_turn,
        save_artifacts=args.save_artifacts,
        scenario=scenario,
        artifact_root=args.artifact_root,
    )
    sys.exit(0 if report["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
