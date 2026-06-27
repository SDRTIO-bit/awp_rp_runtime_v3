"""ScenarioAssertionEngine — deterministic assertion runner for workflow scenarios.

All pass/fail decisions are made by deterministic rules.
No LLM, no human judgment, no probabilistic scoring.
"""

from __future__ import annotations

from typing import Any

from ..contracts.workflow_test_scenario import WorkflowTestScenario
from ..contracts.workflow_test_failure import WorkflowTestFailure
from ..contracts.node_execution_record import NodeExecutionRecord


class ScenarioAssertionEngine:
    """Run deterministic assertions against scenario results."""

    def run_assertions(
        self,
        scenario: WorkflowTestScenario,
        node_records: list[Any],
        state_diff: dict[str, Any],
        memory_diff: dict[str, Any],
    ) -> dict[str, Any]:
        """Run all assertions for a scenario.

        Returns:
            dict with keys: total, passed, failed, failures
        """
        failures: list[dict[str, Any]] = []
        total = 0

        # Normalize node records
        records: list[NodeExecutionRecord] = []
        for r in node_records:
            if isinstance(r, NodeExecutionRecord):
                records.append(r)
            elif isinstance(r, dict):
                records.append(NodeExecutionRecord.from_dict(r))
            else:
                records.append(r)

        records_by_id = {r.node_id: r for r in records}
        records_by_class = {r.node_class: r for r in records}

        # 1. Node expectations
        for expectation in scenario.node_expectations:
            total += 1
            record = None
            if expectation.node_id:
                record = records_by_id.get(expectation.node_id)
            if record is None and expectation.node_class:
                record = records_by_class.get(expectation.node_class)

            if record is None:
                if expectation.expected_execution_status == "not_reached":
                    # Expected not to be found — pass
                    continue
                failures.append({
                    "failure_id": f"node_missing_{expectation.node_id or expectation.node_class}",
                    "assertion_name": "node_present",
                    "node_id": expectation.node_id,
                    "expected": f"node with id={expectation.node_id} or class={expectation.node_class}",
                    "actual": "not found",
                    "message": f"Expected node {expectation.node_id or expectation.node_class} not found in records",
                    "severity": "error",
                })
                continue

            # Check execution status
            if expectation.expected_execution_status and not expectation.allow_any_status:
                total += 1
                if record.execution_status != expectation.expected_execution_status:
                    failures.append({
                        "failure_id": f"exec_status_{expectation.node_id}",
                        "assertion_name": "execution_status",
                        "node_id": expectation.node_id,
                        "expected": expectation.expected_execution_status,
                        "actual": record.execution_status,
                        "message": (
                            f"Node {record.node_id}: expected execution_status="
                            f"{expectation.expected_execution_status}, got {record.execution_status}"
                        ),
                        "severity": "error",
                    })

            # Check business disposition
            if expectation.expected_business_disposition:
                total += 1
                actual_disp = record.business_disposition
                expected_disp = expectation.expected_business_disposition

                # Allow noop if explicitly allowed
                if expectation.allow_noop and actual_disp == "noop":
                    pass  # acceptable
                elif actual_disp != expected_disp:
                    failures.append({
                        "failure_id": f"biz_disp_{expectation.node_id}",
                        "assertion_name": "business_disposition",
                        "node_id": expectation.node_id,
                        "expected": expected_disp,
                        "actual": actual_disp,
                        "message": (
                            f"Node {record.node_id}: expected business_disposition="
                            f"{expected_disp}, got {actual_disp}"
                        ),
                        "severity": "error",
                    })

            # Check semantic health
            if expectation.expected_semantic_health:
                total += 1
                if record.semantic_health != expectation.expected_semantic_health:
                    failures.append({
                        "failure_id": f"sem_health_{expectation.node_id}",
                        "assertion_name": "semantic_health",
                        "node_id": expectation.node_id,
                        "expected": expectation.expected_semantic_health,
                        "actual": record.semantic_health,
                        "message": (
                            f"Node {record.node_id}: expected semantic_health="
                            f"{expectation.expected_semantic_health}, got {record.semantic_health}"
                        ),
                        "severity": "error",
                    })

        # 2. Side effect expectations
        for se_expectation in scenario.side_effect_expectations:
            total += 1
            store = se_expectation.store_name

            if se_expectation.must_be_zero:
                diff_key = f"{store}_writes"
                actual_writes = memory_diff.get(diff_key, state_diff.get("changes", 0))
                if store == "card_state":
                    actual_writes = state_diff.get("changes", 0)
                elif store == "turn_record":
                    actual_writes = state_diff.get("turn_writes", 0)

                if actual_writes != 0:
                    failures.append({
                        "failure_id": f"side_effect_{store}",
                        "assertion_name": f"zero_side_effect_{store}",
                        "expected": 0,
                        "actual": actual_writes,
                        "message": f"Expected zero writes to {store}, got {actual_writes}",
                        "severity": "error",
                    })

        # 3. Upstream failure propagation check
        if scenario.scenario_id == "upstream_failure_propagation":
            total += 1
            failed_nodes = [r for r in records if r.execution_status == "failed"]
            blocked_nodes = [r for r in records if r.execution_status == "blocked_by_upstream_failure"]
            if not failed_nodes:
                failures.append({
                    "failure_id": "no_upstream_failure",
                    "assertion_name": "upstream_failure_exists",
                    "expected": "at least one failed node",
                    "actual": "no failed nodes",
                    "message": "Expected at least one upstream failure",
                    "severity": "error",
                })
            if not blocked_nodes:
                failures.append({
                    "failure_id": "no_blocked_downstream",
                    "assertion_name": "downstream_blocked",
                    "expected": "at least one blocked node",
                    "actual": "no blocked nodes",
                    "message": "Expected downstream nodes to be blocked",
                    "severity": "error",
                })

        passed = total - len(failures)
        return {
            "total": total,
            "passed": passed,
            "failed": len(failures),
            "failures": failures,
        }
