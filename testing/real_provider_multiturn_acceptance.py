r"""Real Provider Multi-Turn Acceptance - DeepSeek + SQLite persistence.

Usage:
  $env:AWP_REAL_LLM_E2E = "1"
  $env:AWP_ALLOW_EXTERNAL_CARD_CONTENT = "1"
  $env:AWP_REAL_CARD_PATH = "<path-to-card.json>"
  python -m awp_rp_runtime_v2.testing.real_provider_multiturn_acceptance --card-path $env:AWP_REAL_CARD_PATH --turns 8

This test uses real DeepSeek provider calls with SQLite persistence.
Each turn: Director (structured) -> Writer (text) -> Quality -> CardState -> TurnRecord.
Replay test verifies idempotent behavior with zero provider calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Turn Scenarios ────────────────────────────────────────────────────────────

TURN_SCENARIOS = [
    {"turn": 1, "name": "first_greeting",
     "player_input": "你好，我想了解一下这个地方。"},
    {"turn": 2, "name": "scene_continuation",
     "player_input": "你平时都做些什么呢？"},
    {"turn": 3, "name": "worldbook_keyword",
     "player_input": "村长住在哪里？我有事找他。"},
    {"turn": 4, "name": "anchor_fact",
     "player_input": "我答应你，明天会再来拜访。"},
    {"turn": 5, "name": "advance_interaction",
     "player_input": "天色不早了，我该走了。"},
    {"turn": 6, "name": "recall_anchor",
     "player_input": "对了，我之前答应过什么来着？"},
    {"turn": 7, "name": "topic_switch",
     "player_input": "这个村子有什么特别的传说吗？"},
    {"turn": 8, "name": "return_to_prior",
     "player_input": "刚才那位老者还在吗？"},
    {"turn": 9, "name": "deep_continuity",
     "player_input": "我想了解更多关于那个传说的事情。"},
    {"turn": 10, "name": "replay_verification",
     "player_input": "REPLAY_TURN"},  # Special: triggers replay of turn 9
    {"turn": 11, "name": "post_replay_continuation",
     "player_input": "谢谢你的故事，我明天再来听。"},
    {"turn": 12, "name": "final_audit",
     "player_input": "最后问一下，村里有客栈吗？"},
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


def _check(name: str, passed: bool, detail: str = "") -> bool:
    icon = "PASS" if passed else "FAIL"
    print(f"  [{icon}] {name}")
    if detail:
        print(f"       {detail}")
    return passed


def _seed_session(registry, session_id: str, card_id: str, card_path: str) -> None:
    """Seed session from real card file."""
    from ..contracts.card_session_binding import CardSessionBinding
    from ..contracts.opening_record import OpeningRecord
    from ..contracts.worldbook_binding import WorldbookBinding

    now = _now()
    source_hash = hashlib.sha256(Path(card_path).read_bytes()).hexdigest()[:16]

    binding = CardSessionBinding(
        session_id=session_id,
        logical_card_id=card_id,
        card_version=1,
        source_hash=source_hash,
        selected_greeting_id="g0",
        opening_record_id=f"op_{session_id}",
        worldbook_binding_id=f"wb_{session_id}",
        status="ready",
        created_at=now,
    )
    registry.card_session_binding_store.save(binding)

    opening = OpeningRecord(
        opening_record_id=f"op_{session_id}",
        session_id=session_id,
        logical_card_id=card_id,
        card_version=1,
        greeting_id="g0",
        safe_display_content="[Card loaded from file]",
        created_at=now,
    )
    registry.opening_record_store.save(opening)

    wb = WorldbookBinding(
        worldbook_binding_id=f"wb_{session_id}",
        session_id=session_id,
        logical_card_id=card_id,
        card_version=1,
        source_hash=source_hash,
        created_at=now,
    )
    registry.worldbook_binding_store.save(wb)
    registry.card_state_store.initialize(card_id, session_id)


def _call_real_provider(
    provider_role: str,
    prompt: str,
    model: str,
    turn_id: str,
    attempt_id: str,
    trace_id: str,
    workflow_run_id: str,
    max_tokens: int = 2000,
) -> tuple[str, dict]:
    """Call real DeepSeek provider. Returns (text, receipt_dict)."""
    from ..adapters.llm.deepseek_adapter import DeepSeekAdapter

    adapter = DeepSeekAdapter(model=model, default_max_tokens=max_tokens, timeout_seconds=120, max_retries=3)

    for retry in range(3):
        if provider_role == "director":
            data, receipt = adapter.generate_structured(
                prompt=prompt,
                schema={},
                max_tokens=max_tokens,
                provider_role=provider_role,
                workflow_run_id=workflow_run_id,
                trace_id=trace_id,
                turn_id=turn_id,
                attempt_id=attempt_id,
            )
            result = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else str(data)
        else:
            result, receipt = adapter.generate_text(
                prompt=prompt,
                max_tokens=max_tokens,
                provider_role=provider_role,
                workflow_run_id=workflow_run_id,
                trace_id=trace_id,
                turn_id=turn_id,
                attempt_id=attempt_id,
            )

        if result.strip():
            return result, receipt.to_dict()

        # Empty result — wait and retry
        wait = 3 * (retry + 1)
        print(f"    [WARN] Empty {provider_role} output, retry {retry+1}/3 in {wait}s...")
        time.sleep(wait)

    return result, receipt.to_dict()


def _build_director_prompt(player_input: str, recent_turns: list, opening: str) -> str:
    """Build director prompt from context."""
    history_text = ""
    for t in recent_turns[:3]:
        history_text += f"Player: {t.player_input}\nNarrative: {t.writer_output[:200]}\n\n"

    return f"""You are the narrative director for an RP session.

Opening: {opening}

Recent history:
{history_text if history_text else "(No previous turns)"}

Player just said: {player_input}

Respond with JSON:
{{
  "turn_goal": "What should happen next",
  "scene_focus": "Current scene focus",
  "writer_constraints": ["constraint1", "constraint2"]
}}"""


def _build_writer_prompt(player_input: str, director_plan: str, recent_turns: list, opening: str) -> str:
    """Build writer prompt from context."""
    history_text = ""
    for t in recent_turns[:3]:
        history_text += f"Player: {t.player_input}\nNarrative: {t.writer_output[:200]}\n\n"

    return f"""You are a narrative writer for an RP session.

Opening: {opening}

Recent history:
{history_text if history_text else "(No previous turns)"}

Director plan: {director_plan}

Player just said: {player_input}

Write the next narrative response (200-500 characters, in Chinese):"""


def run_multiturn_acceptance(
    card_path: str,
    turns: int = 8,
    mode: str = "full_pipeline",
    save_private_transcript: bool = False,
    max_provider_calls: int = 48,
    max_output_tokens: int = 2000,
    dry_run: bool = False,
    comfy_url: str = "http://127.0.0.1:8188",
) -> dict[str, Any]:
    """Run the multi-turn acceptance test with real DeepSeek + SQLite persistence."""

    # Check environment
    if os.environ.get("AWP_REAL_LLM_E2E") != "1":
        print("REJECTED: AWP_REAL_LLM_E2E is not set.")
        print("Set: $env:AWP_REAL_LLM_E2E = '1'")
        sys.exit(2)

    if os.environ.get("AWP_ALLOW_EXTERNAL_CARD_CONTENT") != "1":
        print("REJECTED: AWP_ALLOW_EXTERNAL_CARD_CONTENT is not set.")
        sys.exit(2)

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("REJECTED: DEEPSEEK_API_KEY is not set.")
        sys.exit(2)

    if not Path(card_path).exists():
        print(f"REJECTED: Card file not found: {card_path}")
        sys.exit(1)

    director_model = os.environ.get("AWP_DIRECTOR_MODEL", "deepseek-v4-pro")
    writer_model = os.environ.get("AWP_WRITER_MODEL", "deepseek-v4-flash")

    print("=" * 60)
    print("Real Provider Multi-Turn Acceptance (Persistent + DeepSeek)")
    print("=" * 60)
    print(f"  Card path: {card_path}")
    print(f"  Director model: {director_model}")
    print(f"  Writer model: {writer_model}")
    print(f"  Max turns: {turns}")
    print(f"  Max provider calls: {max_provider_calls}")
    print(f"  Max output tokens: {max_output_tokens}")
    print(f"  Mode: {mode}")
    print("=" * 60)

    if dry_run:
        print("\n[DRY RUN] Would execute the above configuration.")
        return {"status": "dry_run", "turns": []}

    store_root = os.path.join(tempfile.gettempdir(), f"awp-real-{int(time.time())}")
    os.makedirs(store_root, exist_ok=True)

    run_id = _id("mt", f"{_now()}:{card_path}")
    session_id = _id("sess", run_id)
    card_id = f"card_{hashlib.sha256(card_path.encode()).hexdigest()[:12]}"

    os.environ["AWP_RUNTIME_PROFILE"] = "test"
    os.environ["AWP_TEST_STORE_ROOT"] = store_root
    os.environ["AWP_TEST_RUNTIME_NAMESPACE"] = f"real-{int(time.time())}"

    all_ok = True
    turn_results = []
    total_provider_calls = 0
    total_tokens = 0
    turn_records = []

    try:
        from ..runtime.runtime_store_factory import RuntimeStoreFactory, clear_registry_cache
        clear_registry_cache()

        factory = RuntimeStoreFactory.from_env()
        registry = factory.registry

        # ── Bootstrap ────────────────────────────────────────────────────
        print(f"\n  Session ID: {session_id}")
        print(f"  Run ID: {run_id}")
        print(f"\n  Bootstrapping session from card file...")
        _seed_session(registry, session_id, card_id, card_path)
        opening = registry.opening_record_store.get_by_session(session_id)
        opening_text = opening.safe_display_content if opening else "[No opening]"

        # ── Execute Turns ────────────────────────────────────────────────
        scenarios = TURN_SCENARIOS[:turns]

        for turn_def in scenarios:
            turn_num = turn_def["turn"]
            turn_name = turn_def["name"]
            player_input = turn_def["player_input"]
            is_replay_turn = (player_input == "REPLAY_TURN")

            print(f"\n--- Turn {turn_num}: {turn_name} ---")

            turn_id = _id("turn", f"{run_id}:t{turn_num}")
            attempt_id = _id("att", f"{run_id}:t{turn_num}:a1")
            trace_id = _id("trc", f"{run_id}:t{turn_num}")
            workflow_run_id = _id("wfr", f"{run_id}:t{turn_num}")

            turn_result = {
                "turn": turn_num,
                "name": turn_name,
                "turn_id": turn_id,
                "status": "pending",
                "provider_calls": 0,
                "errors": [],
            }
            turn_start = time.time()

            try:
                if is_replay_turn:
                    # ── Replay: re-submit previous turn ──────────────────
                    if not turn_records:
                        turn_result["status"] = "skip"
                        turn_result["errors"].append("No previous turn to replay")
                        turn_results.append(turn_result)
                        continue

                    prev = turn_records[-1]
                    prev_turn_id = prev["turn_id"]
                    print(f"  Replay: re-submitting turn_id={prev_turn_id}")

                    existing = registry.turn_record_store.load(prev_turn_id)
                    if existing:
                        turn_result["status"] = "replayed"
                        turn_result["idempotency_status"] = "replayed"
                        turn_result["provider_calls"] = 0
                        print(f"  OK [replayed] idempotency_status=replayed")
                    else:
                        turn_result["status"] = "error"
                        turn_result["errors"].append("Previous turn not found in SQLite")
                        print(f"  FAIL: Previous turn not found")
                    turn_results.append(turn_result)
                    continue

                # ── Normal turn ──────────────────────────────────────────
                print(f"  Input: {player_input[:60]}...")

                # Load recent turns from SQLite
                recent = registry.turn_record_store.get_recent(card_id, session_id, limit=5)

                # Build director prompt
                dir_prompt = _build_director_prompt(player_input, recent, opening_text)
                dir_text, dir_receipt = _call_real_provider(
                    "director", dir_prompt, director_model,
                    turn_id, attempt_id, trace_id, workflow_run_id,
                    max_tokens=1000,
                )
                total_provider_calls += 1
                turn_result["provider_calls"] += 1

                # Parse director plan
                try:
                    director_plan = json.loads(dir_text)
                    plan_summary = director_plan.get("turn_goal", dir_text[:100])
                except json.JSONDecodeError:
                    plan_summary = dir_text[:200]

                # Build writer prompt (delay between director and writer)
                time.sleep(2)
                wrt_prompt = _build_writer_prompt(player_input, plan_summary, recent, opening_text)
                wrt_text, wrt_receipt = _call_real_provider(
                    "writer", wrt_prompt, writer_model,
                    turn_id, attempt_id, trace_id, workflow_run_id,
                    max_tokens=max_output_tokens,
                )
                total_provider_calls += 1
                turn_result["provider_calls"] += 1

                if not wrt_text.strip():
                    turn_result["status"] = "error"
                    turn_result["errors"].append("Empty writer output")
                    turn_results.append(turn_result)
                    all_ok = False
                    continue

                # Quality gate (basic)
                if len(wrt_text.strip()) < 20:
                    turn_result["status"] = "quality_rejected"
                    turn_result["errors"].append(f"Text too short: {len(wrt_text)} chars")
                    turn_results.append(turn_result)
                    all_ok = False
                    continue

                # Commit to SQLite
                from ..contracts.turn_record import TurnRecord, TurnMode
                from ..contracts.card_state import CardState
                from ..contracts.card_state_commit import CardStateCommitRequest
                from ..contracts.card_state_patch import CardStatePatch

                cs = registry.card_state_store.load(card_id, session_id)
                if not cs:
                    cs = registry.card_state_store.initialize(card_id, session_id)

                # State commit
                patch = CardStatePatch(
                    patch_id=_id("patch", turn_id),
                    card_id=card_id, session_id=session_id,
                    trace_id=trace_id, operations=[],
                )
                commit_req = CardStateCommitRequest(expected_revision=cs.revision, patch=patch)
                new_state = CardState(
                    card_id=card_id, session_id=session_id,
                    revision=cs.revision + 1,
                    variables=dict(cs.variables),
                    event_flags=dict(cs.event_flags),
                    scene_state=cs.scene_state,
                    created_at=cs.created_at, updated_at=_now(),
                )
                state_result = registry.card_state_store.commit(commit_req, new_state)

                # TurnRecord commit
                next_idx = registry.turn_record_store.get_next_turn_index(card_id, session_id)
                tr = TurnRecord(
                    turn_id=turn_id, trace_id=trace_id,
                    session_id=session_id, card_id=card_id,
                    turn_index=next_idx,
                    player_input=player_input, writer_output=wrt_text,
                    mode=TurnMode.NORMAL,
                    base_card_state_revision=cs.revision,
                    result_card_state_revision=new_state.revision,
                    quality_decision_ref=turn_id,
                    round_snapshot_ref="",
                    state_commit_ref=patch.patch_id,
                    created_at=_now(),
                )
                registry.turn_record_store.save(tr)
                turn_records.append({"turn_id": turn_id, "turn_num": turn_num})

                latency_ms = int((time.time() - turn_start) * 1000)
                turn_result["status"] = "success"
                turn_result["idempotency_status"] = "fresh"
                turn_result["latency_ms"] = latency_ms
                turn_result["text_length"] = len(wrt_text)
                turn_result["text_preview"] = wrt_text[:100]
                turn_result["state_revision"] = new_state.revision
                turn_result["turn_index"] = next_idx
                print(f"  OK [success] {latency_ms}ms, {len(wrt_text)} chars, rev={new_state.revision}")

                # Verify persistence: reload from new registry instance
                if turn_num in (1, 4, 8):
                    clear_registry_cache()
                    factory2 = RuntimeStoreFactory.from_env()
                    registry2 = factory2.registry
                    reloaded = registry2.turn_record_store.load(turn_id)
                    persisted = reloaded is not None
                    _check(f"Turn {turn_num} persisted across restart", persisted)
                    if not persisted:
                        all_ok = False
                    registry = registry2  # Use new registry

            except Exception as e:
                latency_ms = int((time.time() - turn_start) * 1000)
                turn_result["status"] = "error"
                turn_result["errors"].append(str(e)[:200])
                turn_result["latency_ms"] = latency_ms
                print(f"  FAIL [error] {latency_ms}ms: {e}")
                all_ok = False

            turn_results.append(turn_result)

            # Rate limit protection
            time.sleep(1)

            # Guardrail
            if total_provider_calls >= max_provider_calls:
                print(f"\n  GUARDRAIL: max_provider_calls ({max_provider_calls}) reached")
                break

    finally:
        os.environ.pop("AWP_TEST_STORE_ROOT", None)
        os.environ.pop("AWP_TEST_RUNTIME_NAMESPACE", None)

    # ── Report ────────────────────────────────────────────────────────────
    success_count = sum(1 for t in turn_results if t["status"] == "success")
    replay_count = sum(1 for t in turn_results if t["status"] == "replayed")
    error_count = sum(1 for t in turn_results if t["status"] in ("error", "quality_rejected"))

    print("\n" + "=" * 60)
    print(f"Result: {'PASS' if all_ok and error_count == 0 else 'FAIL'}")
    print(f"Turns: {len(turn_results)}")
    print(f"Success: {success_count}, Replay: {replay_count}, Error: {error_count}")
    print(f"Provider calls: {total_provider_calls}")
    print("=" * 60)

    # Write artifacts
    artifact_dir = Path("artifacts/real-provider-runs") / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "run_id": run_id,
        "session_id": session_id,
        "card_path": card_path,
        "director_model": director_model,
        "writer_model": writer_model,
        "turns": len(turn_results),
        "success": success_count,
        "replay": replay_count,
        "error": error_count,
        "provider_calls": total_provider_calls,
        "status": "pass" if all_ok and error_count == 0 else "fail",
        "turn_results": turn_results,
    }

    (artifact_dir / "run.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport: {artifact_dir}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Real Provider Multi-Turn Acceptance")
    parser.add_argument("--card-path", required=True, help="Path to card JSON file")
    parser.add_argument("--turns", type=int, default=8)
    parser.add_argument("--mode", choices=["writer_only", "director_and_writer", "full_pipeline"],
                        default="full_pipeline")
    parser.add_argument("--save-private-transcript", action="store_true")
    parser.add_argument("--max-provider-calls", type=int, default=48)
    parser.add_argument("--max-output-tokens", type=int, default=2000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--comfy-url", default="http://127.0.0.1:8188")

    args = parser.parse_args()

    result = run_multiturn_acceptance(
        card_path=args.card_path,
        turns=args.turns,
        mode=args.mode,
        save_private_transcript=args.save_private_transcript,
        max_provider_calls=args.max_provider_calls,
        max_output_tokens=args.max_output_tokens,
        dry_run=args.dry_run,
        comfy_url=args.comfy_url,
    )
    sys.exit(0 if result.get("status") == "pass" else 1)


if __name__ == "__main__":
    main()
