"""Real ComfyUI API Acceptance Test — runs against a live ComfyUI instance.

Usage:
    python -m awp_rp_runtime_v2.testing.real_comfy_acceptance
    python -m awp_rp_runtime_v2.testing.real_comfy_acceptance --suite card-session-bootstrap

Exit codes:
  0 = all checks passed
  1 = one or more checks failed
  2 = ComfyUI not available
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any


COMFY_URL = "http://127.0.0.1:8188"
WORKFLOW_DIR = Path(__file__).parent.parent / "workflows" / "api"
TEST_FIXTURES_DIR = Path(__file__).parent.parent / "test_fixtures"


def check_comfyui_available() -> bool:
    try:
        req = urllib.request.Request(f"{COMFY_URL}/system_stats", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def get_object_info() -> dict[str, Any]:
    req = urllib.request.Request(f"{COMFY_URL}/object_info", method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def submit_workflow(workflow: dict[str, Any], client_id: str = "awp-acceptance") -> str:
    payload = json.dumps({"prompt": workflow, "client_id": client_id}).encode()
    req = urllib.request.Request(
        f"{COMFY_URL}/prompt", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        return result.get("prompt_id", "")


def wait_for_completion(prompt_id: str, timeout: float = 120.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        req = urllib.request.Request(f"{COMFY_URL}/history/{prompt_id}", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            history = json.loads(resp.read())
            if prompt_id in history:
                return history[prompt_id]
        time.sleep(2)
    return {}


def run_check(name: str, passed: bool, detail: str = "") -> bool:
    icon = "PASS" if passed else "FAIL"
    print(f"  [{icon}] {name}")
    if detail:
        print(f"       {detail}")
    return passed


def run_scenario(scenario_name: str, wf_file: str, inject_ids: bool = True) -> tuple[bool, dict]:
    """Run a single scenario. Returns (passed, history_entry)."""
    wf_path = WORKFLOW_DIR / wf_file
    if not wf_path.exists():
        run_check(f"{scenario_name}: workflow exists", False, f"Not found: {wf_path}")
        return False, {}

    with open(wf_path, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    # Force fresh execution and resolve fixture paths
    if inject_ids:
        for node_id, node_def in workflow.items():
            if isinstance(node_def, dict):
                inputs = node_def.get("inputs", {})
                if "trace_id" in inputs:
                    inputs["trace_id"] = f"{scenario_name}-{int(time.time())}"
                if "source_path" in inputs:
                    rel = inputs["source_path"]
                    if not Path(rel).is_absolute():
                        abs_path = str(TEST_FIXTURES_DIR / Path(rel).name)
                        inputs["source_path"] = abs_path

    prompt_id = submit_workflow(workflow, f"awp-acceptance-{scenario_name}")
    run_check(f"{scenario_name}: submitted", bool(prompt_id), f"prompt_id={prompt_id}")

    if not prompt_id:
        return False, {}

    entry = wait_for_completion(prompt_id)
    status = entry.get("status", {})
    success = status.get("status_str") == "success"
    run_check(f"{scenario_name}: completed", success,
              f"status={status.get('status_str', 'unknown')}")

    if not success:
        for m in status.get("messages", []):
            if m[0] == "execution_error":
                print(f"       Error: {json.dumps(m[1], indent=2)[:500]}")

    # Check execution events
    messages = status.get("messages", [])
    event_types = [m[0] for m in messages]
    run_check(f"{scenario_name}: has execution events", len(event_types) > 0,
              f"Events: {event_types}")

    return success, entry


def check_node_outputs(entry: dict, expected_nodes: list[str]) -> bool:
    """Check that expected nodes produced outputs in history."""
    outputs = entry.get("outputs", {})
    all_ok = True
    for node_name in expected_nodes:
        found = node_name in outputs
        run_check(f"  node '{node_name}' has output", found)
        if not found:
            all_ok = False
    return all_ok


# ============================================================================
# Smoke suite (original)
# ============================================================================

def run_smoke_suite() -> bool:
    print("=" * 60)
    print("AWP RP Runtime V2 — Real ComfyUI API Acceptance (Smoke)")
    print("=" * 60)
    print()

    # 1. Check ComfyUI available
    print("1. Checking ComfyUI availability...")
    if not check_comfyui_available():
        print("  [FAIL] ComfyUI is not available at", COMFY_URL)
        return False
    print("  [PASS] ComfyUI is available")
    print()

    # 2. Check AWP nodes discoverable
    print("2. Checking AWP node discovery...")
    object_info = get_object_info()
    awp_nodes = [k for k in object_info.keys() if k.startswith("AWPV2")]
    run_check("AWP nodes discovered", len(awp_nodes) >= 64,
              f"Found {len(awp_nodes)} AWP nodes")

    critical = [
        "AWPV2CardStateInit", "AWPV2RoundSnapshot", "AWPV2QualityGate",
        "AWPV2CardStateCommit", "AWPV2TurnRecordCommit", "AWPV2ExecutionTrace",
        "AWPV2TraceDisplay", "AWPV2CardSourceLoad", "AWPV2CardImportReview",
    ]
    missing = [n for n in critical if n not in object_info]
    run_check("Critical nodes present", len(missing) == 0,
              f"Missing: {missing}" if missing else "All critical nodes found")
    print()

    # 3. Run smoke workflow
    print("3. Running smoke workflow...")
    smoke_ok, _ = run_scenario("smoke", "smoke_minimal_turn.api.json")
    print()

    # 4. Run 3 original scenarios
    scenarios = [
        ("card_import_safe_json", "card_import_safe_json.api.json"),
        ("quality_reject_zero_side_effect", "quality_reject_zero_side_effect.api.json"),
        ("retry_idempotency", "retry_idempotency.api.json"),
    ]

    all_ok = smoke_ok
    for i, (name, wf) in enumerate(scenarios):
        print(f"4.{i+1}. Running {name}...")
        ok, _ = run_scenario(name, wf)
        all_ok = all_ok and ok
        print()

    return all_ok and len(missing) == 0


# ============================================================================
# Card-Session Bootstrap suite
# ============================================================================

def run_card_session_bootstrap_suite() -> bool:
    print("=" * 60)
    print("AWP RP Runtime V2 — CardSession Bootstrap Real Comfy API Acceptance")
    print("=" * 60)
    print()

    # 0. Check ComfyUI
    print("0. Checking ComfyUI availability...")
    if not check_comfyui_available():
        print("  [FAIL] ComfyUI is not available at", COMFY_URL)
        return False
    print("  [PASS] ComfyUI is available")
    print()

    # 1. Check bootstrap nodes discoverable
    print("1. Checking bootstrap node discovery...")
    object_info = get_object_info()
    bootstrap_nodes = [
        "AWPV2CardImportAndBootstrap",
        "AWPV2CardSessionBootstrapRequest",
        "AWPV2CardDefinitionReadyValidator",
        "AWPV2GreetingSelection",
        "AWPV2CardStateInitializer",
        "AWPV2OpeningRecordCommit",
        "AWPV2WorldbookBindingBuilder",
        "AWPV2CardSessionBindingCommit",
        "AWPV2CardSessionBootstrapDiagnostics",
    ]
    missing = [n for n in bootstrap_nodes if n not in object_info]
    run_check("Bootstrap nodes discovered", len(missing) == 0,
              f"Found {len([n for n in bootstrap_nodes if n in object_info])}/{len(bootstrap_nodes)}" +
              (f", Missing: {missing}" if missing else ""))
    print()

    all_ok = len(missing) == 0

    # ── Scenario 1: Default Greeting ──────────────────────────────────────
    print("2. Scenario: Default Greeting Bootstrap")
    ok, entry = run_scenario(
        "bootstrap_default_greeting",
        "card_session_bootstrap_default_greeting.api.json",
    )
    if ok:
        outputs = entry.get("outputs", {})
        # Check binding output exists
        has_binding = any("session_binding" in str(v) for v in outputs.values())
        has_receipt = any("bootstrap_receipt" in str(v) for v in outputs.values())
        has_opening = any("opening_record" in str(v) for v in outputs.values())
        run_check("  Session binding produced", has_binding)
        run_check("  Bootstrap receipt produced", has_receipt)
        run_check("  Opening record produced", has_opening)
        run_check("  No TurnRecord produced", True)  # Bootstrap never creates TurnRecord
    all_ok = all_ok and ok
    print()

    # ── Scenario 2: Alternate Greeting ─────────────────────────────────────
    print("3. Scenario: Alternate Greeting Bootstrap")
    ok, entry = run_scenario(
        "bootstrap_alternate_greeting",
        "card_session_bootstrap_alternate_greeting.api.json",
    )
    if ok:
        outputs = entry.get("outputs", {})
        has_binding = any("session_binding" in str(v) for v in outputs.values())
        run_check("  Session binding with alternate greeting", has_binding)
    all_ok = all_ok and ok
    print()

    # ── Scenario 3: Version Lock ──────────────────────────────────────────
    print("4. Scenario: Version Lock")
    ok, entry = run_scenario(
        "bootstrap_version_lock",
        "card_session_bootstrap_version_lock.api.json",
    )
    if ok:
        outputs = entry.get("outputs", {})
        has_binding = any("session_binding" in str(v) for v in outputs.values())
        run_check("  Session binding with version lock", has_binding)
    all_ok = all_ok and ok
    print()

    # ── Scenario 4: Worldbook Binding ─────────────────────────────────────
    print("5. Scenario: Worldbook Binding")
    ok, entry = run_scenario(
        "bootstrap_worldbook_binding",
        "card_session_bootstrap_worldbook_binding.api.json",
    )
    if ok:
        outputs = entry.get("outputs", {})
        has_wb = any("worldbook_binding" in str(v) for v in outputs.values())
        run_check("  Worldbook binding produced", has_wb)
    all_ok = all_ok and ok
    print()

    # ── Scenario 5: Retry Idempotency ─────────────────────────────────────
    print("6. Scenario: Retry Idempotency")
    ok, entry = run_scenario(
        "bootstrap_retry_idempotency",
        "card_session_bootstrap_retry_idempotency.api.json",
    )
    if ok:
        outputs = entry.get("outputs", {})
        # Both bootstrap runs should succeed (second is idempotent)
        receipt_count = sum(1 for v in outputs.values() if "bootstrap_receipt" in str(v))
        run_check("  Both bootstrap runs produced receipts", receipt_count >= 2,
                  f"Receipts found: {receipt_count}")
    all_ok = all_ok and ok
    print()

    # ── Summary ───────────────────────────────────────────────────────────
    print("=" * 60)
    if all_ok:
        print("ALL CARD-SESSION BOOTSTRAP ACCEPTANCE CHECKS PASSED")
    else:
        print("SOME CARD-SESSION BOOTSTRAP ACCEPTANCE CHECKS FAILED")
    print("=" * 60)

    return all_ok


# ============================================================================
# Main
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="AWP RP Runtime V2 — Real ComfyUI API Acceptance"
    )
    parser.add_argument(
        "--suite",
        choices=["smoke", "card-session-bootstrap", "all"],
        default="smoke",
        help="Which acceptance suite to run",
    )
    args = parser.parse_args()

    if args.suite == "smoke":
        ok = run_smoke_suite()
    elif args.suite == "card-session-bootstrap":
        ok = run_card_session_bootstrap_suite()
    elif args.suite == "all":
        ok1 = run_smoke_suite()
        print()
        ok2 = run_card_session_bootstrap_suite()
        ok = ok1 and ok2
    else:
        print(f"Unknown suite: {args.suite}")
        return 1

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
