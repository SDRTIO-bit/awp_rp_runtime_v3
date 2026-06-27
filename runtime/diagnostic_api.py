"""Diagnostic API — read-only local diagnostic endpoints.

Provides structured access to workflow run diagnostics.
Default binds to localhost only.

Endpoints (all read-only):
  GET /awp/diagnostics/runs/{workflowRunId}
  GET /awp/diagnostics/runs/{workflowRunId}/timeline
  GET /awp/diagnostics/runs/{workflowRunId}/nodes
  GET /awp/diagnostics/runs/{workflowRunId}/nodes/{nodeId}
  GET /awp/diagnostics/runs/{workflowRunId}/state-diff
  GET /awp/diagnostics/runs/{workflowRunId}/memory-diff
  GET /awp/diagnostics/runs/{workflowRunId}/failures
  GET /awp/diagnostics/compare?runA=...&runB=...

Restrictions:
  - Read-only (no state/memory write endpoints)
  - No arbitrary SQL
  - No arbitrary file path exposure
  - No un-redacted raw artifacts
  - localhost only by default
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .diagnostic_redactor import DiagnosticRedactor


class DiagnosticAPI:
    """Read-only diagnostic API backed by test-run artifact files.

    In V1, this reads from the local artifacts/test-runs/ directory.
    No HTTP server is implemented — this is a programmatic interface
    that can later be mapped to MCP tools or HTTP endpoints.
    """

    def __init__(
        self,
        artifact_root: str | Path,
        redaction_level: int = 1,
    ) -> None:
        self.artifact_root = Path(artifact_root)
        self.redactor = DiagnosticRedactor(level=redaction_level)

    def _load_run(self, workflow_run_id: str) -> dict[str, Any] | None:
        run_dir = self.artifact_root / workflow_run_id
        run_file = run_dir / "run.json"
        if not run_file.exists():
            return None
        with open(run_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_json(self, workflow_run_id: str, filename: str) -> Any:
        file_path = self.artifact_root / workflow_run_id / filename
        if not file_path.exists():
            return None
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_run(self, workflow_run_id: str) -> dict[str, Any] | None:
        """Get run-level summary."""
        data = self._load_run(workflow_run_id)
        if data is None:
            return None
        return self.redactor.redact_dict(data) if isinstance(data, dict) else data

    def get_timeline(self, workflow_run_id: str) -> list[dict[str, Any]] | None:
        """Get execution timeline."""
        data = self._load_json(workflow_run_id, "timeline.json")
        if data is None:
            return None
        if isinstance(data, list):
            return [self.redactor.redact_dict(e) if isinstance(e, dict) else e for e in data]
        return data

    def get_nodes(self, workflow_run_id: str) -> list[dict[str, Any]] | None:
        """Get all node execution records."""
        data = self._load_json(workflow_run_id, "node-records.json")
        if data is None:
            return None
        if isinstance(data, list):
            return [self.redactor.redact_dict(r) if isinstance(r, dict) else r for r in data]
        return data

    def get_node(self, workflow_run_id: str, node_id: str) -> dict[str, Any] | None:
        """Get a single node's execution record."""
        nodes = self.get_nodes(workflow_run_id)
        if nodes is None:
            return None
        for node in nodes:
            if isinstance(node, dict) and node.get("node_id") == node_id:
                return node
        return None

    def get_state_diff(self, workflow_run_id: str) -> dict[str, Any] | None:
        """Get state changes produced by this run."""
        data = self._load_json(workflow_run_id, "state-diff.json")
        if data is None:
            return None
        return self.redactor.redact_dict(data) if isinstance(data, dict) else data

    def get_memory_diff(self, workflow_run_id: str) -> dict[str, Any] | None:
        """Get memory changes produced by this run."""
        data = self._load_json(workflow_run_id, "memory-diff.json")
        if data is None:
            return None
        return self.redactor.redact_dict(data) if isinstance(data, dict) else data

    def get_failures(self, workflow_run_id: str) -> list[dict[str, Any]] | None:
        """Get test failures for this run."""
        data = self._load_json(workflow_run_id, "failures.json")
        if data is None:
            return None
        if isinstance(data, list):
            return data
        return [data] if isinstance(data, dict) else None

    def compare_runs(
        self, run_a_id: str, run_b_id: str
    ) -> dict[str, Any]:
        """Compare two workflow runs side by side."""
        run_a = self._load_run(run_a_id)
        run_b = self._load_run(run_b_id)

        result: dict[str, Any] = {
            "run_a": run_a_id,
            "run_b": run_b_id,
            "run_a_exists": run_a is not None,
            "run_b_exists": run_b is not None,
            "differences": [],
        }

        if run_a is None or run_b is None:
            return result

        # Compare node counts
        nodes_a = self._load_json(run_a_id, "node-records.json") or []
        nodes_b = self._load_json(run_b_id, "node-records.json") or []

        ids_a = {n.get("node_id"): n for n in nodes_a if isinstance(n, dict)}
        ids_b = {n.get("node_id"): n for n in nodes_b if isinstance(n, dict)}

        all_node_ids = sorted(set(ids_a.keys()) | set(ids_b.keys()))

        for nid in all_node_ids:
            na = ids_a.get(nid)
            nb = ids_b.get(nid)
            if na is None:
                result["differences"].append({
                    "node_id": nid, "type": "missing_in_a",
                    "status_b": nb.get("execution_status"),
                })
            elif nb is None:
                result["differences"].append({
                    "node_id": nid, "type": "missing_in_b",
                    "status_a": na.get("execution_status"),
                })
            else:
                status_a = na.get("execution_status")
                status_b = nb.get("execution_status")
                if status_a != status_b:
                    result["differences"].append({
                        "node_id": nid, "type": "status_changed",
                        "status_a": status_a, "status_b": status_b,
                    })

        return result
