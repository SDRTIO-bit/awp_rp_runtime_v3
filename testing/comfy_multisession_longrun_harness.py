"""ComfyUI Multi-Session Long-Run Harness — V1.

Runs multiple independent RP sessions through real ComfyUI /prompt execution,
alternating turn-by-turn, collecting per-turn artifacts, and verifying
cross-session isolation.

Usage (offline):
  python -m awp_rp_runtime_v2.testing.comfy_multisession_longrun_harness `
    --comfy-url "http://127.0.0.1:8188" `
    --card-path "<test_card>" `
    --sessions 2 --turns 20 `
    --director-profile-id "fake-director" `
    --writer-profile-id "fake-writer" `
    --player-profile-id "fake-player" `
    --save-artifacts --mode "debug-full"

Usage (real-acceptance):
  AWP_REAL_LLM_E2E=1 AWP_ALLOW_EXTERNAL_CARD_CONTENT=1 `
  python -m awp_rp_runtime_v2.testing.comfy_multisession_longrun_harness `
    --card-path "<your-card-path>.json" `
    --sessions 2 --turns 20 `
    --director-profile-id "deepseek-v4-pro-director" `
    --writer-profile-id "deepseek-v4-flash-writer" `
    --player-profile-id "simulated-player-v1" `
    --restart-after-turn 10 --restart-mode "runtime" `
    --save-artifacts --real-model
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── ID generation ────────────────────────────────────────────────────────────

def _id(prefix: str, seed: str) -> str:
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:12]}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── CLI ──────────────────────────────────────────────────────────────────────

def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="AWP RP Runtime V2 — Comfy Multi-Session Long-Run Harness V1",
    )
    p.add_argument("--comfy-url", default="http://127.0.0.1:8188",
                   help="ComfyUI base URL")
    p.add_argument("--workflow-dir", default="testing/workflows",
                   help="Directory containing workflow JSON templates")
    p.add_argument("--card-path", required=True,
                   help="Path to character card JSON")
    p.add_argument("--card-b-path", default="",
                   help="Optional second character card for session C")
    p.add_argument("--scenario-dir", default="testing/scenarios",
                   help="Directory containing scenario JSON files")
    p.add_argument("--scenario-a", default="session_a_secret_watch",
                   help="Scenario ID for session A")
    p.add_argument("--scenario-b", default="session_b_silver_bell",
                   help="Scenario ID for session B")
    p.add_argument("--sessions", type=int, default=2,
                   help="Number of independent sessions (2 or 3)")
    p.add_argument("--turns", type=int, default=20,
                   help="Number of turns per session")
    p.add_argument("--director-profile-id", default="fake-director",
                   help="Model profile ID for Director")
    p.add_argument("--writer-profile-id", default="fake-writer",
                   help="Model profile ID for Writer")
    p.add_argument("--player-profile-id", default="fake-player",
                   help="Model profile ID for simulated player")
    p.add_argument("--mode", default="visible",
                   choices=["visible", "debug-full"],
                   help="Player simulator visibility mode")
    p.add_argument("--restart-mode", default="none",
                   choices=["none", "runtime"],
                   help="Restart mode: none or runtime (clear factory cache)")
    p.add_argument("--restart-after-turn", type=int, default=0,
                   help="Perform restart after this turn index (0=never)")
    p.add_argument("--save-artifacts", action="store_true",
                   help="Write per-turn artifact files")
    p.add_argument("--artifact-root", default="artifacts/comfy-multisession-runs",
                   help="Root directory for artifacts")
    p.add_argument("--concurrency", type=int, default=1,
                   help="Max concurrent ComfyUI prompts (V1: must be 1)")
    p.add_argument("--fail-fast", action="store_true",
                   help="Stop all sessions on first failure")
    p.add_argument("--resume-run-id", default="",
                   help="Resume a previous run by run_id")
    p.add_argument("--dry-run", action="store_true",
                   help="Use fake adapter — no real ComfyUI or model calls")
    p.add_argument("--real-model", action="store_true",
                   help="Use real LLM models (requires env vars)")
    p.add_argument("--offline", action="store_true",
                   help="Use offline fake adapter (synonym for --dry-run)")
    return p


# ── Workflow adapter (ComfyUI HTTP) ──────────────────────────────────────────

class ComfyWorkflowAdapter:
    """Submit workflows to ComfyUI /prompt and collect results from /history.

    This is the canonical acceptance path — never calls node classes directly.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8188",
                 timeout_seconds: float = 180.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.base_url}/system_stats", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_object_info(self) -> dict[str, Any]:
        import urllib.request
        req = urllib.request.Request(f"{self.base_url}/object_info", method="GET")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def queue_prompt(self, workflow: dict[str, Any],
                     client_id: str = "") -> dict[str, Any]:
        import urllib.request
        import urllib.error
        cid = client_id or f"awp-harness-{uuid.uuid4().hex[:8]}"
        payload = json.dumps({
            "prompt": workflow,
            "client_id": cid,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/prompt", data=payload,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise EnvironmentError(
                f"ComfyUI /prompt returned HTTP {e.code}: {body[:500]}"
            ) from e

    def get_history(self, prompt_id: str) -> dict[str, Any] | None:
        import urllib.request
        try:
            req = urllib.request.Request(
                f"{self.base_url}/history/{prompt_id}", method="GET"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None

    def wait_for_completion(self, prompt_id: str) -> dict[str, Any]:
        """Poll /history until prompt completes or timeout."""
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            history = self.get_history(prompt_id)
            if history and prompt_id in history:
                return history[prompt_id]
            time.sleep(2.0)
        raise TimeoutError(
            f"Prompt {prompt_id} did not complete in {self.timeout_seconds}s"
        )

    def submit_and_wait(self, workflow: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Submit a workflow and wait for completion.

        Returns (prompt_id, history_entry).
        """
        result = self.queue_prompt(workflow)
        prompt_id = result.get("prompt_id", "")
        if not prompt_id:
            raise EnvironmentError("ComfyUI did not return a prompt_id")
        entry = self.wait_for_completion(prompt_id)
        return prompt_id, entry


class FakeComfyWorkflowAdapter(ComfyWorkflowAdapter):
    """Offline adapter — returns simulated ComfyUI responses.

    Uses the real node classes but intercepts at the workflow adapter level.
    This allows testing workflow construction, payload correctness, and artifact
    collection without a running ComfyUI instance.
    """

    def __init__(self) -> None:
        super().__init__("http://fake.invalid", timeout_seconds=10)

    def is_available(self) -> bool:
        return True

    def queue_prompt(self, workflow: dict[str, Any], client_id: str = "") -> dict[str, Any]:
        return {"prompt_id": f"fake-{uuid.uuid4().hex[:16]}", "number": 1}

    def get_history(self, prompt_id: str) -> dict[str, Any] | None:
        return None

    def wait_for_completion(self, prompt_id: str) -> dict[str, Any]:
        return {}

    def submit_and_wait(self, workflow: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        prompt_id = f"fake-{uuid.uuid4().hex[:16]}"
        return prompt_id, {
            "prompt_id": prompt_id,
            "status": {"status_str": "success", "messages": []},
            "outputs": {},
        }


# ── Turn result extraction ───────────────────────────────────────────────────

def extract_probe_from_history(history_entry: dict[str, Any]) -> dict | None:
    """Extract TurnResultProjection from a ComfyUI /history entry."""
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


def extract_text_from_history(history_entry: dict[str, Any]) -> str:
    """Extract writer output text (best effort) from /history."""
    outputs = history_entry.get("outputs", {})
    best = ""
    for node_id, node_output in outputs.items():
        if not isinstance(node_output, dict):
            continue
        # Check TraceDisplay text
        ui = node_output.get("ui", {})
        if isinstance(ui, dict) and "text" in ui:
            for t in (ui["text"] if isinstance(ui["text"], list) else []):
                if isinstance(t, str) and len(t) > len(best):
                    best = t
        # Check raw text fields
        for key in ("text", "output", "result"):
            val = node_output.get(key, "")
            if isinstance(val, str) and len(val) > len(best):
                best = val
    return best


# ── Workflow builder ─────────────────────────────────────────────────────────

class WorkflowBuilder:
    """Load and patch workflow templates with session/turn-specific values."""

    def __init__(self, workflow_dir: str | Path) -> None:
        self.workflow_dir = Path(workflow_dir)

    def load_template(self, name: str) -> dict[str, Any]:
        path = self.workflow_dir / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Workflow template not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def patch(self, template: dict[str, Any], variables: dict[str, str]) -> dict[str, Any]:
        """Deep-copy template and replace {{var}} placeholders with values."""
        variables = {
            "writer_preset_path": "",
            **variables,
        }
        raw = json.dumps(template, ensure_ascii=False)
        for key, val in variables.items():
            raw = raw.replace("{{" + key + "}}", str(val))
        return json.loads(raw)

    def build_first_turn(self, variables: dict[str, str]) -> dict[str, Any]:
        template = self.load_template("persistent_rp_long_session_first_turn_api")
        return self.patch(template, variables)

    def build_continuation_turn(self, variables: dict[str, str]) -> dict[str, Any]:
        template = self.load_template("persistent_rp_long_session_continuation_turn_api")
        return self.patch(template, variables)


# ── Per-turn artifact ────────────────────────────────────────────────────────

def build_turn_artifact(
    turn_index: int,
    session_id: str,
    turn_id: str,
    request_id: str,
    prompt_id: str,
    player_input: str,
    player_intent: str,
    writer_output: str,
    probe: dict | None,
    trace_id: str,
    trace_summary: dict[str, Any],
    node_statuses: dict[str, str],
    l1_turn_ids: list[str],
    l2_memory_ids: list[str],
    l3_memory_ids: list[str],
    worldbook_entry_ids: list[str],
    card_state_rev_before: int,
    card_state_rev_after: int,
    turn_record_id: str,
    memory_commit_ids: list[str],
    quality_verdict: str,
    director_profile: str,
    writer_profile: str,
    player_profile: str,
    director_model: str,
    writer_model: str,
    player_model: str,
    latency_ms: int,
    error_info: dict[str, Any] | None,
    memory_recall_status: str = "N/A",
    fact_source: str = "N/A",
    checkpoint_kind: str = "",
) -> dict[str, Any]:
    return {
        "turn_index": turn_index,
        "session_id": session_id,
        "turn_id": turn_id,
        "request_id": request_id,
        "prompt_id": prompt_id,
        "player_input": player_input,
        "player_intent": player_intent,
        "writer_output": writer_output,
        "turn_result_probe": probe,
        "trace_id": trace_id,
        "trace_summary": trace_summary,
        "node_execution_statuses": node_statuses,
        "l1_turn_ids": l1_turn_ids,
        "l2_memory_ids": l2_memory_ids,
        "l3_memory_ids": l3_memory_ids,
        "worldbook_entry_ids": worldbook_entry_ids,
        "card_state_revision_before": card_state_rev_before,
        "card_state_revision_after": card_state_rev_after,
        "turn_record_id": turn_record_id,
        "memory_commit_ids": memory_commit_ids,
        "quality_verdict": quality_verdict,
        "director_profile": director_profile,
        "writer_profile": writer_profile,
        "player_simulator_profile": player_profile,
        "director_model": director_model,
        "writer_model": writer_model,
        "player_model": player_model,
        "latency_ms": latency_ms,
        "error_info": error_info,
        "memory_recall_status": memory_recall_status,
        "fact_source": fact_source,
        "checkpoint_kind": checkpoint_kind,
        "collected_at": _now(),
    }


# ── Simulated player driver ──────────────────────────────────────────────────

class SimulatedPlayerDriver:
    """Drives the simulated player for multi-session harness.

    Reads the scenario, the last turn's output, and generates the next input.
    Supports retry on empty output.
    """

    MAX_RETRIES = 2

    def __init__(
        self,
        profile_id: str,
        mode: str = "debug-full",
        scenario: dict[str, Any] | None = None,
    ) -> None:
        self.profile_id = profile_id
        self.mode = mode
        self.scenario = scenario or {}
        self.own_history: list[str] = []
        self.is_fake = profile_id.startswith("fake-")

    def get_next_input(
        self,
        turn_index: int,
        last_writer_output: str,
        debug_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate the next player input.

        Returns dict with player_input, action_intent, verify_tag, success, etc.
        """
        try:
            from .simulated_player_agent import (
                SimulatedPlayerAgent,
                PlayerSimulatorInput,
            )
        except ImportError:
            try:
                from testing.simulated_player_agent import (
                    SimulatedPlayerAgent,
                    PlayerSimulatorInput,
                )
            except ImportError:
                # Standalone fallback: use inline fake player
                return self._inline_fake_input(turn_index)

        checkpoints = self.scenario.get("checkpoints", [])
        relevant = [c for c in checkpoints if c.get("turn") == turn_index]

        psin = PlayerSimulatorInput(
            turn_index=turn_index,
            persona=self.scenario.get("player_persona", "一名玩家"),
            goal=self.scenario.get("global_goal", "推进剧情"),
            last_writer_output=last_writer_output,
            own_history=list(self.own_history),
            planned_checkpoints=[c.get("prompt_goal", "") for c in relevant],
            required_facts=self.scenario.get("required_facts", []),
            debug_context=debug_context or {},
        )

        agent = SimulatedPlayerAgent(self.profile_id, self.mode)
        last_error = None

        for retry in range(self.MAX_RETRIES + 1):
            output = agent.run(psin)
            if output.success and output.player_input.strip():
                self.own_history.append(output.player_input)
                return {
                    "player_input": output.player_input,
                    "action_intent": output.action_intent,
                    "verify_tag": output.verify_tag,
                    "success": True,
                    "retries": retry,
                    "profile_id": self.profile_id,
                    "model": output.model,
                    "provider": output.provider,
                    "latency_ms": output.latency_ms,
                }
            last_error = {
                "failure_code": output.failure_code,
                "failure_message": output.failure_message,
                "retry": retry,
            }
            if output.player_input and not output.player_input.strip():
                # Empty output — retry
                continue

        return {
            "player_input": "",
            "action_intent": "",
            "verify_tag": "",
            "success": False,
            "retries": self.MAX_RETRIES,
            "profile_id": self.profile_id,
            "model": "",
            "provider": "",
            "latency_ms": 0,
            "error": last_error,
        }

    def _inline_fake_input(self, turn_index: int) -> dict[str, Any]:
        """Generate fake player input when SimulatedPlayerAgent is not importable."""
        fake_lines = [
            "你好，请带我看看这里。",
            "我答应你，明天一定再来拜访。",
            "我们之前说好的事情，你还记得吗？",
            "我想了解更多关于这个地方的传说。",
            "刚才那位老者还在吗？我有事找他。",
            "你能告诉我村长住在哪里吗？",
            "天色不早了，我该走了，明天见。",
            "我们之间的关系，你怎么看？",
            "这件事我要保守秘密，对吧？",
            "最后再确认一次，我们之间的约定。",
        ]
        idx = (turn_index - 1) % len(fake_lines)
        player_input = fake_lines[idx]
        self.own_history.append(player_input)
        return {
            "player_input": player_input,
            "action_intent": "advance",
            "verify_tag": "free" if turn_index not in (2, 5, 8, 10) else "probe",
            "success": True,
            "retries": 0,
            "profile_id": self.profile_id,
            "model": "fake_player_v1",
            "provider": "standalone_fallback",
            "latency_ms": 0,
        }


# ── Session runner ───────────────────────────────────────────────────────────

class SessionState:
    """Mutable state for one RP session during a long run."""

    def __init__(self, label: str, session_id: str, scenario: dict[str, Any],
                 card_path: str) -> None:
        self.label = label
        self.session_id = session_id
        self.scenario = scenario
        self.card_path = card_path
        self.turn_count: int = 0
        self.last_writer_output: str = ""
        self.last_probe: dict | None = None
        self.last_revision: int = 0
        self.failed: bool = False
        self.failure_reason: str = ""
        self.bootstrap_done: bool = False
        self.artifacts: list[dict[str, Any]] = []


class MultiSessionLongRunHarness:
    """Orchestrates multi-session long-run acceptance testing."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.run_id = args.resume_run_id or f"run-{int(time.time() * 1000)}"
        self.artifact_root = Path(args.artifact_root) / self.run_id
        self.scenario_dir = Path(args.scenario_dir)
        self.sessions: dict[str, SessionState] = {}
        self.is_dry_run = args.dry_run or args.offline
        self.is_real_model = args.real_model

        # Mode determination
        if self.is_dry_run:
            self.effective_mode = "offline"
        elif self.is_real_model:
            self.effective_mode = "real-acceptance" if args.turns >= 20 else "real-smoke"
        else:
            self.effective_mode = "real-smoke"

        # Adapter
        if self.is_dry_run:
            self.adapter: ComfyWorkflowAdapter = FakeComfyWorkflowAdapter()
        else:
            self.adapter = ComfyWorkflowAdapter(args.comfy_url)

        self.workflow_builder = WorkflowBuilder(args.workflow_dir)

    # ── entry point ──────────────────────────────────────────────────────

    def run(self) -> int:
        """Run the complete multi-session long-run. Returns exit code."""
        self._print_header()

        # Pre-flight checks
        if not self._preflight():
            return 1

        # Initialize sessions
        self._init_sessions()

        # Bootstrap all sessions
        if not self._bootstrap_all():
            if self.args.fail_fast:
                return 1

        # Run the alternating turn loop
        self._run_turn_loop()

        # Save artifacts
        if self.args.save_artifacts:
            self._save_artifacts()

        # Cross-session audit
        audit = self._run_audit()

        # Final report
        self._print_final_report(audit)

        return 0 if audit.get("passed_all", False) else 1

    # ── preflight ────────────────────────────────────────────────────────

    def _preflight(self) -> bool:
        print("Pre-flight checks...")

        # Card path
        card_path = Path(self.args.card_path)
        if not card_path.exists():
            print(f"  [FAIL] Card not found: {self.args.card_path}")
            return False
        print(f"  [PASS] Card exists: {card_path}")

        # Workflow templates
        wf_dir = Path(self.args.workflow_dir)
        for name in ["persistent_rp_long_session_first_turn_api",
                      "persistent_rp_long_session_continuation_turn_api"]:
            if not (wf_dir / f"{name}.json").exists():
                print(f"  [FAIL] Workflow template missing: {name}.json")
                return False
        print(f"  [PASS] Workflow templates found")

        # Scenario files
        scenario_dir = Path(self.args.scenario_dir)
        for sid in [self.args.scenario_a, self.args.scenario_b]:
            if not (scenario_dir / f"{sid}.json").exists():
                print(f"  [FAIL] Scenario missing: {sid}.json")
                return False
        print(f"  [PASS] Scenario files found")

        # Real model env check
        if self.is_real_model:
            if not os.environ.get("DEEPSEEK_API_KEY"):
                print("  [FAIL] --real-model requires DEEPSEEK_API_KEY env var")
                return False
            if not os.environ.get("AWP_REAL_LLM_E2E"):
                print("  [WARN] AWP_REAL_LLM_E2E not set (recommended)")
            if not os.environ.get("AWP_ALLOW_EXTERNAL_CARD_CONTENT"):
                print("  [WARN] AWP_ALLOW_EXTERNAL_CARD_CONTENT not set (recommended)")

        # ComfyUI check (skip for dry-run)
        if not self.is_dry_run:
            if not self.adapter.is_available():
                print(f"  [FAIL] ComfyUI not reachable at {self.args.comfy_url}")
                return False
            print(f"  [PASS] ComfyUI available at {self.args.comfy_url}")

            # Check required nodes
            obj_info = self.adapter.get_object_info()
            required = ["AWPV2PersistentBootstrap", "AWPV2PersistentFirstTurn",
                         "AWPV2PersistentContinuationTurn", "AWPV2TurnResultProbe"]
            missing = [n for n in required if n not in obj_info]
            if missing:
                print(f"  [FAIL] Missing nodes: {missing}")
                return False
            print(f"  [PASS] All required nodes registered ({len(required)})")

        return True

    # ── session init ─────────────────────────────────────────────────────

    def _init_sessions(self) -> None:
        print("\nInitializing sessions...")

        # Load scenarios
        with open(self.scenario_dir / f"{self.args.scenario_a}.json", "r", encoding="utf-8") as f:
            scenario_a = json.load(f)
        with open(self.scenario_dir / f"{self.args.scenario_b}.json", "r", encoding="utf-8") as f:
            scenario_b = json.load(f)

        # Create session states
        ts = int(time.time() * 1000)
        self.sessions["A"] = SessionState(
            label="A",
            session_id=f"sess-A-{self.run_id}-{ts}",
            scenario=scenario_a,
            card_path=self.args.card_path,
        )
        self.sessions["B"] = SessionState(
            label="B",
            session_id=f"sess-B-{self.run_id}-{ts + 1}",
            scenario=scenario_b,
            card_path=self.args.card_b_path or self.args.card_path,
        )
        # Optional session C
        if self.args.sessions >= 3 and self.args.card_b_path:
            self.sessions["C"] = SessionState(
                label="C",
                session_id=f"sess-C-{self.run_id}-{ts + 2}",
                scenario=scenario_b,
                card_path=self.args.card_b_path,
            )

        for label, s in self.sessions.items():
            print(f"  Session {label}: {s.session_id} (card={s.card_path})")

    # ── bootstrap ────────────────────────────────────────────────────────

    def _bootstrap_all(self) -> bool:
        print("\nBootstrapping sessions...")
        all_ok = True
        for label, s in self.sessions.items():
            ok = self._bootstrap_session(s)
            all_ok = all_ok and ok
        return all_ok

    def _bootstrap_session(self, s: SessionState) -> bool:
        """Bootstrap a single session via ComfyUI /prompt."""
        print(f"  Session {s.label} ({s.session_id}): bootstrapping...")
        try:
            variables = {
                "card_path": s.card_path,
                "session_id": s.session_id,
                "request_id": f"req-bootstrap-{s.session_id}",
                "run_id": self.run_id,
                "workflow_run_id": f"wfr-bootstrap-{s.session_id}",
                "trace_id": f"trc-bootstrap-{s.session_id}",
                "player_input": "",
                "turn_id": f"turn-0-{s.session_id}",
                "attempt_id": "attempt-0",
                "director_profile_id": self.args.director_profile_id,
                "writer_profile_id": self.args.writer_profile_id,
                "prompt_id": "",
            }

            if self.is_dry_run:
                # Dry run: simulate bootstrap
                s.bootstrap_done = True
                print(f"    [DRY] Bootstrap simulated OK")
                return True

            workflow = self.workflow_builder.build_first_turn(variables)
            prompt_id, entry = self.adapter.submit_and_wait(workflow)

            status = entry.get("status", {}).get("status_str", "unknown")
            ok = status == "success"
            if ok:
                s.bootstrap_done = True
                print(f"    [PASS] Bootstrap OK (prompt_id={prompt_id[:16]}...)")
            else:
                s.failed = True
                s.failure_reason = f"Bootstrap failed: status={status}"
                print(f"    [FAIL] Bootstrap failed: status={status}")
            return ok

        except Exception as e:
            s.failed = True
            s.failure_reason = f"Bootstrap error: {e}"
            print(f"    [FAIL] Bootstrap error: {e}")
            return False

    # ── turn loop ────────────────────────────────────────────────────────

    def _run_turn_loop(self) -> None:
        total_turns = self.args.turns
        restart_at = self.args.restart_after_turn
        active_sessions = {k: s for k, s in self.sessions.items() if not s.failed}

        print(f"\nRunning {total_turns} turns × {len(active_sessions)} sessions...")
        print(f"  Mode: {self.effective_mode}")
        print(f"  Restart after turn: {restart_at}" if restart_at else "  No restart")

        for turn_num in range(1, total_turns + 1):
            print(f"\n{'─' * 50}")
            print(f"Turn {turn_num}/{total_turns}")

            # Restart checkpoint
            if restart_at and turn_num == restart_at + 1:
                self._do_runtime_restart()

            for label, s in list(active_sessions.items()):
                if s.failed:
                    continue
                try:
                    self._execute_turn(turn_num, s)
                except Exception as e:
                    s.failed = True
                    s.failure_reason = f"Turn {turn_num} exception: {e}"
                    print(f"  Session {label}: [FAIL] {e}")
                    if self.args.fail_fast:
                        return

            # Remove failed sessions
            active_sessions = {k: s for k, s in active_sessions.items() if not s.failed}
            if not active_sessions:
                print("\n  All sessions failed.")
                return

        # Record turn counts
        for s in self.sessions.values():
            s.turn_count = len(s.artifacts)

    def _execute_turn(self, turn_num: int, s: SessionState) -> None:
        """Execute one turn for one session."""
        label = s.label
        turn_id = f"turn-{turn_num}-{s.session_id}"
        request_id = f"req-{turn_id}"
        trace_id = f"trc-{turn_id}"
        wfr_id = f"wfr-{turn_id}"

        # ── 1. Identify checkpoint ───────────────────────────────────────
        checkpoints = s.scenario.get("checkpoints", [])
        checkpoint = next((c for c in checkpoints if c.get("turn") == turn_num), None)
        checkpoint_kind = checkpoint.get("kind", "") if checkpoint else ""
        checkpoint_goal = checkpoint.get("prompt_goal", "") if checkpoint else ""

        # ── 2. Simulated player generates input ──────────────────────────
        dbg_ctx = self._build_debug_context(s) if self.args.mode == "debug-full" else {}
        player_driver = SimulatedPlayerDriver(
            self.args.player_profile_id, self.args.mode, s.scenario
        )
        player_driver.own_history = [
            art.get("player_input", "") for art in s.artifacts
        ]

        # If checkpoint provides a specific prompt goal, use it as primary input hint
        player_result = player_driver.get_next_input(
            turn_num, s.last_writer_output, dbg_ctx
        )

        if not player_result["success"]:
            print(f"  Session {label} T{turn_num}: player simulator failed — "
                  f"{player_result.get('error', {}).get('failure_code', 'unknown')}")
            s.failed = True
            s.failure_reason = f"Player simulator failed at turn {turn_num}"
            return

        player_input = player_result["player_input"]
        if checkpoint_goal and checkpoint_kind in ("establish_fact",):
            # Inject the checkpoint goal into the player's action
            player_input = checkpoint_goal

        # ── 3. Build and submit workflow ─────────────────────────────────
        variables = {
            "session_id": s.session_id,
            "player_input": player_input,
            "turn_id": turn_id,
            "attempt_id": "attempt-0",
            "request_id": request_id,
            "run_id": self.run_id,
            "workflow_run_id": wfr_id,
            "trace_id": trace_id,
            "director_profile_id": self.args.director_profile_id,
            "writer_profile_id": self.args.writer_profile_id,
            "prompt_id": "",
        }

        if self.is_dry_run:
            # Simulate a successful turn
            self._simulate_turn(s, turn_num, player_result, turn_id, request_id, trace_id)
            return

        start_time = time.monotonic()
        if turn_num == 1:
            workflow = self.workflow_builder.build_first_turn(variables)
        else:
            workflow = self.workflow_builder.build_continuation_turn(variables)

        try:
            prompt_id, entry = self.adapter.submit_and_wait(workflow)
        except Exception as e:
            print(f"  Session {label} T{turn_num}: workflow failed — {e}")
            s.failed = True
            s.failure_reason = f"Workflow submission failed: {e}"
            return

        latency_ms = int((time.monotonic() - start_time) * 1000)
        status = entry.get("status", {}).get("status_str", "unknown")

        # ── 4. Extract results ────────────────────────────────────────────
        probe = extract_probe_from_history(entry)
        writer_output = extract_text_from_history(entry)

        # Handle failure
        error_info = None
        if status != "success":
            messages = entry.get("status", {}).get("messages", [])
            error_events = [m for m in messages if m[0] == "execution_error"]
            error_info = {
                "status": status,
                "error_events": [{"node": m[1].get("node_id", ""),
                                  "error": str(m[1].get("error", ""))[:300]}
                                 for m in error_events],
            }
            if self.args.fail_fast:
                s.failed = True
                s.failure_reason = f"Turn {turn_num} failed: status={status}"
            # Even on failure, collect what we have
            probe = probe or {}

        # ── 5. Collect artifact ──────────────────────────────────────────
        artifact = build_turn_artifact(
            turn_index=turn_num,
            session_id=s.session_id,
            turn_id=turn_id,
            request_id=request_id,
            prompt_id=prompt_id if not self.is_dry_run else f"fake-{uuid.uuid4().hex[:8]}",
            player_input=player_input,
            player_intent=player_result.get("action_intent", ""),
            writer_output=writer_output,
            probe=probe,
            trace_id=trace_id,
            trace_summary={
                "status": status,
                "prompt_id": prompt_id,
            },
            node_statuses={"workflow": status},
            l1_turn_ids=probe.get("l1_turn_ids", []) if probe else [],
            l2_memory_ids=probe.get("l2_memory_ids", []) if probe else [],
            l3_memory_ids=probe.get("l3_memory_ids", []) if probe else [],
            worldbook_entry_ids=probe.get("worldbook_activated_entry_ids", []) if probe else [],
            card_state_rev_before=probe.get("card_state_revision_before", 0) if probe else s.last_revision,
            card_state_rev_after=probe.get("card_state_revision_after", 0) if probe else 0,
            turn_record_id=probe.get("turn_record_id", "") if probe else "",
            memory_commit_ids=probe.get("memory_commit_ids", []) if probe else [],
            quality_verdict=probe.get("quality_status", "") if probe else "",
            director_profile=self.args.director_profile_id,
            writer_profile=self.args.writer_profile_id,
            player_profile=self.args.player_profile_id,
            director_model=probe.get("provider_usage_summary", {}).get("director_model", "") if probe else "",
            writer_model=probe.get("provider_usage_summary", {}).get("writer_model", "") if probe else "",
            player_model=player_result.get("model", ""),
            latency_ms=latency_ms,
            error_info=error_info,
            checkpoint_kind=checkpoint_kind,
        )
        s.artifacts.append(artifact)

        # ── 6. Update session state ──────────────────────────────────────
        s.last_writer_output = writer_output
        s.last_probe = probe
        if probe:
            s.last_revision = probe.get("card_state_revision_after", 0)

        idem = probe.get("idempotency_status", "?") if probe else "?"
        fail_flag = " [FAIL]" if error_info else ""
        print(f"  Session {label} T{turn_num}: status={status} "
              f"idem={idem} rev={s.last_revision} "
              f"text_len={probe.get('accepted_text_length', 0) if probe else 0}"
              f" latency={latency_ms}ms{fail_flag}")

    def _simulate_turn(
        self, s: SessionState, turn_num: int,
        player_result: dict[str, Any],
        turn_id: str, request_id: str, trace_id: str,
    ) -> None:
        """Create a simulated turn artifact for dry-run mode."""
        fake_probe = {
            "turn_id": turn_id,
            "session_id": s.session_id,
            "turn_index": turn_num,
            "turn_kind": "first" if turn_num == 1 else "continuation",
            "quality_status": "accepted",
            "receipt_status": "committed",
            "idempotency_status": "fresh",
            "card_state_revision_before": s.last_revision,
            "card_state_revision_after": s.last_revision + 1,
            "accepted_text_hash": hashlib.sha256(b"fake output").hexdigest(),
            "accepted_text_length": 80,
            "memory_disposition": "noop",
            "turn_record_id": turn_id,
        }
        s.last_revision = fake_probe["card_state_revision_after"]

        artifact = build_turn_artifact(
            turn_index=turn_num,
            session_id=s.session_id,
            turn_id=turn_id,
            request_id=request_id,
            prompt_id=f"fake-{uuid.uuid4().hex[:8]}",
            player_input=player_result.get("player_input", ""),
            player_intent=player_result.get("action_intent", ""),
            writer_output=f"[DRY RUN] Simulated writer output for turn {turn_num}",
            probe=fake_probe,
            trace_id=trace_id,
            trace_summary={"simulated": True},
            node_statuses={"workflow": "simulated"},
            l1_turn_ids=[],
            l2_memory_ids=[],
            l3_memory_ids=[],
            worldbook_entry_ids=[],
            card_state_rev_before=fake_probe["card_state_revision_before"],
            card_state_rev_after=fake_probe["card_state_revision_after"],
            turn_record_id=turn_id,
            memory_commit_ids=[],
            quality_verdict="accepted",
            director_profile=self.args.director_profile_id,
            writer_profile=self.args.writer_profile_id,
            player_profile=self.args.player_profile_id,
            director_model="fake",
            writer_model="fake",
            player_model="fake",
            latency_ms=1,
            error_info=None,
            checkpoint_kind="simulated",
        )
        s.artifacts.append(artifact)
        print(f"  Session {s.label} T{turn_num}: [DRY] simulated "
              f"rev={s.last_revision}")

    # ── restart ──────────────────────────────────────────────────────────

    def _do_runtime_restart(self) -> None:
        """Clear the RuntimeStoreFactory registry cache (simulated restart)."""
        print("\n  ═══ Runtime Restart (clear registry cache) ═══")
        try:
            try:
                from ..runtime.runtime_store_factory import clear_registry_cache
            except ImportError:
                from awp_rp_runtime_v2.runtime.runtime_store_factory import clear_registry_cache
            clear_registry_cache()
            print("  Registry cache cleared. New factory will be created next access.")
        except ImportError:
            print("  [WARN] Could not import clear_registry_cache — skipping")

    # ── debug context ────────────────────────────────────────────────────

    def _build_debug_context(self, s: SessionState) -> dict[str, Any]:
        """Build a redacted debug context for debug-full player mode."""
        ctx: dict[str, Any] = {}
        if s.last_probe:
            ctx["card_state_summary"] = (
                f"rev={s.last_probe.get('card_state_revision_after', 0)}"
            )
            ctx["quality_verdict"] = s.last_probe.get("quality_status", "")
            ctx["l1_turn_ids"] = s.last_probe.get("l1_turn_ids", [])
            ctx["l2_memory_summaries"] = [
                f"{mid}:..." for mid in s.last_probe.get("l2_memory_ids", [])[:5]
            ]
            ctx["l3_memory_summaries"] = [
                f"{mid}:..." for mid in s.last_probe.get("l3_memory_ids", [])[:5]
            ]
            ctx["worldbook_summaries"] = s.last_probe.get(
                "worldbook_activated_entry_ids", []
            )[:5]
            ctx["last_trace_summary"] = (
                f"idem={s.last_probe.get('idempotency_status', '')}, "
                f"quality={s.last_probe.get('quality_status', '')}"
            )
        return ctx

    # ── artifacts ────────────────────────────────────────────────────────

    def _save_artifacts(self) -> None:
        print("\nSaving artifacts...")
        self.artifact_root.mkdir(parents=True, exist_ok=True)

        # Write run manifest
        manifest = {
            "run_id": self.run_id,
            "mode": self.effective_mode,
            "config": {
                "comfy_url": self.args.comfy_url if not self.is_dry_run else "fake",
                "card_path": self.args.card_path,
                "sessions": self.args.sessions,
                "turns": self.args.turns,
                "director_profile": self.args.director_profile_id,
                "writer_profile": self.args.writer_profile_id,
                "player_profile": self.args.player_profile_id,
                "restart_mode": self.args.restart_mode,
                "restart_after_turn": self.args.restart_after_turn,
                "real_model": self.is_real_model,
                "dry_run": self.is_dry_run,
            },
            "started_at": _now(),
            "sessions": {},
        }

        for label, s in self.sessions.items():
            session_dir = self.artifact_root / "sessions" / f"session-{label}"
            session_dir.mkdir(parents=True, exist_ok=True)

            # Write per-turn artifacts
            for art in s.artifacts:
                turn_file = session_dir / f"turn-{art['turn_index']:03d}.json"
                with open(turn_file, "w", encoding="utf-8") as f:
                    json.dump(art, f, ensure_ascii=False, indent=2)

            # Write session summary
            summary = {
                "session_id": s.session_id,
                "label": label,
                "card_path": s.card_path,
                "turn_count": len(s.artifacts),
                "failed": s.failed,
                "failure_reason": s.failure_reason,
                "last_revision": s.last_revision,
            }
            with open(session_dir / "summary.json", "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)

            manifest["sessions"][f"session-{label}"] = summary

        # Write scenario copies
        scenarios_dir = self.artifact_root / "scenarios"
        scenarios_dir.mkdir(parents=True, exist_ok=True)
        for label, s in self.sessions.items():
            with open(scenarios_dir / f"session-{label}.json", "w", encoding="utf-8") as f:
                json.dump(s.scenario, f, ensure_ascii=False, indent=2)

        # Write workflow manifest
        wf_manifest = {
            "first_turn_template": "persistent_rp_long_session_first_turn_api.json",
            "continuation_turn_template": "persistent_rp_long_session_continuation_turn_api.json",
        }
        with open(self.artifact_root / "workflow_manifest.json", "w", encoding="utf-8") as f:
            json.dump(wf_manifest, f, ensure_ascii=False, indent=2)

        with open(self.artifact_root / "run_manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        print(f"  Artifacts saved to: {self.artifact_root}")

    # ── audit ────────────────────────────────────────────────────────────

    def _run_audit(self) -> dict[str, Any]:
        print("\nRunning cross-session isolation audit...")
        try:
            from .cross_session_audit import run_cross_session_audit
        except ImportError:
            from testing.cross_session_audit import run_cross_session_audit
        audit = run_cross_session_audit(self.artifact_root)
        if self.args.save_artifacts:
            with open(self.artifact_root / "cross_session_audit.json", "w", encoding="utf-8") as f:
                json.dump(audit, f, ensure_ascii=False, indent=2)
        return audit

    # ── final report ─────────────────────────────────────────────────────

    def _print_header(self) -> None:
        print("=" * 60)
        print("AWP RP Runtime V2 — Comfy Multi-Session Long-Run Harness V1")
        print("=" * 60)
        print(f"  Run ID: {self.run_id}")
        print(f"  Mode:   {self.effective_mode}")
        print(f"  Turns:  {self.args.turns} × {self.args.sessions} sessions")
        print(f"  Comfy:  {self.args.comfy_url if not self.is_dry_run else 'DRY-RUN'}")
        print("=" * 60)

    def _print_final_report(self, audit: dict[str, Any]) -> None:
        print("\n" + "=" * 60)
        print("FINAL REPORT")
        print("=" * 60)

        total_turns = sum(len(s.artifacts) for s in self.sessions.values())
        failed_sessions = [s for s in self.sessions.values() if s.failed]

        print(f"  Sessions: {len(self.sessions)}")
        print(f"  Total turns executed: {total_turns}")
        print(f"  Failed sessions: {len(failed_sessions)}")
        for s in failed_sessions:
            print(f"    - {s.label}: {s.failure_reason[:120]}")

        print(f"\n  Cross-session audit: "
              f"{audit['passed']}/{audit['total_checks']} checks passed")

        if audit["findings"]:
            for f in audit["findings"]:
                icon = "PASS" if f["passed"] else "FAIL"
                print(f"    [{icon}] {f['check_id']}: {f['detail'][:120]}")

        # Memory recall summary
        print("\n  Memory recall summary:")
        for label, s in self.sessions.items():
            recall_statuses = set()
            for art in s.artifacts:
                rs = art.get("memory_recall_status", "N/A")
                if rs != "N/A":
                    recall_statuses.add(rs)
            print(f"    Session {label}: {recall_statuses or {'N/A'}} "
                  f"({len(s.artifacts)} turns)")

        # Conclusion
        all_sessions_ok = len(failed_sessions) == 0
        audit_ok = audit.get("passed_all", False)
        has_real_turns = self.is_real_model and not self.is_dry_run

        print("\n  Conclusion:")
        if all_sessions_ok and audit_ok:
            if has_real_turns:
                print("    ACCEPT_AND_FREEZE — all sessions passed, audit clean")
            else:
                print("    ACCEPT_AND_FREEZE — offline/mock verification passed")
        elif all_sessions_ok and not audit_ok:
            print("    ACCEPT_WITH_LIMITATIONS — sessions OK but audit found issues")
        else:
            print("    REJECT_AND_FIX — one or more sessions failed")

        print("=" * 60)


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = build_argparser()
    args = parser.parse_args(argv)

    # Set env for runtime
    if "AWP_RUNTIME_PROFILE" not in os.environ:
        os.environ["AWP_RUNTIME_PROFILE"] = "test"
    if "AWP_TEST_RUNTIME_NAMESPACE" not in os.environ:
        os.environ["AWP_TEST_RUNTIME_NAMESPACE"] = f"multi-{int(time.time())}"

    harness = MultiSessionLongRunHarness(args)
    return harness.run()


def _ensure_on_path() -> None:
    """Add the project root to sys.path so the harness can be run directly."""
    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    # Also add ComfyUI custom_nodes parent if needed
    custom_nodes_root = str(Path(__file__).resolve().parent.parent.parent)
    if custom_nodes_root not in sys.path:
        sys.path.insert(0, custom_nodes_root)


if __name__ == "__main__":
    _ensure_on_path()
    sys.exit(main())
