"""Testing utilities for RP Runtime V2.

P-Observability additions:
  - WorkflowScenarioRunner: execute declarative test scenarios
  - FakeScenarioExecutor: run scenarios with fake stores
  - ComfyApiScenarioExecutor: run scenarios against real ComfyUI
  - ScenarioFixtureFactory: load scenario definitions
  - ScenarioAssertionEngine: deterministic assertion runner
  - ScenarioReportWriter: write machine-readable reports
  - DiagnosticCollector: collect node execution records
  - ComfyAPIClient: thin HTTP client for ComfyUI
  - APIWorkflowLoader: load/validate API workflow files
  - APIWorkflowFixturePatcher: inject test fixtures
  - ComfyWebSocketCollector: collect WS execution events
  - ComfyHistoryCollector: parse /history responses
"""

from .workflow_scenario_runner import WorkflowScenarioRunner, FakeScenarioExecutor
from .scenario_fixture_factory import ScenarioFixtureFactory
from .scenario_assertion_engine import ScenarioAssertionEngine
from .scenario_report_writer import ScenarioReportWriter
from .comfy_api_client import ComfyAPIClient
from .api_workflow_loader import APIWorkflowLoader
from .api_workflow_fixture_patcher import APIWorkflowFixturePatcher
from .comfy_websocket_collector import ComfyWebSocketCollector
from .comfy_history_collector import ComfyHistoryCollector
