# Novel Quality Side-Effects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make chapter revision executable and prevent rejected drafts from changing future novel context.

**Architecture:** `NovelEngine` remains responsible for persisting a reviewable draft. It will invoke `NovelEvolutionCurator` only for an accepted quality decision, preserving the existing ledger and memory ownership boundary.

**Tech Stack:** Python 3.10+, pytest-compatible regression scripts, Pydantic models, SQLite stores.

## Global Constraints

- Keep novel pipeline calls synchronous.
- Only the evolution curator may write novel ledger and RP-derived memory stores.
- A rejected quality decision may persist a draft but must not produce continuity side effects.

---

### Task 1: Guard rejected chapter side effects

**Files:**
- Modify: `runtime/novel_engine.py`
- Test: isolated Python regression script invoked from the repository root

- [ ] Write and run an isolated regression that creates a rejected decision and proves the current `_update_ledger()` invokes the curator.
- [ ] Change `_update_ledger()` to return immediately unless `quality_decision.is_accepted()` is true.
- [ ] Re-run the regression and verify rejected drafts cause zero curator calls while accepted decisions still invoke it.

### Task 2: Restore chapter revision configuration

**Files:**
- Modify: `runtime/novel_engine.py`
- Test: isolated Python regression script invoked from the repository root

- [ ] Write and run an isolated regression that reaches `revise_chapter()` with a stubbed writer and quality pipeline; verify the current code raises `NameError` for `skip_drumbeat`.
- [ ] Derive `writer_prompt_name` and `skip_drumbeat` from the project configuration before calling the quality pipeline.
- [ ] Re-run the regression and verify revision two is persisted.

### Task 3: Verify and document the source of guidance drift

**Files:**
- Inspect: `scripts/novel_cli.py`, `runtime/novel_engine.py`, `novels/daily_high_school/guidance/chapter_01.md`, and Git history for `output/chapter_01.md`

- [ ] Verify whether guidance is delivered to planning, writing, and quality validation.
- [ ] Compare the latest chapter rewrite with the guidance and report which enforcement boundary is absent.
