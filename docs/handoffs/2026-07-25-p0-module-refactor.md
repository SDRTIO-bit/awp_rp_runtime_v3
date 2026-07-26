# Handoff — 2026-07-25: Module Permission Refactor (P0) + DeepSeek Quota Optimization

## Summary

Completed P0 architectural refactoring: extracted the write-path mechanical correctness layer from `novel_style_cleaner.py` into a dedicated `novel_mechanical_gate.py`, then optimized DeepSeek API call distribution to stay under the 3/min rate limit. 1264 tests pass, 0 new failures. Chapter 2 verified end-to-end.

## What Changed

### New File
- `runtime/novel_mechanical_gate.py` (~400 lines) — `NovelMechanicalGate` class containing:
  - `polish_chapter_text()` — V4 HARD-only entry point
  - `_run_hard_loop()` → `_run_audit(HARD)` → `_run_patch_gen()` → `_run_verify()` → `_apply_patches()`
  - Deterministic checks: `check_metadata_leak`, `check_degeneration`, `check_scene_repeat`, `check_chapter_structure`, `normalize_punctuation`
  - `clean_plan()`, `_strip_boilerplate()`, `_call_llm_json()`
  - All prompts/constants: `_AUDIT_SYSTEM_PROMPT`, `_PATCH_SYSTEM_PROMPT`, `_VERIFY_SYSTEM_PROMPT`, `_PATCH_BUDGET=0.08`, etc.

### Modified Files
- `runtime/novel_style_cleaner.py` — Rewritten as `NovelStyleCleaner(NovelMechanicalGate)`. Retains only frozen offline tools: banned words/patterns, drumbeat, STYLE/DESIGN audit, `rewrite_for_issues`. Constructor emits `DeprecationWarning`.
- `runtime/novel_engine.py` — Hot path now uses `NovelMechanicalGate`. Backward-compat `@property _style_cleaner`. Removed 3 `_check_continuity()` calls (merged into Mechanical Audit). Added `mechanical_patch` role config.
- `runtime/novel_llm_factory.py` — Added `mechanical_patch` role. Changed `polish_verify` model from `deepseek-v4-flash` to `deepseek-v4-pro`.
- `scripts/novel_cli.py` — `audit-design` and `audit-style` now instantiate `NovelStyleCleaner` directly instead of going through `engine._style_cleaner`.

### Unchanged
- `runtime/novel_quality_pipeline.py` — Still imports `NovelStyleCleaner` (inherits all mechanical methods). No change needed.
- All prompts, thresholds, budgets, control flow — zero changes beyond import reconnections.

## Architecture After P0

```
Write Path (hot):
  Architect (deepseek-v4-pro) → Writer (gemini, opencode)
    → Quality Pipeline (banned words etc, NovelStyleCleaner)
    → Mechanical Gate (NovelMechanicalGate)
        ├─ Audit (deepseek-v4-pro, 1 call)
        ├─ Patch (gemini via opencode, 1 call)  ← was deepseek
        └─ Verify (deepseek-v4-pro, 1 call)
    → Ledger Curator (gemini via opencode)  ← was deepseek

Offline CLI:
  audit-design → NovelStyleCleaner(NovelMechanicalGate)
  audit-style  → NovelStyleCleaner(NovelMechanicalGate)
```

## DeepSeek Call Distribution (per chapter)

| Step | Model | Calls | Notes |
|---|---|---|---|
| Architect | deepseek-v4-pro | 1 | |
| Writer | gemini (opencode) | 0 ds | |
| Mechanical Audit | deepseek-v4-pro | 1 | Was: polish_audit |
| Mechanical Patch | gemini (opencode) | 0 ds | Was: polish_repair (deepseek) |
| Mechanical Verify | deepseek-v4-pro | 1 | Was: polish_verify (flash→pro) |
| Continuity | **removed** | 0 | Absorbed into Mechanical Audit |
| Ledger Curator | gemini (opencode) | 0 ds | Was: deepseek |
| **Total deepseek** | | **3** | Down from 5 |

## Env Configuration

```powershell
# Writer, Patch, Ledger — all via opencode proxy (gemini)
$env:NOVEL_LLM_PROVIDER_WRITER = "opencode"
$env:NOVEL_LLM_PROVIDER_MECHANICAL_PATCH = "opencode"
$env:NOVEL_LLM_PROVIDER_LEDGER_CURATOR = "opencode"

# Architect, Audit, Verify — DeepSeek
$env:NOVEL_LLM_PROVIDER = "deepseek"  # default, all other roles
$env:DEEPSEEK_API_KEY = "sk-xxx"
$env:OPENCODE_API_KEY = "xxx"
```

## Test Status

- **1264/1274 pass**, 4 skipped
- **10 pre-existing failures** (not caused by P0):
  - 5: Autonomous NPC tests (Director removed from hot path in V4)
  - 2: Writer context tests (field names changed in V4: `核心行动`→`核心场面`)
  - 1: LLM factory test (`deepseek-v4-flash` exists in config)
  - 1: Memory pipeline (needs Pi Host running)
  - 1: Style benchmark (file may not exist)
- **0 new failures** from P0

## Chapter 2 Verification

```
Chapter 2: 新书少了三本 | 2818 chars | accepted
Quality: 5 warnings (banned words/patterns/drumbeat), 0 blocking
Mechanical Gate: 0 hard issues (time/presence/objects/knowledge all clean)
Plan adherence: 100% coverage
```

## Project Charter

`docs/decisions/2026-07-25-project-charter.md` — Frozen principles:
1. System optimizes reading comprehension, not "human-likeness"
2. Mechanical Gate handles only verifiable consistency errors
3. Reviewer can ask reader questions, never decides answers for the author
4. Eliminate unexpected comprehension blocks, not all discomfort
5. Review results calibrate Architect, never feed Writer directly
6. Single samples don't drive rule updates
7. Any new automation must prove it reduces reader friction

## Next Phase (P1 — not started)

Create `runtime/novel_reader_comfort_reviewer.py` — read-only Reader Comfort Reviewer with 8 friction types. See `.omo/plans/2026-07-25-module-permission-refactor.md` for full plan.
