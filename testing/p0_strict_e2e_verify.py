"""Strict P0 E2E verification — checks both /history outputs explicitly."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import uuid

COMFY = "http://127.0.0.1:8188"


def submit_and_wait(wf, timeout=300):
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


def check_outputs(entry, label):
    outputs = entry.get("outputs", {})
    has_text = False
    has_probe = False
    text_len = 0
    probe_text_len = 0
    idem = ""
    turn_idx = 0
    for nid, nout in outputs.items():
        if not isinstance(nout, dict):
            continue
        if "awp_accepted_text" in nout:
            t = nout["awp_accepted_text"]
            if t and isinstance(t, list) and t[0]:
                has_text = True
                text_len = len(t[0])
        if "awp_turn_result_json" in nout:
            t = nout["awp_turn_result_json"]
            if t and isinstance(t, list) and t[0]:
                probe = json.loads(t[0])
                has_probe = True
                probe_text_len = probe.get("accepted_text_length", 0)
                idem = probe.get("idempotency_status", "")
                turn_idx = probe.get("turn_index", 0)
                # Verify probe does NOT contain full text
                if "accepted_text" in probe:
                    print(f"  [FAIL] {label}: probe contains accepted_text field!")
                    return False

    ok = True
    if not has_text:
        print(f"  [FAIL] {label}: awp_accepted_text missing from /history")
        ok = False
    if not has_probe:
        print(f"  [FAIL] {label}: awp_turn_result_json missing from /history")
        ok = False
    if has_text and text_len == 0:
        print(f"  [FAIL] {label}: accepted text is empty")
        ok = False
    if ok:
        print(f"  [PASS] {label}: text_len={text_len}, probe_text_len={probe_text_len}, "
              f"turn_idx={turn_idx}, idem={idem}")
    return ok


def main():
    all_ok = True
    card_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "test_fixtures", "test_card_v3_with_worldbook.json",
    )
    card_path = os.path.normpath(card_path)
    sess_id = f"strict-{int(time.time() * 1000)}"

    print("=" * 60)
    print("P0 Strict E2E Verification")
    print("=" * 60)

    # 1. Bootstrap
    print("\n1. Bootstrap...")
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
    }, timeout=30)
    s = entry["status"]["status_str"]
    print(f"   status={s}")
    if s != "success":
        print("  [FAIL] Bootstrap failed")
        return False

    # 2. First Turn
    print("\n2. First Turn...")
    turn1_id = f"t1-{sess_id}"
    entry = submit_and_wait({
        "1": {
            "class_type": "AWPV2PersistentFirstTurn",
            "inputs": {
                "session_id": sess_id,
                "player_input": "你好，我想了解一下这个地方。",
                "turn_id": turn1_id,
                "request_id": f"r-{turn1_id}",
                "director_profile_id": os.environ.get("AWP_DIRECTOR_PROFILE", "fake-director"),
                "writer_profile_id": os.environ.get("AWP_WRITER_PROFILE", "fake-writer"),
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
                "turn_kind": "first",
            },
        },
    })
    all_ok = check_outputs(entry, "Turn 1") and all_ok

    # 3. Continuation Turn 2
    print("\n3. Continuation Turn 2...")
    turn2_id = f"t2-{sess_id}"
    entry = submit_and_wait({
        "1": {
            "class_type": "AWPV2PersistentContinuationTurn",
            "inputs": {
                "session_id": sess_id,
                "player_input": "你平时都做些什么呢？",
                "turn_id": turn2_id,
                "request_id": f"r-{turn2_id}",
                "director_profile_id": os.environ.get("AWP_DIRECTOR_PROFILE", "fake-director"),
                "writer_profile_id": os.environ.get("AWP_WRITER_PROFILE", "fake-writer"),
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
                "turn_kind": "continuation",
            },
        },
    })
    all_ok = check_outputs(entry, "Turn 2") and all_ok

    # 4. Continuation Turn 3
    print("\n4. Continuation Turn 3...")
    turn3_id = f"t3-{sess_id}"
    entry = submit_and_wait({
        "1": {
            "class_type": "AWPV2PersistentContinuationTurn",
            "inputs": {
                "session_id": sess_id,
                "player_input": "村长住在哪里？",
                "turn_id": turn3_id,
                "request_id": f"r-{turn3_id}",
                "director_profile_id": os.environ.get("AWP_DIRECTOR_PROFILE", "fake-director"),
                "writer_profile_id": os.environ.get("AWP_WRITER_PROFILE", "fake-writer"),
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
                "turn_kind": "continuation",
            },
        },
    })
    all_ok = check_outputs(entry, "Turn 3") and all_ok

    # 5. Replay Turn 3 (same turn_id)
    print("\n5. Replay Turn 3 (same turn_id)...")
    entry = submit_and_wait({
        "1": {
            "class_type": "AWPV2PersistentContinuationTurn",
            "inputs": {
                "session_id": sess_id,
                "player_input": "村长住在哪里？",
                "turn_id": turn3_id,
                "request_id": f"r-{turn3_id}",
                "director_profile_id": os.environ.get("AWP_DIRECTOR_PROFILE", "fake-director"),
                "writer_profile_id": os.environ.get("AWP_WRITER_PROFILE", "fake-writer"),
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
                "turn_kind": "continuation",
            },
        },
    })
    outputs = entry.get("outputs", {})
    replay_ok = False
    for nid, nout in outputs.items():
        if not isinstance(nout, dict):
            continue
        if "awp_turn_result_json" in nout:
            t = nout["awp_turn_result_json"]
            if t and isinstance(t, list) and t[0]:
                probe = json.loads(t[0])
                idem = probe.get("idempotency_status", "")
                if idem == "replayed":
                    print(f"  [PASS] Replay: idempotency_status=replayed")
                    replay_ok = True
                else:
                    print(f"  [FAIL] Replay: idempotency_status={idem} (expected replayed)")
    if not replay_ok:
        all_ok = False

    # 6. New request (different turn_id, same session)
    print("\n6. New request (new turn_id, same session)...")
    turn4_id = f"t4-{sess_id}"
    entry = submit_and_wait({
        "1": {
            "class_type": "AWPV2PersistentContinuationTurn",
            "inputs": {
                "session_id": sess_id,
                "player_input": "天色不早了，我该走了。",
                "turn_id": turn4_id,
                "request_id": f"r-{turn4_id}",
                "director_profile_id": os.environ.get("AWP_DIRECTOR_PROFILE", "fake-director"),
                "writer_profile_id": os.environ.get("AWP_WRITER_PROFILE", "fake-writer"),
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
                "turn_kind": "continuation",
            },
        },
    })
    all_ok = check_outputs(entry, "Turn 4 (new request)") and all_ok

    # Summary
    print("\n" + "=" * 60)
    if all_ok:
        print("ALL STRICT E2E CHECKS PASSED")
    else:
        print("SOME CHECKS FAILED")
    print("=" * 60)
    return all_ok


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
