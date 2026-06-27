"""ScenarioFixtureFactory — loads scenario definitions from JSON fixtures.

Each scenario is a JSON file in tests/workflow_scenarios/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..contracts.workflow_test_scenario import WorkflowTestScenario


class ScenarioFixtureFactory:
    """Load and manage workflow test scenarios."""

    def __init__(self, scenario_dir: str | Path = "tests/workflow_scenarios") -> None:
        self.scenario_dir = Path(scenario_dir)

    def load_scenario(self, scenario_id: str) -> WorkflowTestScenario:
        """Load a single scenario by ID."""
        path = self.scenario_dir / f"{scenario_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Scenario not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return WorkflowTestScenario.from_dict(data)

    def load_suite(self, suite: str = "smoke") -> list[WorkflowTestScenario]:
        """Load all scenarios for a suite."""
        scenarios = []
        if not self.scenario_dir.exists():
            return scenarios
        for path in sorted(self.scenario_dir.glob("*.json")):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            scenario = WorkflowTestScenario.from_dict(data)
            if scenario.suite == suite or suite == "all":
                scenarios.append(scenario)
        return scenarios

    def list_scenarios(self) -> list[str]:
        """List all available scenario IDs."""
        if not self.scenario_dir.exists():
            return []
        return sorted([f.stem for f in self.scenario_dir.glob("*.json")])
