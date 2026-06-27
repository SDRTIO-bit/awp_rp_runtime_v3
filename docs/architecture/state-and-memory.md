# State and Memory Architecture

## SQLite Tables

| Table | Primary Key | Unique Constraints | Indexes | Description |
|---|---|---|---|---|
| `schema_migrations` | `version` | — | — | Migration version tracking |
| `card_states` | `(card_id, session_id)` | — | — | Current CardState per session |
| `card_state_patch_receipts` | `patch_id` | — | `(card_id, session_id, applied_at)` | Audit log for all patches |
| `turn_records` | `turn_id` | `(card_id, session_id, turn_index)` | `(card_id, session_id, accepted_at DESC)` | Accepted turn records |
| `round_snapshots` | `snapshot_id` | — | `(card_id, session_id, created_at DESC)` | Frozen snapshots |
| `execution_traces` | `trace_id` | — | `(turn_id)` | Execution audit trails |
| `active_memory_records` | `(memory_id, card_id, session_id)` | — | `(card_id, session_id, status)` | Active memories (max 15) |
| `rag_memory_records` | `memory_id` | — | `(card_id, session_id)` | Long-term RAG memories |

## Transaction Boundaries

CardState commit is atomic:
1. Check duplicate patch_id
2. Load current state + revision
3. Validate ALL operations
4. Apply operations → new state
5. UPDATE card_states (new revision)
6. INSERT card_state_patch_receipts
7. COMMIT

Steps 5-6 are in the same transaction. If any step fails, ROLLBACK.

## CardState Allowed Operations

| Op | Path Prefix | Value Type | May Create | Error Code |
|---|---|---|---|---|
| `set` | `variables.*` | any non-None | yes | `INVALID_SET` |
| `remove` | `variables.*` \| `event_flags.*` | ignored | no | `INVALID_REMOVE` |
| `increment` | `variables.*` | int/float | no | `INVALID_INCREMENT` |
| `append_unique` | `active_stage_ids` | str | yes | `INVALID_APPEND_UNIQUE` |
| `set_flag` | `event_flags.*` | optional dict | yes | `INVALID_SET_FLAG` |
| `activate_stage` | `active_stage_ids` | str | yes | `INVALID_ACTIVATE_STAGE` |
| `deactivate_stage` | `active_stage_ids` | str | no | `INVALID_DEACTIVATE_STAGE` |
| `set_scene_field` | `scene_state.*` | per-field | yes | `INVALID_SET_SCENE_FIELD` |

Scene fields: `location(str)`, `time_of_day(str)`, `weather(str)`, `active_npcs(list)`, `description(str)`, `metadata(dict)`.

## Quality Gate → Side Effects

```
accept  → allow commit
revise  → block all side effects, allow retry
reject  → block all side effects, final
None    → block all side effects
traceId mismatch → block
```

All commit runtimes call `assert_side_effects_allowed(quality_decision)` before any write.

## TurnRecord ↔ CardState

- `base_card_state_revision`: revision BEFORE this turn's commit
- `result_card_state_revision`: revision AFTER this turn's commit
- `turn_index`: strictly increasing within cardId+sessionId
- `state_commit_ref`: patch_id of the state commit
- `quality_decision_ref`: trace_id of the QualityDecision

## RoundSnapshot

- `snapshot_id`: unique ID for traceability
- `base_card_state_revision`: frozen at build time
- Immutable once created
- Contains up to 5 recent TurnRecords (full, never truncated)
- Contains active memories (≤15, with conflict_status)
- Contains RAG recall (FTS5 + LIKE fallback, with conflict_status)
- Contains `memory_recall_diagnostics` (per-memory RecallDiagnostics)
- Contains `memory_budget_decision` (BudgetDecision: L1/active/rag usage, trimmed reasons)

## Three-Layer Memory (M1)

| Layer | Contract | Limit | Source |
|-------|----------|-------|--------|
| L1 | `AcceptedTurnWindow` | ≤5 full accepted TurnRecords | `turn_record_store.get_recent` |
| L2 | `ActiveMemoryRecord` | ≤15 active per card+session | `active_memory_store.recall` |
| L3 | `RagMemoryRecord` | ≤10 recall per round (configurable) | `rag_memory_store.recall` (FTS5 trigram + LIKE fallback) |

### Priority Order (hard, never overridden by free LLM)
```
CardState hard facts
> last 5 full accepted TurnRecords (L1)
> ActiveMemory (L2)
> high-confidence RAG (L3, confidence ≥ 0.7)
> ordinary RAG
> worldbook background
```

### Memory Commit Chain
```
Writer → QualityGate accept → StateUpdateProposal → CardStateCommit → TurnRecordCommit
→ ActiveMemoryCommit (gate-gated, idempotent)
→ RAGMemoryCommit (gate-gated, idempotent, scope-checked)
```

### Conflict Adjudication (deterministic)
- `ConflictSignal{entity_refs, negated_terms, reason}` → entity overlap + negated term → `conflicted`/`ignored`
- `source_card_state_revision < current.revision` → `stale` (downgraded)
- CardState always wins — no LLM judgement
