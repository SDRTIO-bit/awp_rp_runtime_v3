"""Real ComfyUI API Acceptance Test — runs against a live ComfyUI instance.

Usage:
    python testing/real_comfy_acceptance.py
    python testing/real_comfy_acceptance.py --suite card-session-bootstrap

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
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result.get("prompt_id", "")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  [ERROR] HTTP {e.code}: {body[:500]}")
        return ""


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


def inject_unique_ids(workflow: dict, scenario_name: str) -> None:
    """Inject unique IDs into workflow inputs to force fresh execution."""
    ts = int(time.time() * 1000)
    unique_suffix = f"{scenario_name}-{ts}"
    for node_id, node_def in workflow.items():
        if isinstance(node_def, dict):
            inputs = node_def.get("inputs", {})
            for key in ["run_id", "trace_id", "request_id", "session_id", "workflow_run_id"]:
                if key in inputs:
                    inputs[key] = f"{key[:3]}-{unique_suffix}"
            if "source_path" in inputs:
                rel = inputs["source_path"]
                if not Path(rel).is_absolute():
                    inputs["source_path"] = str(TEST_FIXTURES_DIR / Path(rel).name)


def run_scenario(scenario_name: str, wf_file: str) -> tuple[bool, dict]:
    """Run a single scenario. Returns (passed, history_entry).

    Checks:
      1. Workflow file exists
      2. Prompt submits successfully (HTTP 200)
      3. Workflow completes (status=success)
      4. No execution_error events
    """
    wf_path = WORKFLOW_DIR / wf_file
    if not wf_path.exists():
        run_check(f"{scenario_name}: workflow exists", False, f"Not found: {wf_path}")
        return False, {}

    with open(wf_path, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    inject_unique_ids(workflow, scenario_name)

    prompt_id = submit_workflow(workflow, f"awp-acceptance-{scenario_name}")
    submitted = bool(prompt_id)
    run_check(f"{scenario_name}: submitted", submitted, f"prompt_id={prompt_id}")
    if not submitted:
        return False, {}

    entry = wait_for_completion(prompt_id)
    status = entry.get("status", {})
    status_str = status.get("status_str", "unknown")
    success = status_str in ("success",)
    run_check(f"{scenario_name}: completed", success, f"status={status_str}")

    # Check for errors
    messages = status.get("messages", [])
    event_types = [m[0] for m in messages]
    has_error = "execution_error" in event_types
    run_check(f"{scenario_name}: no execution errors", not has_error,
              f"Events: {event_types}" if has_error else "")

    if has_error:
        for m in messages:
            if m[0] == "execution_error":
                print(f"       Error: {json.dumps(m[1], indent=2)[:500]}")
        return False, entry

    return True, entry


# ============================================================================
# Smoke suite
# ============================================================================

def run_smoke_suite() -> bool:
    print("=" * 60)
    print("AWP RP Runtime V2 — Real ComfyUI API Acceptance (Smoke)")
    print("=" * 60)
    print()

    print("1. Checking ComfyUI availability...")
    if not check_comfyui_available():
        print("  [FAIL] ComfyUI is not available at", COMFY_URL)
        return False
    print("  [PASS] ComfyUI is available")
    print()

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

    print("3. Running smoke workflow...")
    smoke_ok, _ = run_scenario("smoke", "smoke_minimal_turn.api.json")
    print()

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

    print("0. Checking ComfyUI availability...")
    if not check_comfyui_available():
        print("  [FAIL] ComfyUI is not available at", COMFY_URL)
        return False
    print("  [PASS] ComfyUI is available")
    print()

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
    found = len(bootstrap_nodes) - len(missing)
    run_check("Bootstrap nodes discovered", len(missing) == 0,
              f"Found {found}/{len(bootstrap_nodes)}" +
              (f", Missing: {missing}" if missing else ""))
    print()

    all_ok = len(missing) == 0

    # 5 scenarios — each verifies: submit → complete → no error
    scenarios = [
        ("Default Greeting", "bootstrap_default_greeting", "card_session_bootstrap_default_greeting.api.json"),
        ("Alternate Greeting", "bootstrap_alternate_greeting", "card_session_bootstrap_alternate_greeting.api.json"),
        ("Version Lock", "bootstrap_version_lock", "card_session_bootstrap_version_lock.api.json"),
        ("Worldbook Binding", "bootstrap_worldbook_binding", "card_session_bootstrap_worldbook_binding.api.json"),
        ("Retry Idempotency (run 1)", "bootstrap_idempotency_1", "card_session_bootstrap_retry_idempotency.api.json"),
        ("Retry Idempotency (run 2)", "bootstrap_idempotency_2", "card_session_bootstrap_retry_idempotency.api.json"),
    ]

    for i, (label, name, wf) in enumerate(scenarios, 2):
        print(f"{i}. Scenario: {label}")
        ok, _ = run_scenario(name, wf)
        all_ok = all_ok and ok
        print()

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
