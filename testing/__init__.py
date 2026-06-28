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

try:
    from .workflow_scenario_runner import WorkflowScenarioRunner, FakeScenarioExecutor
except ImportError:
    WorkflowScenarioRunner = None  # type: ignore[assignment]
    FakeScenarioExecutor = None  # type: ignore[assignment]

try:
    from .scenario_fixture_factory import ScenarioFixtureFactory
except ImportError:
    ScenarioFixtureFactory = None  # type: ignore[assignment]

try:
    from .scenario_assertion_engine import ScenarioAssertionEngine
except ImportError:
    ScenarioAssertionEngine = None  # type: ignore[assignment]

try:
    from .scenario_report_writer import ScenarioReportWriter
except ImportError:
    ScenarioReportWriter = None  # type: ignore[assignment]

try:
    from .comfy_api_client import ComfyAPIClient
except ImportError:
    ComfyAPIClient = None  # type: ignore[assignment]

try:
    from .api_workflow_loader import APIWorkflowLoader
except ImportError:
    APIWorkflowLoader = None  # type: ignore[assignment]

try:
    from .api_workflow_fixture_patcher import APIWorkflowFixturePatcher
except ImportError:
    APIWorkflowFixturePatcher = None  # type: ignore[assignment]

try:
    from .comfy_websocket_collector import ComfyWebSocketCollector
except ImportError:
    ComfyWebSocketCollector = None  # type: ignore[assignment]

try:
    from .comfy_history_collector import ComfyHistoryCollector
except ImportError:
    ComfyHistoryCollector = None  # type: ignore[assignment]
