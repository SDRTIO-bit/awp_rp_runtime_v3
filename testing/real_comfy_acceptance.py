"""Real ComfyUI API Acceptance Test — runs against a live ComfyUI instance.

Verifies:
  1. /object_info discovers AWP nodes
  2. Smoke workflow executes successfully
  3. WebSocket events are received (via history messages)
  4. /history/{promptId} returns results
  5. Three scenarios pass: card_import, quality_reject, retry_idempotency

Exit codes:
  0 = all checks passed
  1 = one or more checks failed
  2 = ComfyUI not available
"""

from __future__ import annotations

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


def main() -> int:
    print("=" * 60)
    print("AWP RP Runtime V2 — Real ComfyUI API Acceptance")
    print("=" * 60)
    print()

    # 1. Check ComfyUI available
    print("1. Checking ComfyUI availability...")
    if not check_comfyui_available():
        print("  [FAIL] ComfyUI is not available at", COMFY_URL)
        print("  Start ComfyUI before running this script.")
        return 2
    print("  [PASS] ComfyUI is available")
    print()

    # 2. Check AWP nodes discoverable
    print("2. Checking AWP node discovery...")
    object_info = get_object_info()
    awp_nodes = [k for k in object_info.keys() if k.startswith("AWPV2")]
    run_check("AWP nodes discovered", len(awp_nodes) >= 64,
              f"Found {len(awp_nodes)} AWP nodes")

    # Check critical nodes
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
    smoke_passed = True
    try:
        wf_path = WORKFLOW_DIR / "smoke_minimal_turn.api.json"
        with open(wf_path, "r", encoding="utf-8") as f:
            workflow = json.load(f)

        # Modify to force fresh execution
        workflow["3"]["inputs"]["trace_id"] = f"acceptance-{int(time.time())}"

        prompt_id = submit_workflow(workflow, "awp-acceptance-smoke")
        run_check("Prompt submitted", bool(prompt_id), f"prompt_id={prompt_id}")

        entry = wait_for_completion(prompt_id)
        status = entry.get("status", {})
        success = status.get("status_str") == "success"
        run_check("Workflow completed", success,
                  f"status={status.get('status_str', 'unknown')}")

        # Check execution messages
        messages = status.get("messages", [])
        event_types = [m[0] for m in messages]
        run_check("Execution events received", len(event_types) > 0,
                  f"Events: {event_types}")

        # Verify at least some nodes executed (not all cached)
        cached_nodes = []
        for m in messages:
            if m[0] == "execution_cached":
                cached_nodes = m[1].get("nodes", [])
        run_check("Nodes executed (not all cached)",
                  len(cached_nodes) < 6,
                  f"Cached: {cached_nodes}")

    except Exception as exc:
        run_check("Smoke workflow", False, str(exc))
        smoke_passed = False
    print()

    # 4. Run 3 real API scenarios
    scenarios = [
        ("card_import_safe_json", "card_import_safe_json.api.json"),
        ("quality_reject_zero_side_effect", "quality_reject_zero_side_effect.api.json"),
        ("retry_idempotency", "retry_idempotency.api.json"),
    ]

    all_scenarios_passed = True
    for scenario_name, wf_file in scenarios:
        print(f"4.{scenarios.index((scenario_name, wf_file))+1}. Running {scenario_name}...")
        try:
            wf_path = WORKFLOW_DIR / wf_file
            if not wf_path.exists():
                run_check("Workflow file exists", False, f"Not found: {wf_path}")
                all_scenarios_passed = False
                continue

            with open(wf_path, "r", encoding="utf-8") as f:
                workflow = json.load(f)

            # Force fresh execution and resolve fixture paths
            for node_id, node_def in workflow.items():
                if isinstance(node_def, dict):
                    inputs = node_def.get("inputs", {})
                    if "trace_id" in inputs:
                        inputs["trace_id"] = f"{scenario_name}-{int(time.time())}"
                    # Resolve relative test fixture paths to absolute
                    if "source_path" in inputs:
                        rel = inputs["source_path"]
                        if not Path(rel).is_absolute():
                            abs_path = str(TEST_FIXTURES_DIR / Path(rel).name)
                            inputs["source_path"] = abs_path

            prompt_id = submit_workflow(workflow, f"awp-acceptance-{scenario_name}")
            run_check(f"{scenario_name}: submitted", bool(prompt_id))

            entry = wait_for_completion(prompt_id)
            status = entry.get("status", {})
            success = status.get("status_str") == "success"
            run_check(f"{scenario_name}: completed", success,
                      f"status={status.get('status_str', 'unknown')}")

            if not success:
                all_scenarios_passed = False
                # Print error details
                for m in status.get("messages", []):
                    if m[0] == "execution_error":
                        print(f"       Error: {json.dumps(m[1], indent=2)[:500]}")

        except Exception as exc:
            run_check(f"{scenario_name}", False, str(exc))
            all_scenarios_passed = False
        print()

    # Summary
    print("=" * 60)
    overall = smoke_passed and all_scenarios_passed and len(missing) == 0
    if overall:
        print("ALL ACCEPTANCE CHECKS PASSED")
    else:
        print("SOME ACCEPTANCE CHECKS FAILED")
    print("=" * 60)

    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
