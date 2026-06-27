"""ScenarioReportWriter — writes machine-readable test reports.

Outputs per run:
  artifacts/test-runs/<workflowRunId>/
    run.json
    timeline.json
    node-records.json
    state-diff.json
    memory-diff.json
    failures.json
    report.md
    junit.xml
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts.workflow_test_result import WorkflowTestResult


class ScenarioReportWriter:
    """Write test run reports to the artifact directory."""

    def __init__(self, artifact_root: str | Path) -> None:
        self.artifact_root = Path(artifact_root)

    def write(self, result: WorkflowTestResult) -> Path:
        """Write all report files for a test result."""
        run_dir = self.artifact_root / result.workflow_run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        self._write_run_json(run_dir, result)
        self._write_timeline(run_dir, result)
        self._write_node_records(run_dir, result)
        self._write_state_diff(run_dir, result)
        self._write_memory_diff(run_dir, result)
        self._write_failures(run_dir, result)
        self._write_report_md(run_dir, result)
        self._write_junit_xml(run_dir, result)

        return run_dir

    def _write_json(self, path: Path, data: Any) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def _write_run_json(self, run_dir: Path, result: WorkflowTestResult) -> None:
        self._write_json(run_dir / "run.json", result.to_dict())

    def _write_timeline(self, run_dir: Path, result: WorkflowTestResult) -> None:
        timeline = []
        for record in result.node_records:
            if isinstance(record, dict):
                timeline.append({
                    "node_id": record.get("node_id", ""),
                    "node_class": record.get("node_class", ""),
                    "execution_status": record.get("execution_status", ""),
                    "business_disposition": record.get("business_disposition", ""),
                    "semantic_health": record.get("semantic_health", ""),
                    "started_at": record.get("started_at", ""),
                    "finished_at": record.get("finished_at", ""),
                    "duration_ms": record.get("duration_ms", 0),
                })
        self._write_json(run_dir / "timeline.json", timeline)

    def _write_node_records(self, run_dir: Path, result: WorkflowTestResult) -> None:
        self._write_json(run_dir / "node-records.json", result.node_records)

    def _write_state_diff(self, run_dir: Path, result: WorkflowTestResult) -> None:
        self._write_json(run_dir / "state-diff.json", result.state_diff)

    def _write_memory_diff(self, run_dir: Path, result: WorkflowTestResult) -> None:
        self._write_json(run_dir / "memory-diff.json", result.memory_diff)

    def _write_failures(self, run_dir: Path, result: WorkflowTestResult) -> None:
        self._write_json(run_dir / "failures.json", result.failures)

    def _write_report_md(self, run_dir: Path, result: WorkflowTestResult) -> None:
        lines = [
            f"# Test Report: {result.scenario_name}",
            "",
            f"- **Scenario ID**: {result.scenario_id}",
            f"- **Workflow Run ID**: {result.workflow_run_id}",
            f"- **Passed**: {'YES' if result.passed else 'NO'}",
            f"- **Exit Code**: {result.exit_code}",
            f"- **Duration**: {result.duration_ms}ms",
            f"- **Assertions**: {result.passed_assertions}/{result.total_assertions} passed",
            "",
        ]

        if result.failures:
            lines.append("## Failures")
            lines.append("")
            for f in result.failures:
                lines.append(f"- **{f.get('assertion_name', '?')}** [{f.get('node_id', 'global')}]: {f.get('message', '')}")
                if f.get("expected") is not None:
                    lines.append(f"  - Expected: `{f['expected']}`")
                if f.get("actual") is not None:
                    lines.append(f"  - Actual: `{f['actual']}`")
            lines.append("")

        lines.append("## Node Records")
        lines.append("")
        lines.append("| Node ID | Class | Execution | Business | Semantic |")
        lines.append("|---------|-------|-----------|----------|----------|")
        for record in result.node_records:
            if isinstance(record, dict):
                lines.append(
                    f"| {record.get('node_id', '')} "
                    f"| {record.get('node_class', '')} "
                    f"| {record.get('execution_status', '')} "
                    f"| {record.get('business_disposition', '')} "
                    f"| {record.get('semantic_health', '')} |"
                )
        lines.append("")

        with open(run_dir / "report.md", "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _write_junit_xml(self, run_dir: Path, result: WorkflowTestResult) -> None:
        testsuites = ET.Element("testsuites")
        testsuite = ET.SubElement(testsuites, "testsuite")
        testsuite.set("name", result.scenario_name)
        testsuite.set("tests", str(result.total_assertions))
        testsuite.set("failures", str(result.failed_assertions))
        testsuite.set("errors", "0")
        testsuite.set("time", str(result.duration_ms / 1000.0))

        testcase = ET.SubElement(testsuite, "testcase")
        testcase.set("name", result.scenario_id)
        testcase.set("classname", f"workflow_scenarios.{result.scenario_id}")
        testcase.set("time", str(result.duration_ms / 1000.0))

        if not result.passed:
            for failure in result.failures:
                failure_elem = ET.SubElement(testcase, "failure")
                failure_elem.set("message", failure.get("message", ""))
                failure_elem.set("type", failure.get("assertion_name", "assertion"))
                failure_elem.text = json.dumps(failure, indent=2)

        tree = ET.ElementTree(testsuites)
        with open(run_dir / "junit.xml", "wb") as f:
            tree.write(f, xml_declaration=True, encoding="utf-8")
