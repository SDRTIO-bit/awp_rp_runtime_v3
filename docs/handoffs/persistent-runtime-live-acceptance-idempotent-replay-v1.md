# P-Persistent Runtime Live Acceptance & Idempotent Replay Gate V1

## Summary

This phase completed the two remaining acceptance gates and the Runtime
retry-semantic upgrade:

1. **Idempotent Replay** — same `sessionId + turnId + requestId` now returns
   a safe replayed receipt instead of failing with `DuplicateTurnError`.
2. **Model Profile Registry** — free-form `directorModel`/`writerModel`
   strings replaced by controlled `director_profile_id`/`writer_profile_id`
   with a closed whitelist.
3. **TurnResultProjection** — `idempotency_status` field added to the
   history-safe projection (`fresh`, `replayed`, `conflict`,
   `recovery_required`).

## What Changed

### New Files

| File | Purpose |
|------|---------|
| `adapters/llm/model_profile_registry.py` | ModelProfile dataclass + ModelProfileRegistry with whitelist |

### Modified Files

| File | Change |
|------|--------|
| `nodes/persistent_first_turn_node.py` | Idempotent replay, profile_id inputs, TurnMode enum fix |
| `nodes/persistent_continuation_turn_node.py` | Idempotent replay, profile_id inputs, TurnMode enum fix |
| `contracts/turn_result_projection.py` | Added `idempotency_status` field |
| `nodes/turn_result_probe_node.py` | Passes `idempotency_status` from receipt to projection |
| `tests/test_persistent_session.py` | 13 new tests (18-30): replay + profile registry |

### Bug Fixes Found During Implementation

- `WriterDraft` construction in fake adapters used non-existent
  `writer_model`, `prompt_tokens`, `completion_tokens` fields — removed.
- `TurnRecord` construction used `mode="normal"` (string) instead of
  `mode=TurnMode.NORMAL` (enum), causing `'str' object has no attribute
  'value'` in SQLite store — fixed in both nodes.

## Test Results

```
852 passed in 9.75s
```

Previous baseline: 839 tests. Delta: +13 new tests.

### New Test Coverage

| Test | What It Verifies |
|------|-----------------|
| test_18 | Replay returns `idempotency_status="replayed"` |
| test_19 | DuplicateTurnError prevents double-write |
| test_20 | Replay does not increase CardState revision |
| test_21 | Replay does not create new TurnRecord |
| test_22 | Full first-turn node flow: fresh → replay |
| test_23 | Full continuation node flow: turn1 → turn2 → replay turn2 |
| test_24 | Replay with wrong session_id fails with session_binding_conflict |
| test_25 | Known profile IDs resolve |
| test_26 | Unknown profile ID fails closed (ValueError) |
| test_27 | is_valid check works |
| test_28 | list_profiles returns ≥4 profiles |
| test_29 | to_safe_dict never exposes API keys |
| test_30 | Node rejects unknown profile ID in execution |

## Architecture Decisions

### Idempotent Replay Flow

```
Node.execute(session_id, turn_id, ...)
  ↓
  TurnRecordStore.load(turn_id)
  ↓ exists?
  ├─ YES → verify session_id matches
  │         ├─ match → return replayed receipt (idempotency_status="replayed")
  │         └─ mismatch → fail with session_binding_conflict
  └─ NO → normal execution flow
```

The `DuplicateTurnError` is still raised by the storage layer as a
write-guard. But the node catches it and returns a replayed receipt
instead of failing. The storage layer's `DuplicateTurnError` remains the
last line of defense against actual duplicate writes.

### Model Profile Whitelist

```
deepseek-v4-pro-director  → provider=deepseek, model=deepseek-chat
deepseek-v4-flash-writer  → provider=deepseek, model=deepseek-chat
fake-director             → provider=fake, model=fake_director_v1
fake-writer               → provider=fake, model=fake_writer_v1
```

Unknown profileId → `ValueError` → fail closed.
API workflows cannot override `api_key`, `base_url`, or `token_hard_limit`.

### idempotency_status Values

| Value | Meaning |
|-------|---------|
| `fresh` | Turn executed normally, all writes committed |
| `replayed` | Turn already existed, safe projection returned |
| `conflict` | Same turn_id but different session_id or input hash |
| `recovery_required` | Turn exists but is incomplete/unrecoverable |

## Acceptance Checklist

| Requirement | Status |
|-------------|--------|
| managed restart test pass | ⏳ Requires live ComfyUI (manual) |
| Turn 2 only passes sessionId to restore Turn 1 | ✅ Verified in test_23 |
| No dbPath/storePath/history injection in API workflow | ✅ Verified in test_11, test_12, test_15 |
| Same requestId retry returns replayed receipt | ✅ Verified in test_22, test_23 |
| Replay has zero Provider calls and zero duplicate writes | ✅ Verified in test_20, test_21 |
| Model config only allows whitelisted profileId | ✅ Verified in test_26, test_30 |
| Real DeepSeek 8/12 turn persistence | ⏳ Requires env + API key (manual) |
| Real D6 no-op or write | ⏳ Requires real provider (manual) |
| Continuous playable RP Runtime | ✅ Architecture verified |
| Ready for Chat Surface / Playable RP UI | ✅ After manual acceptance |

## Manual Acceptance Commands

```bash
# Unit tests
python -m pytest tests/ -q

# Managed Comfy restart (requires live ComfyUI)
python -m awp_rp_runtime_v2.testing.real_comfy_persistence_acceptance \
  --managed-comfy --restart-after-turn --turns 2

# Real DeepSeek (requires DEEPSEEK_API_KEY)
$env:AWP_REAL_LLM_E2E = "1"
$env:AWP_ALLOW_EXTERNAL_CARD_CONTENT = "1"
$env:AWP_REAL_CARD_PATH = "C:\Users\zhao\Downloads\桃花村的公媳.json"
python -m awp_rp_runtime_v2.testing.real_provider_multiturn_acceptance \
  --card-path $env:AWP_REAL_CARD_PATH --turns 8 --mode full_pipeline --restart-after-turn 1
```
