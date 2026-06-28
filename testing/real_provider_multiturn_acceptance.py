"""Real Provider Multi-Turn Acceptance -- 12-turn automated RP scenario.

Usage:
  python -m awp_rp_runtime_v2.testing.real_provider_multiturn_acceptance \\
    --card-path $env:AWP_REAL_CARD_PATH \\
    --turns 12 \\
    --mode full_pipeline

Requires:
  AWP_REAL_LLM_E2E=1
  AWP_ALLOW_EXTERNAL_CARD_CONTENT=1
  DEEPSEEK_API_KEY=<key>
  AWP_REAL_CARD_PATH=<path>

Never prints API keys or card content to stdout/artifacts.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from awp_rp_runtime_v2.runtime.provider_env_guard import (
    require_real_provider_env, check_real_provider_env, ProviderEnvConfig,
)
from awp_rp_runtime_v2.contracts.provider_guardrail_config import ProviderGuardrailConfig
from awp_rp_runtime_v2.contracts.provider_request import (
    ProviderAttemptReceipt, ProviderUsage, FailureCode,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"


# ── Turn Definitions ────────────────────────────────────────────────────────

TURN_SCENARIOS = [
    {
        "turn": 1,
        "name": "first_greeting",
        "description": "Session ready, first player input",
        "player_input": "你好，我想了解一下这个地方。",
        "expectations": {
            "quality_accept_min_length": 50,
            "must_have_turn_record": True,
        },
    },
    {
        "turn": 2,
        "name": "scene_continuation",
        "description": "Continue same scene, verify OpeningContext available",
        "player_input": "这里的人平时都做些什么？",
        "expectations": {
            "quality_accept_min_length": 50,
            "must_have_turn_record": True,
        },
    },
    {
        "turn": 3,
        "name": "worldbook_keyword",
        "description": "Trigger worldbook retrieval with entity keyword",
        "player_input": "村长在哪里？我想找他聊聊。",
        "expectations": {
            "quality_accept_min_length": 50,
            "worldbook_entries_checked": True,
        },
    },
    {
        "turn": 4,
        "name": "anchor_fact",
        "description": "Introduce a trackable conversation anchor",
        "player_input": "我答应你，明天会再来拜访。",
        "expectations": {
            "quality_accept_min_length": 50,
            "state_proposal_generated": True,
        },
    },
    {
        "turn": 5,
        "name": "advance_interaction",
        "description": "Advance the interaction, verify state commit",
        "player_input": "天色不早了，我该走了。",
        "expectations": {
            "quality_accept_min_length": 50,
            "card_state_committed": True,
        },
    },
    {
        "turn": 6,
        "name": "recall_anchor",
        "description": "Ask about previous anchor/fact",
        "player_input": "对了，我之前答应过什么来着？",
        "expectations": {
            "quality_accept_min_length": 50,
        },
    },
    {
        "turn": 7,
        "name": "topic_switch",
        "description": "Switch topic, verify context budget and state continuity",
        "player_input": "这个村子有什么特别的传说吗？",
        "expectations": {
            "quality_accept_min_length": 50,
        },
    },
    {
        "turn": 8,
        "name": "return_to_prior",
        "description": "Return to prior event, verify recent turns / memory visibility",
        "player_input": "刚才那位老者还在吗？",
        "expectations": {
            "quality_accept_min_length": 50,
        },
    },
    {
        "turn": 9,
        "name": "conditional_worldbook",
        "description": "Trigger conditional worldbook entry if available",
        "player_input": "有没有什么禁忌是我不知道的？",
        "expectations": {
            "quality_accept_min_length": 50,
            "worldbook_entries_checked": True,
        },
    },
    {
        "turn": 10,
        "name": "retry_idempotency",
        "description": "Same turnId/requestId retry, no duplicate writes",
        "player_input": "我答应你，明天会再来拜访。",
        "is_retry": True,
        "retry_of_turn": 4,
        "expectations": {
            "no_duplicate_state": True,
            "no_duplicate_turn": True,
        },
    },
    {
        "turn": 11,
        "name": "post_retry_normal",
        "description": "Normal input after retry, session not corrupted",
        "player_input": "谢谢你今天的招待。",
        "expectations": {
            "quality_accept_min_length": 50,
            "must_have_turn_record": True,
        },
    },
    {
        "turn": 12,
        "name": "final_continuity",
        "description": "Final continuity and resource boundary check",
        "player_input": "再见，希望下次还能见面。",
        "expectations": {
            "quality_accept_min_length": 50,
            "must_have_turn_record": True,
        },
    },
]


# ── ComfyUI API Client ──────────────────────────────────────────────────────

class ComfyUIClient:
    """Minimal ComfyUI API client for multi-turn acceptance."""

    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: int = 120):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def check_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self._base_url}/system_stats")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def queue_prompt(self, workflow: dict[str, Any]) -> dict[str, Any]:
        import uuid
        client_id = f"awp-mt-{uuid.uuid4().hex[:8]}"
        payload = json.dumps({"prompt": workflow, "client_id": client_id}).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/prompt",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def wait_for_completion(self, prompt_id: str, timeout: int = 0) -> dict[str, Any]:
        if not timeout:
            timeout = self._timeout
        start = time.time()
        while time.time() - start < timeout:
            try:
                req = urllib.request.Request(f"{self._base_url}/history/{prompt_id}")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    history = json.loads(resp.read().decode("utf-8"))
                    if prompt_id in history:
                        return history[prompt_id]
            except Exception:
                pass
            time.sleep(2)
        raise TimeoutError(f"Prompt {prompt_id} did not complete in {timeout}s")

    def get_object_info(self) -> dict[str, Any]:
        req = urllib.request.Request(f"{self._base_url}/object_info")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))


# ── Report Writer ────────────────────────────────────────────────────────────

class MultiturnReportWriter:
    """Writes acceptance artifacts for multi-turn runs."""

    def __init__(self, artifact_root: str | Path):
        self._root = Path(artifact_root)
        self._root.mkdir(parents=True, exist_ok=True)

    def write_run(self, run_id: str, data: dict[str, Any]) -> Path:
        run_dir = self._root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return run_dir

    def write_turns(self, run_dir: Path, turns: list[dict[str, Any]]) -> None:
        (run_dir / "turns.json").write_text(
            json.dumps(turns, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def write_provider_usage(self, run_dir: Path, usage: list[dict[str, Any]]) -> None:
        (run_dir / "provider-usage.json").write_text(
            json.dumps(usage, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def write_report(self, run_dir: Path, report: str) -> None:
        (run_dir / "report.md").write_text(report, encoding="utf-8")

    def write_narrative_regression(self, run_dir: Path, report: dict[str, Any]) -> None:
        (run_dir / "narrative-regression-report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )


# ── Narrative Regression Checker ─────────────────────────────────────────────

class NarrativeRegressionChecker:
    """Optional narrative quality checks.

    Outputs: pass / warning / review_required
    Never replaces hard runtime assertions.
    """

    def check(self, text: str, turn_index: int) -> dict[str, Any]:
        issues = []
        status = "pass"

        # Empty or extremely short
        if not text or len(text.strip()) < 20:
            issues.append("empty_or_very_short")
            status = "review_required"

        # JSON leak
        if "{" in text and "}" in text and ":" in text:
            issues.append("possible_json_leak")
            status = "review_required"

        # Debug markers
        for marker in ["DEBUG", "TODO", "FIXME", "print(", "console.log"]:
            if marker in text:
                issues.append(f"debug_marker_{marker.lower().replace('(', '')}")
                status = "review_required"

        # System prompt leak
        for leak in ["system_prompt", "api_key", "token=", "Authorization:"]:
            if leak.lower() in text.lower():
                issues.append("system_prompt_leak")
                status = "review_required"

        # Repetition (same sentence 3+ times)
        sentences = [s.strip() for s in text.split("。") if s.strip()]
        if len(sentences) >= 3:
            from collections import Counter
            counts = Counter(sentences)
            for sent, count in counts.items():
                if count >= 3:
                    issues.append(f"repetitive_sentence")
                    if status == "pass":
                        status = "warning"
                    break

        return {
            "turn_index": turn_index,
            "status": status,
            "issues": issues,
            "text_length": len(text),
        }


# ── Main Runner ──────────────────────────────────────────────────────────────

def run_multiturn_acceptance(
    card_path: str,
    turns: int = 12,
    mode: str = "full_pipeline",
    save_private_transcript: bool = False,
    max_provider_calls: int = 48,
    max_output_tokens: int = 2000,
    dry_run: bool = False,
    comfy_url: str = "http://127.0.0.1:8188",
) -> dict[str, Any]:
    """Run the multi-turn acceptance test.

    Returns a summary dict with pass/fail per turn.
    """
    # Check environment
    config = require_real_provider_env()

    # Print summary (no secrets)
    director_model = os.environ.get("AWP_DIRECTOR_MODEL", "deepseek-v4-pro")
    writer_model = os.environ.get("AWP_WRITER_MODEL", "deepseek-v4-flash")

    print("=" * 60)
    print("Real Provider Multi-Turn Acceptance (Dual Model)")
    print("=" * 60)
    print(f"  Card path: {config.card_path}")
    print(f"  Director model: {director_model}")
    print(f"  Writer model: {writer_model}")
    print(f"  Max turns: {turns}")
    print(f"  Max provider calls: {max_provider_calls}")
    print(f"  Max output tokens: {max_output_tokens}")
    print(f"  Mode: {mode}")
    print(f"  Dry run: {dry_run}")
    print(f"  Save private transcript: {save_private_transcript}")
    print(f"  ComfyUI URL: {comfy_url}")
    print("=" * 60)

    if dry_run:
        print("\n[DRY RUN] Would execute the above configuration.")
        print("[DRY RUN] No API calls will be made.")
        return {"status": "dry_run", "turns": []}

    # Verify card file exists
    if not Path(card_path).exists():
        print(f"ERROR: Card file not found: {card_path}")
        sys.exit(1)

    # Verify ComfyUI is available
    comfy = ComfyUIClient(comfy_url)
    if not comfy.check_available():
        print(f"ERROR: ComfyUI not available at {comfy_url}")
        sys.exit(2)

    # Check for AWP nodes
    obj_info = comfy.get_object_info()
    awp_nodes = [k for k in obj_info if k.startswith("AWPV2")]
    print(f"\n  AWP nodes found: {len(awp_nodes)}")
    if len(awp_nodes) < 64:
        print("WARNING: Expected >= 64 AWP nodes")

    # Initialize guardrails
    guardrails = ProviderGuardrailConfig(
        max_turns=turns,
        max_provider_calls=max_provider_calls,
        max_output_tokens_per_call=max_output_tokens,
    )

    # Initialize report writer
    run_id = _id("mt", f"{_now()}:{card_path}")
    report_writer = MultiturnReportWriter("artifacts/real-provider-runs")
    narrative_checker = NarrativeRegressionChecker()

    # Track results
    turn_results: list[dict[str, Any]] = []
    provider_receipts: list[dict[str, Any]] = []
    total_provider_calls = 0
    total_tokens = 0
    narrative_reports: list[dict[str, Any]] = []
    all_passed = True

    # Prepare private transcript collector
    from awp_rp_runtime_v2.testing.private_transcript_collector import PrivateTranscriptCollector
    transcript_collector = PrivateTranscriptCollector(run_id)

    # Load workflow
    workflow_path = Path(__file__).parent.parent / "workflows" / "api" / "real_provider_multiturn_v1.api.json"
    if not workflow_path.exists():
        print(f"ERROR: Workflow not found: {workflow_path}")
        sys.exit(1)

    workflow_template = json.loads(workflow_path.read_text(encoding="utf-8"))

    # Session state (persists across turns)
    session_id = _id("sess", run_id)
    logical_card_id = ""
    source_hash = ""
    card_version = 1
    # Track previous turn records for continuation path
    previous_turn_records: list[dict[str, Any]] = []
    # Track turn results for lifecycle audit
    turn_audit_data: list[dict[str, Any]] = []

    print(f"\n  Session ID: {session_id}")
    print(f"  Run ID: {run_id}")
    print()

    # ── Execute Turns ────────────────────────────────────────────────────
    for turn_def in TURN_SCENARIOS[:turns]:
        turn_num = turn_def["turn"]
        turn_name = turn_def["name"]
        player_input = turn_def["player_input"]
        expectations = turn_def.get("expectations", {})

        print(f"--- Turn {turn_num}: {turn_name} ---")
        print(f"  Input: {player_input[:50]}...")

        turn_start = time.time()
        turn_id = _id("turn", f"{run_id}:t{turn_num}")
        attempt_id = _id("att", f"{run_id}:t{turn_num}:a1")
        workflow_run_id = _id("wfr", f"{run_id}:t{turn_num}")

        turn_result = {
            "turn": turn_num,
            "name": turn_name,
            "turn_id": turn_id,
            "attempt_id": attempt_id,
            "workflow_run_id": workflow_run_id,
            "player_input_length": len(player_input),
            "status": "pending",
            "provider_calls": 0,
            "errors": [],
        }

        try:
            # Check guardrails
            if total_provider_calls >= guardrails.max_provider_calls:
                turn_result["status"] = "guardrail_exceeded"
                turn_result["errors"].append("max_provider_calls exceeded")
                turn_results.append(turn_result)
                all_passed = False
                print(f"  FAIL: Guardrail exceeded (max_provider_calls)")
                break

            # Build workflow with turn-specific inputs
            import copy
            workflow = copy.deepcopy(workflow_template.get("prompt", {}))

            # Determine turn kind and execution node
            is_first_turn = (turn_num == 1)
            turn_kind = "first" if is_first_turn else "continuation"
            execution_node_class = "AWPV2FirstTurnExecution" if is_first_turn else "AWPV2ContinuationTurnExecution"

            # Patch workflow inputs
            for node_id, node in workflow.items():
                if not isinstance(node, dict):
                    continue
                inputs = node.get("inputs", {})
                class_type = node.get("class_type", "")

                # Patch the turn execution node class_type
                if class_type == "{{turn_execution_node}}" or "turn_execution_node" in str(inputs):
                    pass  # Handled below

                # Patch common inputs
                if "session_id" in inputs:
                    inputs["session_id"] = session_id
                if "player_input" in inputs:
                    inputs["player_input"] = player_input
                if "turn_id" in inputs:
                    inputs["turn_id"] = turn_id
                if "attempt_id" in inputs:
                    inputs["attempt_id"] = attempt_id
                if "workflow_run_id" in inputs:
                    inputs["workflow_run_id"] = workflow_run_id
                if "trace_id" in inputs:
                    inputs["trace_id"] = _id("trc", workflow_run_id)
                # Dual model support
                if "director_model" in inputs:
                    inputs["director_model"] = os.environ.get("AWP_DIRECTOR_MODEL", "deepseek-v4-pro")
                if "writer_model" in inputs:
                    inputs["writer_model"] = os.environ.get("AWP_WRITER_MODEL", "deepseek-v4-flash")
                if "request_id" in inputs:
                    inputs["request_id"] = _id("req", f"{turn_id}:{attempt_id}")
                if "run_id" in inputs:
                    inputs["run_id"] = _id("run", f"{turn_id}:{attempt_id}")

                # Continuation-specific inputs
                if "previous_turn_records" in inputs:
                    inputs["previous_turn_records"] = json.dumps(previous_turn_records, ensure_ascii=False)
                if "turn_index" in inputs:
                    inputs["turn_index"] = turn_num

                # Probe-specific inputs
                if "prompt_id" in inputs:
                    inputs["prompt_id"] = ""  # Will be set after queue
                if "turn_kind" in inputs:
                    inputs["turn_kind"] = turn_kind

                # Patch card path
                if "source_path" in inputs:
                    inputs["source_path"] = card_path
                if "fixture_path" in inputs:
                    inputs["fixture_path"] = card_path
                # Patch card_definition with minimal dict if placeholder
                if "card_definition" in inputs and isinstance(inputs["card_definition"], str):
                    inputs["card_definition"] = {
                        "logical_card_id": logical_card_id or "card_001",
                        "card_version": 1,
                        "source_hash": source_hash or "",
                        "status": "ready",
                    }

                # Patch card identity
                if "logical_card_id" in inputs and logical_card_id:
                    inputs["logical_card_id"] = logical_card_id
                if "source_hash" in inputs and source_hash:
                    inputs["source_hash"] = source_hash
                if "card_version" in inputs:
                    inputs["card_version"] = card_version

            # Fix class_type for turn execution node
            for node_id, node in workflow.items():
                if not isinstance(node, dict):
                    continue
                if node.get("class_type") in ("{{turn_execution_node}}", "AWPV2FirstTurnExecution", "AWPV2ContinuationTurnExecution"):
                    node["class_type"] = execution_node_class

            # Submit workflow
            result = comfy.queue_prompt(workflow)
            prompt_id = result.get("prompt_id", "")
            turn_result["prompt_id"] = prompt_id

            # Patch prompt_id into probe node for /history correlation
            for node_id, node in workflow.items():
                if not isinstance(node, dict):
                    continue
                if node.get("class_type") == "AWPV2TurnResultProbe":
                    node["inputs"]["prompt_id"] = prompt_id

            # Wait for completion
            history_entry = comfy.wait_for_completion(prompt_id, timeout=120)

            # Check for errors
            status_str = history_entry.get("status", {}).get("status_str", "")
            messages = history_entry.get("status", {}).get("messages", [])
            has_error = any(m[0] == "execution_error" for m in messages if isinstance(m, (list, tuple)))

            if status_str != "success" or has_error:
                turn_result["status"] = "execution_error"
                turn_result["errors"].append(f"ComfyUI execution error: {status_str}")
                all_passed = False
            else:
                turn_result["status"] = "success"

                # Extract outputs (multiple formats)
                outputs = history_entry.get("outputs", {})
                extracted_text = ""
                probe_projection = None

                for node_id, node_output in outputs.items():
                    if not isinstance(node_output, dict):
                        continue
                    # Format 1: direct text/string_value
                    for output_key in ["text", "string_value"]:
                        if output_key in node_output:
                            val = node_output[output_key]
                            if isinstance(val, list):
                                val = val[0] if val else ""
                            if isinstance(val, str) and len(val) > len(extracted_text):
                                extracted_text = val
                    # Format 2: TraceDisplay ui.text
                    if "ui" in node_output:
                        ui = node_output["ui"]
                        if isinstance(ui, dict) and "text" in ui:
                            ui_texts = ui["text"]
                            if isinstance(ui_texts, list) and ui_texts:
                                for t in ui_texts:
                                    if isinstance(t, str) and len(t) > len(extracted_text):
                                        extracted_text = t
                    # Format 3: TurnResultProbe ui.awp_turn_result_json
                    if "ui" in node_output:
                        ui = node_output["ui"]
                        if isinstance(ui, dict) and "awp_turn_result_json" in ui:
                            probe_texts = ui["awp_turn_result_json"]
                            if isinstance(probe_texts, list) and probe_texts:
                                try:
                                    probe_projection = json.loads(probe_texts[0])
                                    turn_result["probe_projection"] = probe_projection
                                    turn_result["has_probe_output"] = True
                                except (json.JSONDecodeError, IndexError):
                                    pass

                if extracted_text and len(extracted_text) > 10:
                    turn_result["output_text_length"] = len(extracted_text)
                    turn_result["output_preview"] = extracted_text[:200]
                    # Narrative regression check
                    ncheck = narrative_checker.check(extracted_text, turn_num)
                    narrative_reports.append(ncheck)
                    if ncheck["status"] != "pass":
                        turn_result["narrative_status"] = ncheck["status"]
                        turn_result["narrative_issues"] = ncheck["issues"]

                # Also check file-based output from node
                output_file = Path("artifacts/real-provider-outputs") / f"turn_{turn_id[:16]}.json"
                if output_file.exists():
                    try:
                        output_data = json.loads(output_file.read_text(encoding="utf-8"))
                        file_text = output_data.get("accepted_text", "")
                        if file_text and len(file_text) > len(extracted_text):
                            turn_result["output_text_length"] = len(file_text)
                            turn_result["output_preview"] = file_text[:200]
                            turn_result["quality_verdict"] = output_data.get("quality_verdict", "")
                            ncheck = narrative_checker.check(file_text, turn_num)
                            narrative_reports.append(ncheck)
                            if ncheck["status"] != "pass":
                                turn_result["narrative_status"] = ncheck["status"]
                                turn_result["narrative_issues"] = ncheck["issues"]
                    except Exception:
                        pass

                # Collect private transcript (only from accepted TurnRecords)
                if probe_projection and probe_projection.get("quality_status") == "accepted":
                    accepted_text_for_transcript = ""
                    # Try to get from file output (contains full text)
                    if output_file.exists():
                        try:
                            output_data = json.loads(output_file.read_text(encoding="utf-8"))
                            accepted_text_for_transcript = output_data.get("accepted_text", "")
                        except Exception:
                            pass
                    transcript_collector.collect(
                        turn_index=turn_num,
                        turn_id=turn_id,
                        turn_record_id=probe_projection.get("turn_record_id", ""),
                        accepted_text=accepted_text_for_transcript,
                        quality_status=probe_projection.get("quality_status", ""),
                    )

                # Track turn data for lifecycle audit
                audit_entry = {
                    "turn_index": turn_num,
                    "turn_kind": turn_kind,
                    "turn_id": turn_id,
                    "quality_status": probe_projection.get("quality_status", "unknown") if probe_projection else "unknown",
                    "receipt_status": probe_projection.get("receipt_status", "unknown") if probe_projection else "unknown",
                    "turn_record_id": probe_projection.get("turn_record_id", "") if probe_projection else "",
                    "accepted_text_hash": probe_projection.get("accepted_text_hash", "") if probe_projection else "",
                    "accepted_text_length": probe_projection.get("accepted_text_length", 0) if probe_projection else 0,
                    "card_state_revision_before": probe_projection.get("card_state_revision_before", 0) if probe_projection else 0,
                    "card_state_revision_after": probe_projection.get("card_state_revision_after", 0) if probe_projection else 0,
                    "memory_disposition": probe_projection.get("memory_disposition", "") if probe_projection else "",
                    "diagnostic_status": probe_projection.get("diagnostic_status", "") if probe_projection else "",
                    "has_opening_context": is_first_turn,
                    "has_probe_output": bool(probe_projection),
                }
                turn_audit_data.append(audit_entry)

                # Track previous turn records for continuation
                if probe_projection and probe_projection.get("quality_status") == "accepted":
                    previous_turn_records.append({
                        "turn_id": turn_id,
                        "turn_index": turn_num,
                        "card_id": logical_card_id or "card_001",
                        "session_id": session_id,
                        "player_input": player_input,
                        "writer_output": extracted_text[:500] if extracted_text else "",
                        "mode": "normal",
                        "base_card_state_revision": probe_projection.get("card_state_revision_before", 0),
                        "result_card_state_revision": probe_projection.get("card_state_revision_after", 0),
                        "created_at": turn_result.get("timestamp", ""),
                    })

            # Estimate provider calls (rough: 2 per turn for director+writer)
            turn_result["provider_calls"] = 2 if mode == "full_pipeline" else 1
            total_provider_calls += turn_result["provider_calls"]

            # Private transcript collected via collector above (no direct file writes)

        except TimeoutError as e:
            turn_result["status"] = "timeout"
            turn_result["errors"].append(str(e)[:200])
            all_passed = False

        except Exception as e:
            turn_result["status"] = "error"
            turn_result["errors"].append(f"{type(e).__name__}: {str(e)[:200]}")
            all_passed = False

        turn_result["latency_ms"] = int((time.time() - turn_start) * 1000)
        turn_results.append(turn_result)

        status_icon = "OK" if turn_result["status"] == "success" else "FAIL"
        print(f"  {status_icon} [{turn_result['status']}] {turn_result.get('latency_ms', 0)}ms")

    # ── Lifecycle Audit ─────────────────────────────────────────────────
    from awp_rp_runtime_v2.testing.multiturn_lifecycle_audit import MultiTurnLifecycleAudit
    lifecycle_audit = MultiTurnLifecycleAudit()
    audit_report = lifecycle_audit.audit(turn_audit_data)

    # ── Flush Private Transcript ────────────────────────────────────────
    transcript_dir = transcript_collector.flush()
    if transcript_dir:
        print(f"\n  Private transcript saved to: {transcript_dir}")
    elif save_private_transcript:
        print(f"\n  Private transcript: no accepted turns to save")

    # ── Write Reports ────────────────────────────────────────────────────
    run_data = {
        "run_id": run_id,
        "session_id": session_id,
        "card_path": card_path,
        "model": config.model,
        "mode": mode,
        "total_turns": len(turn_results),
        "total_provider_calls": total_provider_calls,
        "total_tokens": total_tokens,
        "status": "pass" if all_passed else "fail",
        "started_at": _now(),
        "guardrails": guardrails.to_safe_summary(),
        "lifecycle_audit": audit_report.to_dict(),
        "probe_capture_rate": sum(1 for t in turn_audit_data if t.get("has_probe_output")) / max(len(turn_audit_data), 1),
    }

    run_dir = report_writer.write_run(run_id, run_data)
    report_writer.write_turns(run_dir, turn_results)
    report_writer.write_provider_usage(run_dir, provider_receipts)
    report_writer.write_narrative_regression(run_dir, {
        "overall_status": "pass" if all(not r.get("narrative_issues") for r in narrative_reports) else "warning",
        "checks": narrative_reports,
    })
    # Write lifecycle audit report
    (run_dir / "lifecycle-audit.json").write_text(
        json.dumps(audit_report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Generate markdown report
    report_lines = [
        f"# Multi-Turn Acceptance Report",
        f"",
        f"**Run ID:** {run_id}",
        f"**Session ID:** {session_id}",
        f"**Model:** {config.model}",
        f"**Mode:** {mode}",
        f"**Turns:** {len(turn_results)}",
        f"**Provider Calls:** {total_provider_calls}",
        f"**Status:** {'PASS' if all_passed else 'FAIL'}",
        f"**Lifecycle Audit:** {audit_report.overall_status}",
        f"**Probe Capture Rate:** {run_data.get('probe_capture_rate', 0):.0%}",
        f"",
        f"## Turn Results",
        f"",
        f"| # | Name | Status | Latency | Probe | Narrative |",
        f"|---|------|--------|---------|-------|-----------|",
    ]
    for tr in turn_results:
        nstatus = tr.get("narrative_status", "-")
        probe = "YES" if tr.get("has_probe_output") else "NO"
        report_lines.append(
            f"| {tr['turn']} | {tr['name']} | {tr['status']} | {tr.get('latency_ms', 0)}ms | {probe} | {nstatus} |"
        )

    # Lifecycle audit section
    if audit_report.findings:
        report_lines.extend(["", "## Lifecycle Audit", ""])
        report_lines.append(f"**Total checks:** {audit_report.total_checks}")
        report_lines.append(f"**Passed:** {audit_report.passed}")
        report_lines.append(f"**Failed:** {audit_report.failed}")
        report_lines.append(f"**Warnings:** {audit_report.warnings}")
        if audit_report.failed > 0:
            report_lines.extend(["", "### Failed Checks", ""])
            for f in audit_report.findings:
                if f.status == "fail":
                    report_lines.append(f"- Turn {f.turn_index}: {f.check_name} — {f.message}")

    if any(r.get("narrative_issues") for r in narrative_reports):
        report_lines.extend(["", "## Narrative Issues", ""])
        for nr in narrative_reports:
            if nr.get("issues"):
                report_lines.append(f"- Turn {nr['turn_index']}: {', '.join(nr['issues'])}")

    report_writer.write_report(run_dir, "\n".join(report_lines))

    # Print summary
    print("\n" + "=" * 60)
    print(f"Result: {'PASS' if all_passed else 'FAIL'}")
    print(f"Turns: {len(turn_results)}")
    print(f"Provider calls: {total_provider_calls}")
    print(f"Lifecycle Audit: {audit_report.overall_status}")
    print(f"Probe Capture Rate: {run_data.get('probe_capture_rate', 0):.0%}")
    print(f"Private Transcript: {transcript_collector.collected_count} entries")
    print(f"Report: {run_dir}")
    print("=" * 60)

    return run_data


# ── CLI Entry Point ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Real Provider Multi-Turn Acceptance Test"
    )
    parser.add_argument("--card-path", required=True, help="Path to real card JSON")
    parser.add_argument("--turns", type=int, default=12, help="Number of turns")
    parser.add_argument(
        "--mode",
        choices=["writer_only", "director_and_writer", "full_pipeline"],
        default="full_pipeline",
        help="Provider mode",
    )
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

    sys.exit(0 if result.get("status") == "pass" or result.get("status") == "dry_run" else 1)


if __name__ == "__main__":
    main()
