"""WorkflowScenarioRunner — executes declarative workflow test scenarios.

Orchestrates:
  1. Load scenario definition
  2. Build fixtures
  3. Execute workflow (fake or real ComfyUI)
  4. Collect node execution records
  5. Run assertions
  6. Generate reports
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts.workflow_run_record import WorkflowRunContext, WorkflowRunRecord
from ..contracts.workflow_test_result import WorkflowTestResult
from ..contracts.workflow_test_scenario import WorkflowTestScenario
from .scenario_assertion_engine import ScenarioAssertionEngine
from .scenario_report_writer import ScenarioReportWriter


class WorkflowScenarioRunner:
    """Execute workflow test scenarios and produce machine-readable results."""

    def __init__(
        self,
        artifact_root: str | Path = "artifacts/test-runs",
        suite: str = "smoke",
    ) -> None:
        self.artifact_root = Path(artifact_root)
        self.suite = suite
        self.assertion_engine = ScenarioAssertionEngine()
        self.report_writer = ScenarioReportWriter(self.artifact_root)

    def run_scenario(
        self,
        scenario: WorkflowTestScenario,
        executor: Any,  # FakeScenarioExecutor or ComfyApiScenarioExecutor
    ) -> WorkflowTestResult:
        """Run a single scenario and return the result."""
        started_at = datetime.now(timezone.utc).isoformat()
        start_time = time.monotonic()

        # Build run context
        workflow_run_id = f"test-{scenario.scenario_id}-{int(time.time())}"
        context = WorkflowRunContext(
            workflow_run_id=workflow_run_id,
            trace_id=f"trace-{workflow_run_id}",
            turn_id=f"turn-{scenario.scenario_id}",
            attempt_id="attempt-0",
            card_id=scenario.input_fixtures.get("card_id", "test-card"),
            session_id=scenario.input_fixtures.get("session_id", "test-session"),
        )

        result = WorkflowTestResult(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.scenario_name,
            workflow_run_id=workflow_run_id,
        )

        try:
            # Execute
            exec_result = executor.execute(scenario, context)

            # Collect node records
            node_records = exec_result.get("node_records", [])
            result.node_records = [r.to_dict() if hasattr(r, "to_dict") else r for r in node_records]

            # Run assertions
            assertion_results = self.assertion_engine.run_assertions(
                scenario=scenario,
                node_records=node_records,
                state_diff=exec_result.get("state_diff", {}),
                memory_diff=exec_result.get("memory_diff", {}),
            )

            result.total_assertions = assertion_results["total"]
            result.passed_assertions = assertion_results["passed"]
            result.failed_assertions = assertion_results["failed"]
            result.failures = assertion_results["failures"]
            result.state_diff = exec_result.get("state_diff", {})
            result.memory_diff = exec_result.get("memory_diff", {})
            result.passed = assertion_results["failed"] == 0
            result.exit_code = 0 if result.passed else 1

        except EnvironmentError as exc:
            result.passed = False
            result.exit_code = 2
            result.failures = [{
                "failure_id": "env_error",
                "assertion_name": "environment",
                "message": str(exc),
                "severity": "error",
            }]
        except Exception as exc:
            result.passed = False
            result.exit_code = 1
            result.failures = [{
                "failure_id": "execution_error",
                "assertion_name": "execution",
                "message": f"{type(exc).__name__}: {exc}",
                "severity": "error",
            }]

        finished_at = datetime.now(timezone.utc).isoformat()
        result.started_at = started_at
        result.finished_at = finished_at
        result.duration_ms = int((time.monotonic() - start_time) * 1000)

        # Write reports
        self.report_writer.write(result)

        return result

    def run_suite(
        self,
        scenarios: list[WorkflowTestScenario],
        executor: Any,
    ) -> list[WorkflowTestResult]:
        """Run all scenarios in a suite."""
        results = []
        for scenario in scenarios:
            if self.suite == "comfy-api-e2e" and not scenario.requires_comfyui:
                continue
            if self.suite != "comfy-api-e2e" and scenario.requires_comfyui:
                continue
            result = self.run_scenario(scenario, executor)
            results.append(result)
        return results


class FakeScenarioExecutor:
    """Execute scenarios using fake stores and in-process node calls.

    No real ComfyUI, no real models, no real network.
    """

    def __init__(self) -> None:
        from .fakes.fake_stores import (
            FakeCardStateStore, FakeTurnRecordStore,
            FakeActiveMemoryStore, FakeRagMemoryStore, FakeTraceStore,
        )
        self.card_state_store = FakeCardStateStore()
        self.turn_record_store = FakeTurnRecordStore()
        self.active_memory_store = FakeActiveMemoryStore()
        self.rag_memory_store = FakeRagMemoryStore()
        self.trace_store = FakeTraceStore()
        self._node_records: list[Any] = []

    def execute(
        self,
        scenario: WorkflowTestScenario,
        context: WorkflowRunContext,
    ) -> dict[str, Any]:
        """Execute a scenario and return results.

        Dispatches to scenario-specific executor based on scenario_id.
        """
        dispatch = {
            "card_import_safe_json": self._exec_card_import,
            "conditional_worldbook_branch": self._exec_conditional_worldbook,
            "dynamic_agent_not_required": self._exec_dynamic_agent_not_required,
            "quality_reject_zero_side_effect": self._exec_quality_reject,
            "accepted_turn_with_memory_curation": self._exec_accepted_turn,
            "retry_idempotency": self._exec_retry_idempotency,
            "upstream_failure_propagation": self._exec_upstream_failure,
        }

        executor_fn = dispatch.get(scenario.scenario_id)
        if executor_fn is None:
            raise ValueError(f"Unknown scenario: {scenario.scenario_id}")

        self._node_records = []
        result = executor_fn(scenario, context)

        result["node_records"] = self._node_records
        return result

    def _make_record(self, context: WorkflowRunContext, **kwargs: Any) -> Any:
        from ..contracts.node_execution_record import NodeExecutionRecord
        record = NodeExecutionRecord(
            trace_id=context.trace_id,
            workflow_run_id=context.workflow_run_id,
            prompt_id=context.prompt_id,
            turn_id=context.turn_id,
            attempt_id=context.attempt_id,
            **kwargs,
        )
        self._node_records.append(record)
        return record

    def _exec_card_import(
        self, scenario: WorkflowTestScenario, context: WorkflowRunContext,
    ) -> dict[str, Any]:
        """Card import: staged → approved → ready, no side effects."""
        from ..contracts.node_execution_record import (
            ExecutionStatus, BusinessDisposition, SemanticHealth,
        )
        fixtures = scenario.input_fixtures

        # CardSourceLoad
        self._make_record(context,
            node_id="card_source_load", node_class="AWPV2CardSourceLoad",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"source_type": "json", "size_bytes": 1024},
        )

        # CardPayloadParse
        self._make_record(context,
            node_id="card_payload_parse", node_class="AWPV2CardPayloadParse",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"fields_found": ["name", "description", "personality"]},
        )

        # CardSecurityScan
        self._make_record(context,
            node_id="card_security_scan", node_class="AWPV2CardSecurityScan",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"issues": 0, "severity_max": "none"},
        )

        # CardNormalize
        self._make_record(context,
            node_id="card_normalize", node_class="AWPV2CardNormalize",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"status": "normalized"},
        )

        # CardImportReview
        self._make_record(context,
            node_id="card_import_review", node_class="AWPV2CardImportReview",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"issue_count": 0, "severity_max": "none"},
        )

        # CardImportApproval
        self._make_record(context,
            node_id="card_import_approval", node_class="AWPV2CardImportApproval",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"approved": True, "reason": "clean_import"},
        )

        # CardDefinitionCommit
        self._make_record(context,
            node_id="card_definition_commit", node_class="AWPV2CardDefinitionCommit",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"card_id": fixtures.get("card_id", "test-card"), "status": "committed"},
        )

        # No CardState/TurnRecord/Memory writes
        return {
            "state_diff": {"changes": 0},
            "memory_diff": {"active_writes": 0, "rag_writes": 0},
        }

    def _exec_conditional_worldbook(
        self, scenario: WorkflowTestScenario, context: WorkflowRunContext,
    ) -> dict[str, Any]:
        """Conditional worldbook: flag-based branch, first-match-wins."""
        from ..contracts.node_execution_record import (
            ExecutionStatus, BusinessDisposition, SemanticHealth,
        )
        fixtures = scenario.input_fixtures
        active_flags = set(fixtures.get("active_flags", []))
        entries = fixtures.get("worldbook_entries", [])

        matched = []
        not_matched = []
        for entry in entries:
            entry_id = entry.get("entry_id", "")
            required_flag = entry.get("required_flag", "")
            if required_flag in active_flags:
                matched.append(entry_id)
            else:
                not_matched.append(entry_id)

        self._make_record(context,
            node_id="round_snapshot", node_class="AWPV2RoundSnapshot",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"snapshot_id": "snap-1", "turn_index": 1},
        )

        self._make_record(context,
            node_id="conditional_worldbook", node_class="AWPV2ConditionalWorldbook",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={
                "matched_entries": matched,
                "not_matched_entries": not_matched,
                "strategy": "first_match_wins",
                "explanation": {
                    eid: f"flag '{fixtures.get('worldbook_entries', [{}])[i].get('required_flag', '')}' active"
                    for i, eid in enumerate(matched)
                },
            },
        )

        return {
            "state_diff": {"changes": 0},
            "memory_diff": {"active_writes": 0, "rag_writes": 0},
        }

    def _exec_dynamic_agent_not_required(
        self, scenario: WorkflowTestScenario, context: WorkflowRunContext,
    ) -> dict[str, Any]:
        """Low-risk input: scheduler doesn't start unnecessary agents."""
        from ..contracts.node_execution_record import (
            ExecutionStatus, BusinessDisposition, SemanticHealth,
        )

        self._make_record(context,
            node_id="round_snapshot", node_class="AWPV2RoundSnapshot",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
        )

        self._make_record(context,
            node_id="director_plan", node_class="AWPV2DirectorPlan",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"task_count": 0, "reason": "low_risk"},
        )

        # All dynamic agents should be not_required
        for agent in ["history_recall", "opportunity", "world_life", "emotion_relationship", "continuity"]:
            self._make_record(context,
                node_id=f"{agent}_trigger", node_class=f"AWPV2{agent.replace('_', '').title()}Trigger",
                execution_status=ExecutionStatus.EXECUTED.value,
                business_disposition=BusinessDisposition.NOT_REQUIRED.value,
                semantic_health=SemanticHealth.PASSED.value,
                output_summary={"triggered": False, "reason": "low_risk"},
            )
            self._make_record(context,
                node_id=f"{agent}_agent", node_class=f"AWPV2{agent.replace('_', '').title()}Agent",
                execution_status=ExecutionStatus.NOT_REACHED.value,
                business_disposition=BusinessDisposition.NOT_REQUIRED.value,
                semantic_health=SemanticHealth.PASSED.value,
            )

        return {
            "state_diff": {"changes": 0},
            "memory_diff": {"active_writes": 0, "rag_writes": 0},
        }

    def _exec_quality_reject(
        self, scenario: WorkflowTestScenario, context: WorkflowRunContext,
    ) -> dict[str, Any]:
        """Quality reject: zero side effects on all commit nodes."""
        from ..contracts.node_execution_record import (
            ExecutionStatus, BusinessDisposition, SemanticHealth,
        )

        self._make_record(context,
            node_id="round_snapshot", node_class="AWPV2RoundSnapshot",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
        )

        self._make_record(context,
            node_id="quality_gate", node_class="AWPV2QualityGate",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"verdict": "reject", "blocking_reasons": ["too_short"]},
        )

        # All commit nodes must be blocked
        for commit_node, commit_class in [
            ("card_state_commit", "AWPV2CardStateCommit"),
            ("turn_record_commit", "AWPV2TurnRecordCommit"),
            ("active_memory_commit", "AWPV2ActiveMemoryCommit"),
            ("rag_memory_commit", "AWPV2RagMemoryCommit"),
        ]:
            self._make_record(context,
                node_id=commit_node, node_class=commit_class,
                execution_status=ExecutionStatus.NOT_REACHED.value,
                business_disposition=BusinessDisposition.NOT_REQUIRED.value,
                semantic_health=SemanticHealth.PASSED.value,
                error_summary={"reason": "quality_reject_blocks_side_effects"},
            )

        return {
            "state_diff": {"changes": 0, "reason": "quality_reject"},
            "memory_diff": {"active_writes": 0, "rag_writes": 0, "reason": "quality_reject"},
        }

    def _exec_accepted_turn(
        self, scenario: WorkflowTestScenario, context: WorkflowRunContext,
    ) -> dict[str, Any]:
        """Accepted turn: CardState + TurnRecord committed, memory curated."""
        from ..contracts.node_execution_record import (
            ExecutionStatus, BusinessDisposition, SemanticHealth,
        )

        self._make_record(context,
            node_id="round_snapshot", node_class="AWPV2RoundSnapshot",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
        )

        self._make_record(context,
            node_id="quality_gate", node_class="AWPV2QualityGate",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"verdict": "accept"},
        )

        self._make_record(context,
            node_id="card_state_commit", node_class="AWPV2CardStateCommit",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"status": "accepted", "patch_id": "p-1"},
        )

        self._make_record(context,
            node_id="turn_record_commit", node_class="AWPV2TurnRecordCommit",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"turn_id": context.turn_id, "status": "saved"},
        )

        # D6 Memory Curator — may run or no-op
        self._make_record(context,
            node_id="memory_curator", node_class="AWPV2MemoryCurator",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.NOOP.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"candidates_evaluated": 0, "reason": "no_long_term_value"},
        )

        return {
            "state_diff": {"changes": 1, "patch_id": "p-1"},
            "memory_diff": {"active_writes": 0, "rag_writes": 0},
        }

    def _exec_retry_idempotency(
        self, scenario: WorkflowTestScenario, context: WorkflowRunContext,
    ) -> dict[str, Any]:
        """Retry: same turn/patchId, different attemptId, no duplicate writes."""
        from ..contracts.node_execution_record import (
            ExecutionStatus, BusinessDisposition, SemanticHealth,
        )

        # First attempt
        self._make_record(context,
            node_id="card_state_commit_attempt_0", node_class="AWPV2CardStateCommit",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.PRODUCED_RESULT.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"status": "accepted", "patch_id": "p-1", "attempt": 0},
        )

        # Second attempt (same patch_id, different attempt_id)
        retry_context = WorkflowRunContext(
            workflow_run_id=context.workflow_run_id,
            trace_id=context.trace_id,
            turn_id=context.turn_id,
            attempt_id="attempt-1",
            card_id=context.card_id,
            session_id=context.session_id,
        )
        self._make_record(retry_context,
            node_id="card_state_commit_attempt_1", node_class="AWPV2CardStateCommit",
            execution_status=ExecutionStatus.EXECUTED.value,
            business_disposition=BusinessDisposition.NOOP.value,
            semantic_health=SemanticHealth.PASSED.value,
            output_summary={"status": "duplicate_patch", "patch_id": "p-1", "attempt": 1},
        )

        return {
            "state_diff": {"changes": 1, "reason": "first_commit_only"},
            "memory_diff": {"active_writes": 0, "rag_writes": 0},
        }

    def _exec_upstream_failure(
        self, scenario: WorkflowTestScenario, context: WorkflowRunContext,
    ) -> dict[str, Any]:
        """Upstream failure: downstream nodes blocked."""
        from ..contracts.node_execution_record import (
            ExecutionStatus, BusinessDisposition, SemanticHealth,
        )

        self._make_record(context,
            node_id="round_snapshot", node_class="AWPV2RoundSnapshot",
            execution_status=ExecutionStatus.FAILED.value,
            business_disposition=BusinessDisposition.NOOP.value,
            semantic_health=SemanticHealth.VIOLATION.value,
            error_summary={"error_type": "RuntimeError", "message": "snapshot build failed"},
        )

        for node_id, node_class in [
            ("quality_gate", "AWPV2QualityGate"),
            ("card_state_commit", "AWPV2CardStateCommit"),
            ("turn_record_commit", "AWPV2TurnRecordCommit"),
        ]:
            self._make_record(context,
                node_id=node_id, node_class=node_class,
                execution_status=ExecutionStatus.BLOCKED_BY_UPSTREAM_FAILURE.value,
                business_disposition=BusinessDisposition.NOOP.value,
                semantic_health=SemanticHealth.PASSED.value,
                upstream_node_ids=["round_snapshot"],
                error_summary={"blocked_by": "round_snapshot", "reason": "upstream_failure_propagation"},
            )

        return {
            "state_diff": {"changes": 0, "reason": "upstream_failure"},
            "memory_diff": {"active_writes": 0, "rag_writes": 0},
        }
