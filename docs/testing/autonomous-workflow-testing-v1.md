# Autonomous Workflow Testing V1

## Overview

The AWP RP Runtime V2 test harness enables fully automated, unattended testing
of ComfyUI workflows. All pass/fail decisions are made by deterministic rules —
no LLM, no human judgment, no probabilistic scoring.

## Architecture

```
Scenario JSON → ScenarioFixtureFactory → WorkflowScenarioRunner
                                              ↓
                                    FakeScenarioExecutor  (smoke/integration)
                                    ComfyApiScenarioExecutor  (comfy-api-e2e)
                                              ↓
                                    ScenarioAssertionEngine (deterministic)
                                              ↓
                                    ScenarioReportWriter
                                              ↓
                                    artifacts/test-runs/<workflowRunId>/
                                      run.json, timeline.json, node-records.json,
                                      state-diff.json, memory-diff.json,
                                      failures.json, report.md, junit.xml
```

## Test Suites

### smoke (default)
- Pure Python, fake stores, no network, no ComfyUI
- Runs in CI on push/PR
- Covers all 7 declarative scenarios

### integration
- Pure Python, fake stores, extended scenarios
- Runs nightly via GitHub Actions

### comfy-api-e2e
- Connects to local ComfyUI API
- Submits real API workflows with test fixtures
- Uses fake adapters (no real models)
- Requires local ComfyUI instance
- Exit code 2 if ComfyUI not available

## Running Tests

```bash
# All existing tests + new observability tests
python -m pytest tests/ -q

# Smoke scenario suite (fake environment)
python -m awp_rp_runtime_v2.testing.run_workflow_scenarios --suite smoke

# Integration scenario suite (fake environment)
python -m awp_rp_runtime_v2.testing.run_workflow_scenarios --suite integration

# ComfyUI E2E suite (requires local ComfyUI)
python -m awp_rp_runtime_v2.testing.run_workflow_scenarios --suite comfy-api-e2e

# PowerShell E2E script
.\scripts\run_awp_comfy_e2e.ps1
```

## Scenarios

| ID | Description | Suite |
|----|-------------|-------|
| `card_import_safe_json` | Legal card import, staged → approved → ready | smoke |
| `conditional_worldbook_branch` | Flag-based worldbook branching | smoke |
| `dynamic_agent_not_required` | Low-risk input, no unnecessary agents | smoke |
| `quality_reject_zero_side_effect` | Quality reject → zero writes | smoke |
| `accepted_turn_with_memory_curation` | Accept → commit → curate | smoke |
| `retry_idempotency` | Same turn retry, no duplicate writes | smoke |
| `upstream_failure_propagation` | Upstream fail → downstream blocked | smoke |

## Three-Layer Status Model

Every NodeExecutionRecord has three status groups:

- **executionStatus**: executed | cached | failed | blocked_by_upstream_failure | cancelled | not_reached
- **businessDisposition**: produced_result | noop | not_required | skipped_by_policy | skipped_by_budget | degraded
- **semanticHealth**: passed | warning | violation | not_checked

## Data Redaction

Three levels of data redaction protect sensitive information:

- **Level 1 (Summary)**: Default. Type, length, hash only.
- **Level 2 (Redline)**: Key IDs, revision, status, count, reason codes.
- **Level 3 (Raw)**: Full artifacts. Default OFF. Local only.

Never exposed at any level: API keys, tokens, cookies, system prompts,
full card text, full player input, raw model chain-of-thought.

## CI Configuration

- `.github/workflows/ci.yml`: Runs on push/PR. Unit tests + smoke suite.
- `.github/workflows/nightly-scenarios.yml`: Daily at 03:17 UTC. All test suites.

## Windows Scheduled Task

```powershell
# Register (optional, explicit only)
.\scripts\register_awp_comfy_e2e_task.ps1

# Remove
.\scripts\register_awp_comfy_e2e_task.ps1 -Remove
```

Default: daily at 03:17 Asia/Tokyo local (18:17 UTC previous day).

### Time Configuration

| System | Time | Timezone |
|--------|------|----------|
| GitHub nightly cron | 18:17 | UTC |
| Windows scheduled task | 03:17 | Asia/Tokyo local |

Both fire at the same absolute moment.
