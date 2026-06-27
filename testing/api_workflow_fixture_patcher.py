"""API Workflow Fixture Patcher — inject test fixtures into API workflows.

Creates an immutable test payload by:
  1. Deep-copying the API workflow
  2. Injecting test-specific IDs (workflowRunId, traceId, turnId, attemptId)
  3. Injecting test fixture paths (card, SQLite store, fake adapter config)
  4. Injecting fixed player input
"""

from __future__ import annotations

import copy
import json
from typing import Any


class APIWorkflowFixturePatcher:
    """Patch API workflow with test fixtures."""

    def patch(
        self,
        workflow: dict[str, Any],
        fixtures: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a patched copy of the workflow.

        Args:
            workflow: The original API workflow dict.
            fixtures: Test fixtures to inject.

        Returns:
            A new dict with fixtures injected.
        """
        patched = copy.deepcopy(workflow)

        # Inject run identity into AWP nodes
        for node_id, node_def in patched.items():
            if not isinstance(node_def, dict):
                continue

            class_type = node_def.get("class_type", "")
            inputs = node_def.get("inputs", {})

            # Inject trace/run IDs into AWP nodes
            if class_type.startswith("AWPV2"):
                if "trace_id" in inputs and "trace_id" in fixtures:
                    inputs["trace_id"] = fixtures["trace_id"]
                if "turn_id" in inputs and "turn_id" in fixtures:
                    inputs["turn_id"] = fixtures["turn_id"]

            # Inject card_id
            if "card_id" in inputs and "card_id" in fixtures:
                inputs["card_id"] = fixtures["card_id"]

            # Inject session_id
            if "session_id" in inputs and "session_id" in fixtures:
                inputs["session_id"] = fixtures["session_id"]

            # Inject player_input for RoundSnapshot
            if class_type == "AWPV2RoundSnapshot" and "player_input" in fixtures:
                inputs["player_input"] = fixtures["player_input"]

            # Inject auto_accept for QualityGate in test mode
            if class_type == "AWPV2QualityGate" and fixtures.get("auto_accept"):
                inputs["auto_accept"] = True

        return patched

    def create_standard_fixtures(
        self,
        workflow_run_id: str = "test-wr-001",
        trace_id: str = "test-tr-001",
        turn_id: str = "test-turn-001",
        attempt_id: str = "attempt-0",
        card_id: str = "test-card-001",
        session_id: str = "test-session-001",
    ) -> dict[str, Any]:
        """Create a standard set of test fixtures."""
        return {
            "workflow_run_id": workflow_run_id,
            "trace_id": trace_id,
            "turn_id": turn_id,
            "attempt_id": attempt_id,
            "card_id": card_id,
            "session_id": session_id,
            "player_input": "Test player input for automated testing.",
            "auto_accept": False,
        }
