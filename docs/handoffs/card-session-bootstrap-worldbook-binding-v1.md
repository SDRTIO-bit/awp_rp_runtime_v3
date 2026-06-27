# P-CardSession Bootstrap & Worldbook Binding V1 — Handoff

## Summary

Implemented the deterministic bootstrap chain from approved CardDefinition to ready RP Session.

**Branch:** `feat/card-session-bootstrap-worldbook-binding-v1`
**Tag:** `card-session-bootstrap-worldbook-binding-v1`
**Tests:** 711 passing (31 new + 680 existing)

---

## 1. Session Binding

A Session binds to a specific card version via `CardSessionBinding`:

- `session_id` → `logical_card_id` + `card_version` + `source_hash`
- Once ready, the binding is **immutable** — new card versions never change existing bindings
- Version conflict (same session, different card) → explicit rejection

**Contract:** `contracts/card_session_binding.py`

---

## 2. Greeting → OpeningRecord

The selected greeting is saved as an independent `OpeningRecord`:

- `opening_record_id` = `opr_{hash(session_id + greeting_id)}`
- Stores `safe_display_content` (sanitized, never raw)
- References source via `source_greeting_ref`
- Created by `AWPV2OpeningRecordCommit` node

**Contract:** `contracts/opening_record.py`

---

## 3. OpeningRecord ≠ TurnRecord

| Property | OpeningRecord | TurnRecord |
|----------|--------------|------------|
| Created by | Bootstrap | Turn lifecycle |
| Triggers D6 | No | Yes |
| Enters ActiveMemory | No | Yes |
| Enters RagMemory | No | Yes |
| Has player_input | No | Yes |
| ID prefix | `opr_` | `tr_` |

OpeningRecord is a **static resource reference**, not a runtime interaction.

---

## 4. Initial CardState Source

CardState is initialized **only** from `initialStateSeed`:

- Must be explicit, structured, schema-validated input
- Default: empty (no variables)
- **NEVER** from description/personality/scenario
- **NEVER** from Tavern macros, EJS, JS, or Regex Script
- **NEVER** from variable scripts in the card

**Contract:** `contracts/card_session_bootstrap_request.py` → `initial_state_seed` field
**Runtime:** `runtime/card_session_bootstrap_pipeline.py` → `_init_card_state()`

---

## 5. External Card Cannot Directly Change CardState

CardState is the **runtime reality**. CardDefinition is a **static resource**.

- CardDefinition changes (new import, new version) do NOT affect existing CardState
- Only `CardStateCommitRuntime` can write to CardState (with revision checks)
- Bootstrap creates CardState from seed only — card content is not compiled into state

---

## 6. WorldbookBinding ≠ Activation

| Concept | WorldbookBinding | Actual Activation |
|---------|-----------------|-------------------|
| Created at | Bootstrap | Round context assembly |
| Purpose | Register available entries | Select entries for prompt |
| Budget enforcement | No | Yes |
| Condition evaluation | Deferred | Runtime evaluation |
| Injects into prompt | No | Yes |

**Binding categories:**
- `candidate` — enabled, constant or normal entries
- `disabled` — explicitly disabled in card
- `deferred` — selective entries requiring condition evaluation
- `unsupported` — activation types not yet supported

**Contract:** `contracts/worldbook_binding.py`

---

## 7. Retry / Recovery Idempotency

- `request_id` is the idempotency key
- Same `request_id` → returns existing receipt (no duplicate writes)
- Partial failure (e.g., card not found) → no binding/receipt created
- Retry after failure → can succeed when conditions are met
- `session_id` + different card version → explicit conflict rejection

**Runtime:** `CardSessionBootstrapPipeline.bootstrap()` checks `self._receipts.get_by_request()` first

---

## 8. Node Tracing

All 8 new nodes support `@awp_trace_node` via the existing `AWPTraceableNodeMixin`.

**New diagnostic specs added:**
- `AWPV2CardDefinitionReadyValidator`
- `AWPV2GreetingSelection`
- `AWPV2CardStateInitializer`
- `AWPV2OpeningRecordCommit`
- `AWPV2WorldbookBindingBuilder`
- `AWPV2CardSessionBindingCommit`

**Must-expose fields:**
`logicalCardId`, `cardVersion`, `sourceHash`, `sessionId`, `requestId`,
`selectedGreetingId`, `openingRecordId`, `worldbookBindingId`,
`cardStateRevisionBefore`, `cardStateRevisionAfter`, `boundEntryCount`,
`disabledEntryCount`, `deferredEntryCount`, `commitStatus`, `idempotencyStatus`

**Never exposed:** full greeting text, card description, worldbook content, player input, keys

---

## 9. Node Architecture

8 new ComfyUI nodes, each with single responsibility:

| Node | Purpose |
|------|---------|
| `AWPV2CardSessionBootstrapRequest` | Create bootstrap request contract |
| `AWPV2CardDefinitionReadyValidator` | Validate card is ready |
| `AWPV2GreetingSelection` | Select and validate greeting |
| `AWPV2CardStateInitializer` | Initialize CardState from seed |
| `AWPV2OpeningRecordCommit` | Commit OpeningRecord |
| `AWPV2WorldbookBindingBuilder` | Build WorldbookBinding |
| `AWPV2CardSessionBindingCommit` | Commit binding + receipt |
| `AWPV2CardSessionBootstrapDiagnostics` | Output diagnostic summary |

**ComfyUI types:** `BOOTSTRAP_REQUEST`, `CARD_DEFINITION`, `VALIDATION_RESULT`, `GREETING_SELECTION`, `CARD_STATE`, `OPENING_RECORD`, `WORLDBOOK_BINDING`, `CARD_SESSION_BINDING`, `BOOTSTRAP_RECEIPT`, `DIAGNOSTICS`

---

## 10. Readiness for P-First Turn Execution

✅ Ready to proceed. The bootstrap chain provides:

- Immutable session-to-card binding
- OpeningRecord for greeting context
- WorldbookBinding for static resource reference
- Initial CardState for runtime state
- Full diagnostic trace

**Next phase:** P-First Turn Execution & Context Assembly V1
- Session Ready → Player Input → RoundSnapshot → Worldbook Retrieval → Director/Writer → First RP Turn

---

## Files Created

### Contracts (8)
- `contracts/card_session_bootstrap_request.py`
- `contracts/card_session_binding.py`
- `contracts/greeting_selection.py`
- `contracts/opening_record.py`
- `contracts/worldbook_binding.py`
- `contracts/card_session_bootstrap_receipt.py`
- `contracts/card_session_bootstrap_failure.py`
- `contracts/card_session_bootstrap_diagnostics.py`

### Storage (1)
- `storage/card_session_interfaces.py`

### Runtime (1)
- `runtime/card_session_bootstrap_pipeline.py`

### Nodes (8)
- `nodes/card_session_bootstrap_request_node.py`
- `nodes/card_definition_ready_validator_node.py`
- `nodes/greeting_selection_node.py`
- `nodes/card_state_initializer_node.py`
- `nodes/opening_record_commit_node.py`
- `nodes/worldbook_binding_builder_node.py`
- `nodes/card_session_binding_commit_node.py`
- `nodes/card_session_bootstrap_diagnostics_node.py`

### Testing (1)
- `testing/fakes/fake_card_session_stores.py`

### Tests (1)
- `tests/test_card_session_bootstrap.py` (31 tests)

### Workflows (2)
- `workflows/official_card_session_bootstrap_v1.json`
- `workflows/api/card_session_bootstrap_v1.api.json`

### Modified
- `nodes/__init__.py` — registered 8 new nodes
- `runtime/node_diagnostic_specs.py` — added 6 new diagnostic specs
- `tests/test_p1_nodes.py` — updated node count assertion
- `tests/test_p2_nodes.py` — updated node count assertion (77 → 85)
- `nodes/trace_display_node.py` — fixed `*` wildcard type compatibility
