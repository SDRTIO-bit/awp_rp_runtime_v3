"""Entry point for running workflow scenarios.

Usage:
    python -m awp_rp_runtime_v2.testing.run_workflow_scenarios --suite smoke
    python -m awp_rp_runtime_v2.testing.run_workflow_scenarios --suite integration
    python -m awp_rp_runtime_v2.testing.run_workflow_scenarios --suite comfy-api-e2e

Exit codes:
    0 = all scenarios passed
    1 = one or more scenarios failed
    2 = environment error (e.g., ComfyUI not available)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .scenario_fixture_factory import ScenarioFixtureFactory
from .workflow_scenario_runner import WorkflowScenarioRunner, FakeScenarioExecutor


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run AWP RP Runtime V2 workflow test scenarios"
    )
    parser.add_argument(
        "--suite",
        choices=["smoke", "integration", "comfy-api-e2e", "all"],
        default="smoke",
        help="Which test suite to run",
    )
    parser.add_argument(
        "--artifact-root",
        default="artifacts/test-runs",
        help="Root directory for test run artifacts",
    )
    parser.add_argument(
        "--scenario-dir",
        default="tests/workflow_scenarios",
        help="Directory containing scenario JSON files",
    )
    parser.add_argument(
        "--comfy-url",
        default="http://127.0.0.1:8188",
        help="ComfyUI base URL (for comfy-api-e2e suite)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Timeout in seconds for ComfyUI execution",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Load scenarios
    factory = ScenarioFixtureFactory(args.scenario_dir)
    scenarios = factory.load_suite(args.suite)

    if not scenarios:
        print(f"No scenarios found for suite '{args.suite}' in {args.scenario_dir}")
        return 2

    print(f"Loaded {len(scenarios)} scenarios for suite '{args.suite}'")

    # Create runner
    runner = WorkflowScenarioRunner(
        artifact_root=args.artifact_root,
        suite=args.suite,
    )

    # Create executor
    if args.suite == "comfy-api-e2e":
        from .comfy_api_scenario_runner import ComfyApiScenarioExecutor
        try:
            executor = ComfyApiScenarioExecutor(
                base_url=args.comfy_url,
                timeout_seconds=args.timeout,
            )
            executor.check_environment()
        except EnvironmentError as exc:
            print(f"ERROR: {exc}")
            return 2
    else:
        executor = FakeScenarioExecutor()

    # Run
    results = runner.run_suite(scenarios, executor)

    # Report
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    print(f"\n{'='*60}")
    print(f"Suite: {args.suite}")
    print(f"Total: {total}  Passed: {passed}  Failed: {failed}")
    print(f"{'='*60}")

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {result.scenario_id}: {result.scenario_name}")
        if not result.passed:
            for failure in result.failures:
                print(f"      - {failure.get('assertion_name', '?')}: {failure.get('message', '')}")
            if result.exit_code == 2:
                print(f"      (environment error)")

    # Write suite summary
    summary_path = Path(args.artifact_root) / f"suite-{args.suite}-summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "suite": args.suite,
            "total": total,
            "passed": passed,
            "failed": failed,
            "results": [r.to_dict() for r in results],
        }, f, indent=2, default=str)

    print(f"\nArtifacts written to: {args.artifact_root}/")
    print(f"Suite summary: {summary_path}")

    if failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
