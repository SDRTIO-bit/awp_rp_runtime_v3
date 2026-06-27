# AI Failure Triage V1

## Role of AI in Testing

AI (Claude Code / Mimo2.5Pro) is a **reader and advisor**, not a judge.

### AI CAN:
- Read `failures.json`, `timeline.json`, `node-records.json`
- Read `state-diff.json`, `memory-diff.json`
- Find the first anomalous node in the execution trace
- Explain the root cause and impact scope
- Suggest minimal fixes
- Attempt patches on independent branches

### AI MUST NOT:
- Decide test pass/fail based on story quality
- Read full sensitive card text or player memories
- Auto-modify main
- Auto-execute real models
- Auto-write to production databases

## How to Locate the First Anomalous Node

1. Read `node-records.json` for the failed run
2. Filter by `semantic_health == "violation"` or `execution_status == "failed"`
3. Sort by `started_at` timestamp
4. The first match is the root cause node
5. Read its `error_summary` and `contract_checks`
6. Follow `upstream_node_ids` to trace the failure chain

## Structured Evidence for AI

Each test run produces:

| File | Content |
|------|---------|
| `run.json` | Run-level summary |
| `timeline.json` | Chronological node execution events |
| `node-records.json` | Full per-node records with three-layer status |
| `state-diff.json` | CardState changes (or zero if rejected) |
| `memory-diff.json` | Memory changes (or zero if rejected) |
| `failures.json` | Failed assertions with expected vs actual |
| `report.md` | Human-readable summary |
| `junit.xml` | Machine-readable JUnit format |

## Diagnostic API

Programmatic access to run diagnostics:

```python
from awp_rp_runtime_v2.runtime.diagnostic_api import DiagnosticAPI

api = DiagnosticAPI("artifacts/test-runs")
run = api.get_run("workflowRunId")
nodes = api.get_nodes("workflowRunId")
failures = api.get_failures("workflowRunId")
comparison = api.compare_runs("runA", "runB")
```

## Node Diagnostic Specs

Each critical node declares:
- **role**: What it does in the pipeline
- **successInvariants**: Must hold when node succeeds
- **normalNoopReasons**: Valid reasons for no result
- **enforcedChecks**: Business rules that block execution
- **observationalChecks**: Diagnostic rules that only warn

See `runtime/node_diagnostic_specs.py` for the full registry.
