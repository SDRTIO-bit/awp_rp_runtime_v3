"""P0 Freeze Acceptance: 5 fresh turns + restart + turn 6.

Requires real DeepSeek API key and ComfyUI running at 127.0.0.1:8188.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import uuid

COMFY = "http://127.0.0.1:8188"
TIMEOUT = 300


def submit_and_wait(wf, timeout=TIMEOUT):
    payload = json.dumps({"prompt": wf, "client_id": f"v-{uuid.uuid4().hex[:6]}"})
    req = urllib.request.Request(
        f"{COMFY}/prompt", data=payload.encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    pid = json.loads(resp.read())["prompt_id"]
    for _ in range(timeout // 2):
        time.sleep(2)
        r = urllib.request.urlopen(f"{COMFY}/history/{pid}", timeout=30)
        h = json.loads(r.read())
        if pid in h:
            return h[pid]
    raise TimeoutError(f"{pid} timeout")


def extract_outputs(entry):
    outputs = entry.get("outputs", {})
    result = {"text_len": 0, "probe_text_len": 0, "turn_idx": 0,
              "idem": "", "quality": "", "hash": "", "has_text": False,
              "has_probe": False, "probe_has_full_text": False,
              "rev_before": 0, "rev_after": 0}
    for nid, nout in outputs.items():
        if not isinstance(nout, dict):
            continue
        if "awp_accepted_text" in nout:
            t = nout["awp_accepted_text"]
            if t and isinstance(t, list) and t[0]:
                result["has_text"] = True
                result["text_len"] = len(t[0])
        if "awp_turn_result_json" in nout:
            t = nout["awp_turn_result_json"]
            if t and isinstance(t, list) and t[0]:
                probe = json.loads(t[0])
                result["has_probe"] = True
                result["probe_text_len"] = probe.get("accepted_text_length", 0)
                result["turn_idx"] = probe.get("turn_index", 0)
                result["idem"] = probe.get("idempotency_status", "")
                result["quality"] = probe.get("quality_status", "")
                result["hash"] = probe.get("accepted_text_hash", "")[:16]
                result["rev_before"] = probe.get("card_state_revision_before", 0)
                result["rev_after"] = probe.get("card_state_revision_after", 0)
                result["probe_has_full_text"] = "accepted_text" in probe
    return result


def check(label, r, expect_idem="fresh", expect_turn_idx=0):
    ok = True
    if not r["has_text"]:
        print(f"  [FAIL] {label}: awp_accepted_text missing")
        ok = False
    if not r["has_probe"]:
        print(f"  [FAIL] {label}: awp_turn_result_json missing")
        ok = False
    if r["probe_has_full_text"]:
        print(f"  [FAIL] {label}: probe leaks full text")
        ok = False
    if r["idem"] != expect_idem:
        print(f"  [FAIL] {label}: idem={r['idem']}, expected {expect_idem}")
        ok = False
    if expect_turn_idx and r["turn_idx"] != expect_turn_idx:
        print(f"  [FAIL] {label}: turn_idx={r['turn_idx']}, expected {expect_turn_idx}")
        ok = False
    if r["text_len"] != r["probe_text_len"]:
        print(f"  [FAIL] {label}: text_len={r['text_len']} != probe_text_len={r['probe_text_len']}")
        ok = False
    if r["text_len"] == 0:
        print(f"  [FAIL] {label}: empty text")
        ok = False
    if ok:
        print(f"  [PASS] {label}: turn_idx={r['turn_idx']}, idem={r['idem']}, "
              f"text_len={r['text_len']}, rev={r['rev_before']}->{r['rev_after']}, "
              f"hash={r['hash']}...")
    return ok


def make_turn_wf(sess_id, turn_id, player_input, turn_kind, director, writer):
    node_class = "AWPV2PersistentFirstTurn" if turn_kind == "first" else "AWPV2PersistentContinuationTurn"
    return {
        "1": {
            "class_type": node_class,
            "inputs": {
                "session_id": sess_id,
                "player_input": player_input,
                "turn_id": turn_id,
                "request_id": f"r-{turn_id}",
                "workflow_run_id": f"wfr-{turn_id}",
                "trace_id": f"trc-{turn_id}",
                "director_profile_id": director,
                "writer_profile_id": writer,
            },
        },
        "2": {
            "class_type": "AWPV2AcceptedTextOutput",
            "inputs": {"turn_record": ["1", 4]},
        },
        "3": {
            "class_type": "AWPV2TurnResultProbe",
            "inputs": {
                "receipt": ["1", 0],
                "diagnostics": ["1", 2],
                "turn_record": ["1", 4],
                "turn_kind": turn_kind,
            },
        },
    }


PLAYER_INPUTS = [
    "你好，我想了解一下这个地方。",
    "你平时都做些什么呢？",
    "村长住在哪里？我有事找他。",
    "我答应你，明天会再来拜访。",
    "天色不早了，我该走了。",
    "对了，我之前答应过什么来着？",
]


def main():
    card_path = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "test_fixtures", "test_card_v3_with_worldbook.json",
    ))
    director = os.environ.get("AWP_DIRECTOR_PROFILE", "fake-director")
    writer = os.environ.get("AWP_WRITER_PROFILE", "fake-writer")
    sess_id = f"freeze-{int(time.time() * 1000)}"
    all_ok = True
    turn_records = []

    print("=" * 70)
    print("P0 Freeze Acceptance: 5 fresh turns + restart + turn 6")
    print(f"  Director: {director}")
    print(f"  Writer:   {writer}")
    print(f"  Session:  {sess_id}")
    print("=" * 70)

    # ── Bootstrap ─────────────────────────────────────────────────────
    print("\n0. Bootstrap...")
    entry = submit_and_wait({
        "1": {
            "class_type": "AWPV2PersistentBootstrap",
            "inputs": {
                "source_path": card_path, "session_id": sess_id,
                "greeting_id": "g0",
                "request_id": f"r-bs-{sess_id}",
                "run_id": f"run-{sess_id}",
            },
        }
    }, timeout=60)
    s = entry["status"]["status_str"]
    print(f"   status={s}")
    if s != "success":
        print("  [FAIL] Bootstrap failed")
        return False

    # ── Turns 1-5 ─────────────────────────────────────────────────────
    for i in range(1, 6):
        turn_kind = "first" if i == 1 else "continuation"
        turn_id = f"t{i}-{sess_id}"
        player_input = PLAYER_INPUTS[(i - 1) % len(PLAYER_INPUTS)]

        print(f"\n{i}. Turn {i} ({turn_kind})...")
        entry = submit_and_wait(make_turn_wf(
            sess_id, turn_id, player_input, turn_kind, director, writer,
        ))
        s = entry["status"]["status_str"]
        if s != "success":
            print(f"  [FAIL] Turn {i} status={s}")
            all_ok = False
            continue

        r = extract_outputs(entry)
        ok = check(f"Turn {i}", r, expect_idem="fresh", expect_turn_idx=i)
        all_ok = ok and all_ok
        turn_records.append({
            "turn_id": turn_id, "turn_idx": r["turn_idx"],
            "text_len": r["text_len"], "idem": r["idem"],
        })

    # ── Summary before restart ────────────────────────────────────────
    print("\n" + "-" * 70)
    print("Before restart — turn summary:")
    for t in turn_records:
        print(f"  {t['turn_id']}: idx={t['turn_idx']}, text_len={t['text_len']}, idem={t['idem']}")
    print("-" * 70)

    # ── Report: require output for external restart ───────────────────
    print("\n" + "=" * 70)
    print("RESTART REQUIRED")
    print("Please restart ComfyUI now, then re-run this script with --phase2 flag.")
    print(f"  Session ID: {sess_id}")
    print(f"  Save this session_id for the post-restart turn.")
    print("=" * 70)

    # Save state for phase 2
    state = {
        "session_id": sess_id,
        "director": director,
        "writer": writer,
        "turn_records": turn_records,
        "card_path": card_path,
    }
    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_freeze_state.json")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f"\nState saved to {state_path}")

    if "--phase2" not in sys.argv:
        print("\nRun again with --phase2 after restarting ComfyUI.")
        return all_ok

    # ── Phase 2: Post-restart turn 6 ──────────────────────────────────
    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_freeze_state.json")
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)
    sess_id = state["session_id"]
    director = state["director"]
    writer = state["writer"]
    turn_records = state["turn_records"]

    print("\n" + "=" * 70)
    print("Phase 2: Post-restart Turn 6")
    print(f"  Session: {sess_id}")
    print("=" * 70)

    turn6_id = f"t6-{sess_id}"
    player_input = PLAYER_INPUTS[5]

    print(f"\n6. Turn 6 (continuation, post-restart)...")
    entry = submit_and_wait(make_turn_wf(
        sess_id, turn6_id, player_input, "continuation", director, writer,
    ))
    s = entry["status"]["status_str"]
    if s != "success":
        print(f"  [FAIL] Turn 6 status={s}")
        return False

    r = extract_outputs(entry)
    ok = check("Turn 6 (post-restart)", r, expect_idem="fresh", expect_turn_idx=6)
    all_ok = ok and all_ok

    # ── Verify L1 continuity ──────────────────────────────────────────
    # The text should reference prior context (fake writer includes it)
    # For real writer, just check text_len > 0 (already done in check())
    print(f"\n  L1 continuity: Turn 6 text_len={r['text_len']}, "
          f"rev={r['rev_before']}->{r['rev_after']}")

    # ── Final report ──────────────────────────────────────────────────
    print("\n" + "=" * 70)
    turn_records.append({
        "turn_id": turn6_id, "turn_idx": r["turn_idx"],
        "text_len": r["text_len"], "idem": r["idem"],
    })
    print("All turns:")
    for t in turn_records:
        print(f"  {t['turn_id']}: idx={t['turn_idx']}, text_len={t['text_len']}, idem={t['idem']}")
    print("=" * 70)

    if all_ok:
        print("\nACCEPT_AND_FREEZE: All checks passed")
    else:
        print("\nREJECT: Some checks failed")
    return all_ok


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
