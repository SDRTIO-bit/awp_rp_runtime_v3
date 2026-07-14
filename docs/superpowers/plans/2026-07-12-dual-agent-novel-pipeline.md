# Dual-Agent Novel Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a bounded, testable Plan-to-Writer contract that improves chapter flow without exposing the Writer to the full planning corpus.

**Architecture:** Add a deterministic context compiler between `ChapterPlan` and `NovelWriterAdapter`. Keep the single-pass Writer, filter cast/world/history before prompt construction, and validate draft adherence before persistence.

**Tech Stack:** Python 3.10+, dataclasses, pytest, existing SQLite registry and synchronous LLM adapters.

## Global Constraints

- No async/await in the novel pipeline.
- No RP-mode changes.
- No Director LLM restoration.
- Tests must fail before production changes and pass afterward.
- Preserve user-authored novel outputs and existing dirty-worktree changes.

---

### Task 1: Define Writer context contract

**Files:**
- Create: `runtime/novel_writer_context.py`
- Modify: `contracts/novel_write_packet.py`
- Test: `tests/test_novel_writer_context.py`

**Interfaces:**
- Produces: `NovelWriterContextCompiler.compile(plan, ledger_items, character_states, prev_tail, summaries) -> NovelWritePacket`
- Produces: `NovelWritePacket.allowed_cast`, `chapter_contract`, and `history_context`.

- [ ] Write tests proving future characters, unplanned characters, unrelated ledger facts, and unbounded history are excluded.
- [ ] Run tests and confirm failures because the compiler and packet fields do not exist.
- [ ] Add packet fields with serialization support.
- [ ] Implement the compiler with deterministic character, world, ledger, and history selection.
- [ ] Run the focused tests and commit.

### Task 2: Rebuild the single-pass Writer prompt

**Files:**
- Modify: `runtime/novel_writer_adapter.py`
- Modify: `scripts/novel_cli.py`
- Test: `tests/test_novel_writer_context.py`

**Interfaces:**
- Consumes: compiled `NovelWritePacket` fields from Task 1.
- Produces: a prompt containing medium-granularity narrative moves, required payoff, allowed cast, bounded history, world rules, and previous tail.

- [ ] Write tests proving turning point, climax, ending, every scene beat, allowed cast, and world rules appear in the prompt.
- [ ] Write tests proving full Story Bible guidance is not automatically duplicated into Writer guidance.
- [ ] Run tests and confirm the current prompt fails these assertions.
- [ ] Replace the cause-development-ending shortcut with the chapter contract.
- [ ] Separate Plan guidance from Writer chapter-specific guidance in CLI loading.
- [ ] Run focused tests and commit.

### Task 3: Enforce plan adherence

**Files:**
- Create: `runtime/novel_plan_adherence.py`
- Modify: `runtime/novel_engine.py`
- Test: `tests/test_novel_plan_adherence.py`

**Interfaces:**
- Produces: `PlanAdherenceResult(blocking_reasons, warnings, coverage)`.
- Consumes: `ChapterPlan`, draft text, and all known project character names.

- [ ] Write failing tests for missing climax/payoff and unauthorized known characters.
- [ ] Implement deterministic token/phrase claim extraction with conservative warnings for ambiguous semantic matches.
- [ ] Integrate results after quality and continuity checks, before draft status is decided.
- [ ] Ensure rejected adherence results cannot be reported as accepted.
- [ ] Run focused tests and commit.

### Task 4: Correct project context and compatibility

**Files:**
- Modify: `runtime/novel_writer_adapter.py`
- Modify: `runtime/novel_engine.py`
- Modify: `runtime/novel_write_packet_builder.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_novel_writer_context.py`

**Interfaces:**
- Resolves style benchmark from the project directory stored in project metadata/state before legacy fallbacks.
- Treats `first_appearance <= 0` as unscheduled.

- [ ] Write failing tests for hyphenated project IDs versus underscored directories and `first_appearance=0` exclusion.
- [ ] Implement bounded path resolution and remove the cross-project `steam_magic` fallback.
- [ ] Replace the legacy v2 test imports with v3 package imports.
- [ ] Run novel tests and commit.

### Task 5: Verification

**Files:**
- Verify all files modified above.

- [ ] Run `pytest -q --noconftest tests/test_novel_writer_context.py tests/test_novel_plan_adherence.py tests/test_novel_beat_continuity.py`.
- [ ] Run the broader novel test subset with standard conftest.
- [ ] Compile all changed Python files with `python -m py_compile`.
- [ ] Build a clean temporary `daily_high_school` database and inspect the compiled Writer prompt.
- [ ] Run one isolated chapter generation only if provider availability is confirmed.
- [ ] Review `git diff --check`, status, and final diff before completion.
