"""Playable E2E Test -- runs full RP session via ComfyUI API.

Usage:
  python -m awp_rp_runtime_v2.testing.playable_e2e_test --turns 8

Requires:
  - ComfyUI running at http://127.0.0.1:8188
  - AWP_RUNTIME_PROFILE=test
  - AWP_TEST_RUNTIME_NAMESPACE set (auto-generated if not)
  - For real provider: DEEPSEEK_API_KEY, AWP_DIRECTOR_PROFILE_ID, AWP_WRITER_PROFILE_ID
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any


COMFY_URL = "http://127.0.0.1:8188"


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


def _check(name: str, passed: bool, detail: str = "") -> bool:
    icon = "PASS" if passed else "FAIL"
    print(f"  [{icon}] {name}")
    if detail:
        print(f"       {detail}")
    return passed


def _submit_and_wait(workflow: dict, url: str = COMFY_URL, timeout: int = 120) -> dict:
    """Submit workflow to ComfyUI and wait for completion."""
    import uuid
    payload = json.dumps({
        "prompt": workflow,
        "client_id": f"play-{uuid.uuid4().hex[:8]}"
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/prompt", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    prompt_id = result.get("prompt_id", "")

    # Wait for completion
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(f"{url}/history/{prompt_id}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                history = json.loads(resp.read().decode("utf-8"))
                if prompt_id in history:
                    return history[prompt_id]
        except Exception:
            pass
        time.sleep(2)

    raise TimeoutError(f"Prompt {prompt_id} did not complete in {timeout}s")


def _extract_probe(history_entry: dict) -> dict | None:
    """Extract TurnResultProbe projection from history entry."""
    outputs = history_entry.get("outputs", {})
    for node_id, node_output in outputs.items():
        if not isinstance(node_output, dict):
            continue
        ui = node_output.get("ui", {})
        if isinstance(ui, dict) and "awp_turn_result_json" in ui:
            texts = ui["awp_turn_result_json"]
            if isinstance(texts, list) and texts:
                try:
                    return json.loads(texts[0])
                except json.JSONDecodeError:
                    pass
    return None


def _extract_text(history_entry: dict) -> str:
    """Extract writer output text from history entry."""
    outputs = history_entry.get("outputs", {})
    best = ""
    for node_id, node_output in outputs.items():
        if not isinstance(node_output, dict):
            continue
        # TraceDisplay ui.text
        ui = node_output.get("ui", {})
        if isinstance(ui, dict) and "text" in ui:
            for t in (ui["text"] if isinstance(ui["text"], list) else []):
                if isinstance(t, str) and len(t) > len(best):
                    best = t
    return best


PLAYER_INPUTS = [
    "你好，我想了解一下这个地方。",
    "你平时都做些什么呢？",
    "村长住在哪里？我有事找他。",
    "我答应你，明天会再来拜访。",
    "天色不早了，我该走了。",
    "对了，我之前答应过什么来着？",
    "这个村子有什么特别的传说吗？",
    "刚才那位老者还在吗？",
]


def run_playable_e2e(
    turns: int = 8,
    director_profile: str = "fake-director",
    writer_profile: str = "fake-writer",
    comfy_url: str = COMFY_URL,
) -> bool:
    """Run full playable E2E test via ComfyUI API."""

    print("=" * 60)
    print("AWP RP Runtime V2 -- Playable E2E Test")
    print("=" * 60)
    print(f"  ComfyUI URL: {comfy_url}")
    print(f"  Turns: {turns}")
    print(f"  Director profile: {director_profile}")
    print(f"  Writer profile: {writer_profile}")
    print("=" * 60)

    # Check ComfyUI
    try:
        req = urllib.request.Request(f"{comfy_url}/system_stats")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
    except Exception:
        print("ERROR: ComfyUI not available")
        return False

    # Check nodes
    req = urllib.request.Request(f"{comfy_url}/object_info")
    with urllib.request.urlopen(req, timeout=10) as resp:
        obj_info = json.loads(resp.read().decode("utf-8"))

    required = ["AWPV2PersistentBootstrap", "AWPV2PersistentFirstTurn",
                 "AWPV2PersistentContinuationTurn", "AWPV2TurnResultProbe"]
    missing = [n for n in required if n not in obj_info]
    if missing:
        print(f"ERROR: Missing nodes: {missing}")
        return False
    _check("All required nodes available", True, f"{len(required)} nodes")

    session_id = f"play-sess-{int(time.time() * 1000)}"
    all_ok = True

    # ── Phase 1: Bootstrap ──────────────────────────────────────────────
    print(f"\n1. Bootstrap (session={session_id})...")
    card_path = str(Path(__file__).parent.parent / "test_fixtures" / "test_card_v3_with_worldbook.json")

    bootstrap_wf = {
        "1": {
            "class_type": "AWPV2PersistentBootstrap",
            "inputs": {
                "source_path": card_path,
                "session_id": session_id,
                "greeting_id": "g0",
                "request_id": f"req-bs-{int(time.time())}",
                "run_id": f"run-{int(time.time())}",
            }
        }
    }

    try:
        entry = _submit_and_wait(bootstrap_wf, comfy_url, timeout=30)
        status = entry.get("status", {}).get("status_str", "unknown")
        all_ok = _check("Bootstrap completed", status == "success", f"status={status}") and all_ok
    except Exception as e:
        all_ok = _check("Bootstrap completed", False, str(e)[:100]) and all_ok
        return False

    # ── Phase 2: First Turn ─────────────────────────────────────────────
    print(f"\n2. First Turn...")
    turn1_id = f"turn-1-{int(time.time())}"
    player_input = PLAYER_INPUTS[0]

    firstturn_wf = {
        "1": {
            "class_type": "AWPV2PersistentFirstTurn",
            "inputs": {
                "session_id": session_id,
                "player_input": player_input,
                "turn_id": turn1_id,
                "request_id": f"req-{turn1_id}",
                "workflow_run_id": f"wfr-{turn1_id}",
                "trace_id": f"trc-{turn1_id}",
                "director_profile_id": director_profile,
                "writer_profile_id": writer_profile,
            }
        },
        "2": {
            "class_type": "AWPV2TurnResultProbe",
            "inputs": {
                "receipt": ["1", 0],
                "diagnostics": ["1", 2],
                "turn_record": ["1", 4],
                "turn_kind": "first",
            }
        }
    }

    try:
        entry = _submit_and_wait(firstturn_wf, comfy_url, timeout=120)
        status = entry.get("status", {}).get("status_str", "unknown")
        all_ok = _check("Turn 1 completed", status == "success", f"status={status}") and all_ok

        probe = _extract_probe(entry)
        if probe:
            idem = probe.get("idempotency_status", "")
            all_ok = _check("Turn 1 idempotency_status=fresh", idem == "fresh",
                            f"got '{idem}'") and all_ok
            print(f"       Turn 1: rev_before={probe.get('card_state_revision_before')}, "
                  f"rev_after={probe.get('card_state_revision_after')}, "
                  f"text_len={probe.get('accepted_text_length')}")
    except Exception as e:
        all_ok = _check("Turn 1 completed", False, str(e)[:100]) and all_ok

    # ── Phase 3: Continuation Turns ─────────────────────────────────────
    turn_ids = [turn1_id]
    for turn_num in range(2, turns + 1):
        print(f"\n{turn_num + 1}. Turn {turn_num}...")
        turn_id = f"turn-{turn_num}-{int(time.time())}"
        player_input = PLAYER_INPUTS[(turn_num - 1) % len(PLAYER_INPUTS)]

        cont_wf = {
            "1": {
                "class_type": "AWPV2PersistentContinuationTurn",
                "inputs": {
                    "session_id": session_id,
                    "player_input": player_input,
                    "turn_id": turn_id,
                    "request_id": f"req-{turn_id}",
                    "workflow_run_id": f"wfr-{turn_id}",
                    "trace_id": f"trc-{turn_id}",
                    "director_profile_id": director_profile,
                    "writer_profile_id": writer_profile,
                }
            },
            "2": {
                "class_type": "AWPV2TurnResultProbe",
                "inputs": {
                    "receipt": ["1", 0],
                    "diagnostics": ["1", 2],
                    "turn_record": ["1", 4],
                    "turn_kind": "continuation",
                }
            }
        }

        try:
            entry = _submit_and_wait(cont_wf, comfy_url, timeout=120)
            status = entry.get("status", {}).get("status_str", "unknown")
            ok = status == "success"
            all_ok = _check(f"Turn {turn_num} completed", ok, f"status={status}") and all_ok

            probe = _extract_probe(entry)
            if probe:
                idem = probe.get("idempotency_status", "")
                all_ok = _check(f"Turn {turn_num} idempotency_status=fresh", idem == "fresh",
                                f"got '{idem}'") and all_ok
                print(f"       Turn {turn_num}: rev_before={probe.get('card_state_revision_before')}, "
                      f"rev_after={probe.get('card_state_revision_after')}, "
                      f"text_len={probe.get('accepted_text_length')}")

                # Verify L1 contains previous turns
                turn_idx = probe.get("turn_index", 0)
                all_ok = _check(f"Turn {turn_num} turn_index={turn_num}",
                                turn_idx == turn_num,
                                f"got {turn_idx}") and all_ok

            turn_ids.append(turn_id)
        except Exception as e:
            all_ok = _check(f"Turn {turn_num} completed", False, str(e)[:100]) and all_ok

    # ── Phase 4: Replay ─────────────────────────────────────────────────
    print(f"\n{turns + 2}. Replay Turn {turns} (same turnId)...")
    replay_id = turn_ids[-1]

    replay_wf = {
        "1": {
            "class_type": "AWPV2PersistentContinuationTurn",
            "inputs": {
                "session_id": session_id,
                "player_input": PLAYER_INPUTS[(turns - 1) % len(PLAYER_INPUTS)],
                "turn_id": replay_id,
                "request_id": f"req-{replay_id}",
                "workflow_run_id": f"wfr-replay-{int(time.time())}",
                "trace_id": f"trc-replay-{int(time.time())}",
                "director_profile_id": director_profile,
                "writer_profile_id": writer_profile,
            }
        },
        "2": {
            "class_type": "AWPV2TurnResultProbe",
            "inputs": {
                "receipt": ["1", 0],
                "diagnostics": ["1", 2],
                "turn_record": ["1", 4],
                "turn_kind": "continuation",
            }
        }
    }

    try:
        entry = _submit_and_wait(replay_wf, comfy_url, timeout=60)
        status = entry.get("status", {}).get("status_str", "unknown")
        all_ok = _check("Replay completed", status == "success", f"status={status}") and all_ok

        probe = _extract_probe(entry)
        if probe:
            idem = probe.get("idempotency_status", "")
            all_ok = _check("Replay idempotency_status=replayed", idem == "replayed",
                            f"got '{idem}'") and all_ok
            print(f"       Replay: turn_index={probe.get('turn_index')}, "
                  f"rev_before={probe.get('card_state_revision_before')}, "
                  f"rev_after={probe.get('card_state_revision_after')}")
    except Exception as e:
        all_ok = _check("Replay completed", False, str(e)[:100]) and all_ok

    # ── Final ────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if all_ok:
        print("PLAYABLE E2E TEST: ALL CHECKS PASSED")
    else:
        print("PLAYABLE E2E TEST: SOME CHECKS FAILED")
    print("=" * 60)

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Playable E2E Test")
    parser.add_argument("--turns", type=int, default=8)
    parser.add_argument("--director-profile", default="fake-director")
    parser.add_argument("--writer-profile", default="fake-writer")
    parser.add_argument("--comfy-url", default=COMFY_URL)

    args = parser.parse_args()

    # Set test profile
    if "AWP_RUNTIME_PROFILE" not in os.environ:
        os.environ["AWP_RUNTIME_PROFILE"] = "test"
    if "AWP_TEST_RUNTIME_NAMESPACE" not in os.environ:
        os.environ["AWP_TEST_RUNTIME_NAMESPACE"] = f"play-{int(time.time())}"

    ok = run_playable_e2e(
        turns=args.turns,
        director_profile=args.director_profile,
        writer_profile=args.writer_profile,
        comfy_url=args.comfy_url,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
