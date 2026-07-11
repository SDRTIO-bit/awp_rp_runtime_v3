# 小说运行时可靠性整改实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使 v3 包可被测试和脚本稳定导入，并让小说批量生成准确持久化成功、部分失败和完全失败终态。

**Architecture:** v3 是仓库根目录对应的唯一 Python 包名。测试夹具与直接运行的脚本把仓库父目录加入 `sys.path`，从而可导入根目录包。`BatchProgress` 增加失败章节元数据，`NovelEngine.batch_write()` 在循环中聚合失败，再一次性写入准确终态。

**Tech Stack:** Python 3.10+, pytest, dataclasses, SQLite。

## Global Constraints

- 不修改已有 SQLite schema 或历史小说数据。
- 不改动 LLM 角色、提示词和质量门控规则。
- 历史归档文档保留 v2 原文；可执行 Python、测试、CI、打包入口和现行 README 统一为 v3。
- 每项行为变更遵循 Red-Green-Refactor。

---

### Task 1: 统一 v3 包入口并恢复测试收集

**Files:**
- Modify: `pyproject.toml`, `__init__.py`, `tests/conftest.py`
- Modify: all non-archive executable `.py` files currently importing `awp_rp_runtime_v2`
- Modify: `.github/workflows/ci.yml`, `.github/workflows/nightly-scenarios.yml`, `README.md`
- Test: `tests/test_novel_engine.py`

**Interfaces:**
- Consumes: repository root directory named `awp_rp_runtime_v3`.
- Produces: importable `awp_rp_runtime_v3` package for pytest and direct scripts.

- [ ] **Step 1: Write a failing import smoke test**

Add this to `tests/test_novel_engine.py` before engine tests:

```python
def test_v3_package_is_importable():
    from awp_rp_runtime_v3.runtime.novel_engine import NovelEngine

    assert NovelEngine.__name__ == "NovelEngine"
```

- [ ] **Step 2: Verify the test currently fails during collection**

Run: `python -m pytest tests/test_novel_engine.py -q`

Expected: collection failure mentioning `awp_rp_runtime_v2` or inability to import `awp_rp_runtime_v3`.

- [ ] **Step 3: Replace active v2 imports and metadata**

Replace `awp_rp_runtime_v2` with `awp_rp_runtime_v3` only in tracked executable/source/test/CI files outside `docs/archive/` and existing dated historical design documents. Set the distribution name to `awp-rp-runtime-v3`; set the console entry point to `awp_rp_runtime_v3.scripts.awp_tui:main`; update the root module docstring. In `tests/conftest.py`, prepend `project_root.parent` rather than `project_root` to `sys.path`.

- [ ] **Step 4: Verify the focused import test passes**

Run: `python -m pytest tests/test_novel_engine.py::test_v3_package_is_importable -q`

Expected: `1 passed`.

### Task 2: Preserve partial batch failures in the contract and engine

**Files:**
- Modify: `contracts/novel_batch.py`
- Modify: `runtime/novel_engine.py:880-976`
- Test: `tests/test_novel_engine.py`

**Interfaces:**
- Consumes: `BatchProgress(batch_id, project_id, chapter_start, chapter_end, chapter_index, status, error_message)`.
- Produces: `BatchProgress(..., status="completed_with_failures", failed_chapters=(...), error_message=...)` when at least one chapter fails and at least one succeeds.

- [ ] **Step 1: Write failing tests for final batch status**

Add tests that replace `engine.write_chapter` with a callable raising `RuntimeError("writer unavailable")` for selected indexes. Assert:

```python
assert progress.status == "completed_with_failures"
assert progress.failed_chapters == (2,)
assert len(drafts) == 2
```

and for a batch where every write fails:

```python
assert progress.status == "failed"
assert progress.failed_chapters == (1, 2)
assert drafts == []
```

- [ ] **Step 2: Verify the new tests fail**

Run: `python -m pytest tests/test_novel_engine.py -q`

Expected: assertions fail because current code overwrites failure with `completed` and the contract has no `failed_chapters` field.

- [ ] **Step 3: Implement the minimal aggregate state**

Add `failed_chapters: tuple[int, ...] = ()` to `BatchProgress` and serialize/deserialize it as a JSON-compatible list. In `batch_write()`, collect `(chapter_index, error_message)` for caught chapter exceptions. After the loop choose `completed`, `completed_with_failures`, or `failed`; persist one final `BatchProgress` with the failed indexes and a joined, 200-character-per-entry error summary. Preserve existing per-chapter progress writes.

- [ ] **Step 4: Verify focused tests pass**

Run: `python -m pytest tests/test_novel_engine.py -q`

Expected: all tests pass.

### Task 3: Validate the novel reliability slice and documentation

**Files:**
- Modify: `README.md`, `docs/novel_cli_guide.md` only where package/terminal status wording is stale
- Test: `tests/test_novel_agents.py`, `tests/test_novel_memory_pipeline.py`, `tests/test_novel_beat_continuity.py`, `tests/test_novel_stores.py`

**Interfaces:**
- Consumes: v3 package imports and serialized `BatchProgress`.
- Produces: runnable documented test and CLI instructions.

- [ ] **Step 1: Update active user-facing package references**

Ensure current installation, Python examples and TUI command use `awp_rp_runtime_v3`; retain historical v2 release references only in archive material.

- [ ] **Step 2: Run novel test suite**

Run: `python -m pytest tests/test_novel_engine.py tests/test_novel_agents.py tests/test_novel_memory_pipeline.py tests/test_novel_beat_continuity.py tests/test_novel_stores.py -q`

Expected: all collected tests pass.

- [ ] **Step 3: Run syntax and collection checks**

Run:

```powershell
python -m compileall -q runtime adapters contracts storage scripts
python -m pytest --collect-only -q
```

Expected: compile succeeds; pytest collection completes without package import errors.

- [ ] **Step 4: Commit the implementation**

```powershell
git add pyproject.toml __init__.py .github README.md scripts testing tests runtime contracts docs/novel_cli_guide.md
git commit -m "fix: stabilize v3 novel runtime batch status"
```
