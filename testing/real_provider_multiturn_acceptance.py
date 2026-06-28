r"""Real Provider Persistent Multi-Turn Acceptance.

This is the CANONICAL real-model acceptance path. It drives real DeepSeek
Director + Writer through the persistent nodes:

    AWPV2PersistentBootstrap
    AWPV2PersistentFirstTurn
    AWPV2PersistentContinuationTurn

It does NOT hand-build Director/Writer prompts, does NOT call the provider
directly, and does NOT hand-write CardState/TurnRecord. All persistence and
all provider calls go through the persistent node chain + the shared
PersistentTurnEngine, which records trace + D6 evidence per turn.

Usage (real model):
  $env:AWP_REAL_LLM_E2E = "1"
  $env:DEEPSEEK_API_KEY = "..."
  $env:AWP_ALLOW_EXTERNAL_CARD_CONTENT = "1"
  python -m awp_rp_runtime_v2.testing.real_provider_multiturn_acceptance \
      --card-path "<card.json>" --turns 10 \
      --director-profile-id deepseek-v4-pro-director \
      --writer-profile-id deepseek-v4-flash-writer \
      --restart-after-turn 5

A legacy direct-provider smoke test is retained as
real_provider_direct_smoke (renamed) — it is NOT the persistent playable
acceptance path and is clearly labeled as a provider-only smoke test.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .user_simulation_harness import (
    run_harness, load_scenario, ScenarioSpec,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_persistent_multiturn_acceptance(
    card_path: str,
    turns: int = 10,
    director_profile_id: str = "deepseek-v4-pro-director",
    writer_profile_id: str = "deepseek-v4-flash-writer",
    player_profile_id: str = "simulated-player-v1",
    mode: str = "debug-full",
    restart_after_turn: int = 5,
    save_artifacts: bool = True,
    scenario_name: str = "demo_long_session_v1",
    artifact_root: str = "artifacts/long-session-runs",
) -> dict[str, Any]:
    """Run the canonical persistent real-model multi-turn acceptance.

    Delegates to the user_simulation_harness with real profiles, which enforces
    the AWP_REAL_LLM_E2E double-opt-in guard and drives the persistent nodes.
    """
    scenario = load_scenario(scenario_name)
    return run_harness(
        card_path=card_path,
        turns=turns,
        director_profile_id=director_profile_id,
        writer_profile_id=writer_profile_id,
        player_profile_id=player_profile_id,
        mode=mode,
        restart_after_turn=restart_after_turn,
        save_artifacts=save_artifacts,
        scenario=scenario,
        artifact_root=artifact_root,
    )


# ── Legacy direct-provider smoke test (NOT the persistent path) ──────────────

def run_direct_provider_smoke(
    card_path: str,
    turns: int = 3,
) -> dict[str, Any]:
    """DIRECT-PROVIDER SMOKE TEST ONLY.

    This is a provider connectivity smoke test that calls DeepSeek directly
    (Director + Writer) WITHOUT the persistent node chain. It exists only to
    verify provider reachability. It is NOT the persistent playable
    acceptance path — do not treat its pass as evidence that the persistent
    node chain works. Use run_persistent_multiturn_acceptance for that.
    """
    if os.environ.get("AWP_REAL_LLM_E2E") != "1":
        print("REJECTED (direct smoke): AWP_REAL_LLM_E2E is not '1'.")
        sys.exit(2)
    if not os.environ.get("DEEPSEEK_API_KEY", ""):
        print("REJECTED (direct smoke): DEEPSEEK_API_KEY is not set.")
        sys.exit(2)
    if not Path(card_path).exists():
        print(f"REJECTED (direct smoke): card not found: {card_path}")
        sys.exit(2)

    from ..adapters.llm.deepseek_adapter import DeepSeekAdapter
    director_model = os.environ.get("AWP_DIRECTOR_MODEL", "deepseek-v4-pro")
    writer_model = os.environ.get("AWP_WRITER_MODEL", "deepseek-v4-flash")

    print("=" * 60)
    print("DIRECT-PROVIDER SMOKE TEST (not persistent acceptance)")
    print("=" * 60)
    print(f"  card: {card_path}")
    print(f"  director: {director_model}, writer: {writer_model}, turns: {turns}")
    print("=" * 60)

    adapter = DeepSeekAdapter(model=writer_model, timeout_seconds=120, max_retries=2)
    results = []
    for i in range(1, turns + 1):
        prompt = f"Say a single short greeting line in Chinese (turn {i})."
        text, receipt = adapter.generate_text(
            prompt, provider_role="writer_smoke",
            turn_id=f"smoke_t{i}", attempt_id=f"smoke_a{i}",
        )
        ok = receipt.success and bool(text.strip())
        results.append({"turn": i, "success": ok,
                        "text_length": len(text)})
        print(f"  turn {i}: {'OK' if ok else 'FAIL'} ({len(text)} chars)")
        time.sleep(1)

    all_ok = all(r["success"] for r in results)
    report = {
        "kind": "direct_provider_smoke",
        "status": "pass" if all_ok else "fail",
        "turns": results,
        "note": "Provider connectivity smoke test ONLY. Not persistent acceptance.",
    }
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Real Provider Persistent Multi-Turn Acceptance"
    )
    parser.add_argument("--card-path", required=True)
    parser.add_argument("--turns", type=int, default=10)
    parser.add_argument("--director-profile-id", default="deepseek-v4-pro-director")
    parser.add_argument("--writer-profile-id", default="deepseek-v4-flash-writer")
    parser.add_argument("--player-profile-id", default="simulated-player-v1")
    parser.add_argument("--mode", choices=["visible", "debug-full"], default="debug-full")
    parser.add_argument("--restart-after-turn", type=int, default=5)
    parser.add_argument("--save-artifacts", action="store_true", default=True)
    parser.add_argument("--scenario", default="demo_long_session_v1")
    parser.add_argument("--artifact-root", default="artifacts/long-session-runs")
    parser.add_argument("--direct-smoke", action="store_true",
                        help="Run the legacy direct-provider smoke test instead "
                             "of the persistent acceptance path.")
    args = parser.parse_args()

    if args.direct_smoke:
        report = run_direct_provider_smoke(args.card_path, turns=args.turns)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(0 if report["status"] == "pass" else 1)

    report = run_persistent_multiturn_acceptance(
        card_path=args.card_path,
        turns=args.turns,
        director_profile_id=args.director_profile_id,
        writer_profile_id=args.writer_profile_id,
        player_profile_id=args.player_profile_id,
        mode=args.mode,
        restart_after_turn=args.restart_after_turn,
        save_artifacts=args.save_artifacts,
        scenario_name=args.scenario,
        artifact_root=args.artifact_root,
    )
    sys.exit(0 if report["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
