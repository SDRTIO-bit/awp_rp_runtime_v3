# Novel-Only Repository Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove RP/ComfyUI-only product code and generated dependencies while preserving a tested, installable novel-writing runtime.

**Architecture:** Establish a side-effect-free novel package boundary, narrow the shared store registry to novel and novel-memory stores, extract the mixed Novel HTTP API, then remove unreachable RP code, tests, UI, workflows, and documentation. Each destructive batch is preceded by an exact target check and followed by import and novel-suite verification.

**Tech Stack:** Python 3.10+, Pydantic v2, SQLite, aiohttp, React 18, TypeScript, Node.js >=22.19, pytest, Node test runner.

## Global Constraints

- Product scope is Novel Mode only; RP Mode is discontinued.
- Preserve all files and untracked runtime artifacts under `novels/`.
- Preserve current `.omo/` continuation files.
- Python remains the only state/file writer for novel runtime data.
- Do not silently fall back from Pi to legacy runtime.
- Delete only exact Git-tracked targets verified to resolve inside the repository.
- Keep cleanup commits independent from the author-editor feature commits.
- Every code task follows test-first or characterization-test-first order.

---

### Task 1: Freeze the Novel Package Boundary

**Files:**
- Create: `tests/test_novel_package_boundary.py`
- Modify: `__init__.py`
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Modify: `README.md`

**Interfaces:**
- Consumes: current package import and setuptools configuration.
- Produces: side-effect-free `awp_rp_runtime_v3` import and a package list containing only novel/shared packages.

- [ ] **Step 1: Write failing boundary tests**

```python
def test_root_package_has_no_comfy_node_or_server_side_effects(monkeypatch):
    imported = importlib.import_module("awp_rp_runtime_v3")
    assert not hasattr(imported, "NODE_CLASS_MAPPINGS")
    assert "awp_rp_runtime_v3.runtime.management_api" not in sys.modules


def test_setuptools_excludes_retired_rp_packages():
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    for retired in (".nodes", ".policies", ".services", ".testing"):
        assert retired not in text
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/test_novel_package_boundary.py -v`

Expected: FAIL because the root package currently registers ComfyUI nodes and the package list includes RP packages.

- [ ] **Step 3: Make the root import side-effect free**

Replace root `__init__.py` with version metadata only:

```python
"""AWP Novel Runtime."""

__version__ = "0.2.0"
__all__ = ["__version__"]
```

Update `pyproject.toml` project description and explicit package list to retain only the root, `adapters`, `contracts`, `runtime`, `scripts`, `storage`, and `storage.sqlite` packages. Add `web/node_modules/`, `web/dist/`, and novel Pi session directories to `.gitignore`. Rewrite README entry points around `tui`, `novel_cli.py`, and `agent_harness`.

- [ ] **Step 4: Run boundary tests**

Run: `python -m pytest tests/test_novel_package_boundary.py -v`

Expected: PASS.

- [ ] **Step 5: Remove tracked Web dependencies without deleting the local install**

Run:

```powershell
git rm -r --cached -- web/node_modules
```

Expected: 19,627 tracked dependency files staged for deletion; the local directory remains available for `npm run build`.

- [ ] **Step 6: Commit**

```powershell
git add -- __init__.py pyproject.toml .gitignore README.md tests/test_novel_package_boundary.py
git commit -m "chore: establish novel-only package boundary"
```

### Task 2: Narrow the Persistent Store Surface

**Files:**
- Modify: `runtime/session_runtime_registry.py`
- Modify: `runtime/runtime_store_factory.py`
- Modify: `storage/interfaces.py`
- Test: `tests/test_novel_stores.py`
- Test: `tests/test_novel_memory_pipeline.py`

**Interfaces:**
- Consumes: `Database`, nine novel stores, Active Memory Store, and RAG Memory Store.
- Produces: `SessionRuntimeStoreRegistry` containing only stores referenced by Novel Mode.

- [ ] **Step 1: Add a registry surface test**

```python
def test_registry_exposes_only_novel_and_novel_memory_stores(tmp_path):
    db = Database(tmp_path / "novel.db")
    db.initialize()
    registry = SessionRuntimeStoreRegistry(db)
    assert registry.novel_project_store
    assert registry.active_memory_store
    assert registry.rag_memory_store
    for retired in (
        "card_state_store", "turn_record_store", "round_snapshot_store",
        "card_definition_store", "card_session_binding_store",
    ):
        assert not hasattr(registry, retired)
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python -m pytest tests/test_novel_stores.py -v`

Expected: FAIL because the registry still constructs RP stores.

- [ ] **Step 3: Remove RP stores from the registry**

Keep these attributes:

```python
self.active_memory_store = SqliteActiveMemoryStore(db)
self.rag_memory_store = SqliteRagMemoryStore(db)
self.novel_project_store = SqliteNovelProjectStore(db)
self.novel_volume_store = SqliteNovelVolumeStore(db)
self.novel_chapter_plan_store = SqliteNovelChapterPlanStore(db)
self.novel_chapter_draft_store = SqliteNovelChapterDraftStore(db)
self.novel_ledger_store = SqliteNovelLedgerStore(db)
self.novel_character_store = SqliteNovelCharacterStore(db)
self.novel_batch_progress_store = SqliteNovelBatchProgressStore(db)
self.novel_reference_book_store = SqliteNovelReferenceBookStore(db)
self.novel_plan_store = SqliteNovelPlanStore(db)
```

Remove RP convenience accessors from `RuntimeStoreFactory`. Reduce `storage/interfaces.py` to `ActiveMemoryStore`, `RagMemoryStore`, `RecallLogStore`, and `RetentionDecisionStore` plus the exceptions actually imported by their SQLite implementations.

- [ ] **Step 4: Run store and memory tests**

Run:

```powershell
python -m pytest tests/test_novel_stores.py tests/test_novel_memory_pipeline.py -q
```

Expected: PASS, except an explicitly documented Pi Host availability skip/failure already present in the baseline.

- [ ] **Step 5: Commit**

```powershell
git add -- runtime/session_runtime_registry.py runtime/runtime_store_factory.py storage/interfaces.py tests/test_novel_stores.py
git commit -m "refactor: narrow registry to novel stores"
```

### Task 3: Extract a Novel-Only HTTP API and Web Shell

**Files:**
- Create: `runtime/novel_api.py`
- Rewrite: `scripts/awp_server.py`
- Modify: `web/src/main.tsx`
- Modify: `web/src/components/Layout.tsx`
- Rewrite: `web/src/api/client.ts`
- Modify: `web/package.json`
- Delete: `web/src/pages/Sessions.tsx`
- Delete: `web/src/pages/SessionChat.tsx`
- Delete: `web/src/pages/SessionChat.css`
- Delete: `web/src/pages/Cards.tsx`
- Delete: `web/src/components/NewSessionModal.tsx`
- Delete: `web/src/components/PipelineStreamDrawer.tsx`
- Delete: `web/src/components/PipelineStreamDrawer.css`
- Delete: `web/src/components/PresetViewer.tsx`
- Delete: `web/src/components/WorkflowSelector.tsx`
- Create: `tests/test_novel_api.py`

**Interfaces:**
- Consumes: `SessionRuntimeStoreRegistry`, `NovelEngine`, existing novel project/draft contracts.
- Produces: `register_novel_routes(app, registry_factory)` and a web client containing only `/novels` endpoints.

- [ ] **Step 1: Add API route characterization tests**

```python
def test_novel_app_registers_only_novel_and_static_routes():
    app = create_app(registry_factory=fake_registry_factory)
    paths = {resource.canonical for resource in app.router.resources()}
    assert "/awp/api/v1/novels" in paths
    assert not any("/sessions" in path or "/cards" in path for path in paths)
```

- [ ] **Step 2: Run the API test and verify it fails**

Run: `python -m pytest tests/test_novel_api.py -v`

Expected: FAIL because the standalone server currently registers RP routes and no novel routes.

- [ ] **Step 3: Extract novel handlers**

Move the novel endpoints from `runtime/management_api.py` into functions in `runtime/novel_api.py`. Route handlers receive a registry from the injected factory; no ComfyUI global is imported. Include project list/detail/delete, outline, chapter list/plan/read/write/revise, drafts, batch, ledger, characters, autonomy summary, state promotion, and concept planning.

Expose:

```python
def register_novel_routes(
    app: web.Application,
    registry_factory: Callable[[], SessionRuntimeStoreRegistry],
) -> None:
    handlers = NovelApiHandlers(registry_factory)
    app.router.add_get("/awp/api/v1/novels", handlers.list_projects)
    app.router.add_post("/awp/api/v1/novels", handlers.create_project)
    app.router.add_get(
        "/awp/api/v1/novels/{project_id}", handlers.get_project
    )
```

- [ ] **Step 4: Rewrite the standalone server**

`create_app()` constructs aiohttp, calls `register_novel_routes`, and serves the SPA. Remove console, sessions, cards, workflows, presets, automatic ComfyUI discovery, and RP dispatcher imports.

- [ ] **Step 5: Reduce the React shell**

Default `/` to `/novels`; keep only `Novels` and `NovelDetail`. Rewrite `client.ts` to retain the generic request helpers and novel types/functions beginning at the current Novel Mode section. Rename the package to `awp-novel-panel`.

- [ ] **Step 6: Run API tests and build the Web app**

Run:

```powershell
python -m pytest tests/test_novel_api.py -v
npm run build
```

Working directory for the second command: `web/`.

Expected: API tests PASS and TypeScript/Vite build succeeds.

- [ ] **Step 7: Commit**

```powershell
git add -- runtime/novel_api.py scripts/awp_server.py web/src web/package.json tests/test_novel_api.py
git commit -m "refactor: make server and web novel-only"
```

### Task 4: Remove RP Product Code, Tests, Workflows, and Documents

**Files:**
- Delete: `nodes/`
- Delete: `workflows/`
- Delete: `services/`
- Delete: `policies/`
- Delete: `testing/`
- Delete: `runtime/management_api.py`
- Delete: RP-only runtime modules listed as unreachable in `docs/architecture/2026-07-26-novel-only-cleanup-audit.md`
- Delete: RP-only contracts not imported from the retained novel/shared graph
- Delete: all non-novel tests except shared LLM adapter tests
- Delete: RP-only archived/reference/testing docs
- Delete: root RP/debug scripts and ComfyUI launch scripts
- Modify: `runtime/__init__.py`
- Modify: `contracts/__init__.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Consumes: the passing package/store/API boundary from Tasks 1-3.
- Produces: a source tree containing only novel and demonstrably shared Python modules.

- [ ] **Step 1: Generate and inspect exact deletion manifests**

Use AST import reachability rooted at:

```text
runtime/novel_*.py
contracts/novel_*.py
scripts/novel_cli.py
scripts/awp_tui.py
runtime/novel_api.py
```

Before deletion, assert every resolved path is a tracked file under the repository root and none is under `novels/` or `.omo/`.

- [ ] **Step 2: Add a forbidden-import boundary test**

```python
FORBIDDEN_PREFIXES = (
    "awp_rp_runtime_v3.nodes",
    "awp_rp_runtime_v3.policies",
    "awp_rp_runtime_v3.services",
    "awp_rp_runtime_v3.testing",
    "awp_rp_runtime_v3.runtime.persistent_turn_engine",
)

def test_novel_source_has_no_retired_rp_imports():
    for path in novel_python_files():
        text = path.read_text(encoding="utf-8")
        assert not any(prefix in text for prefix in FORBIDDEN_PREFIXES)
```

- [ ] **Step 3: Run the boundary test and verify it fails before deletion**

Run: `python -m pytest tests/test_novel_package_boundary.py -v`

Expected: FAIL while mixed entry points still reference retired modules.

- [ ] **Step 4: Delete exact RP targets**

Use `git rm -- <verified-files>` for the manifest and explicit `git rm -r -- nodes workflows services policies testing`. Do not run recursive removal against the repository root or a computed directory.

- [ ] **Step 5: Rewrite package initializers and test fixtures**

Make `runtime/__init__.py` and `contracts/__init__.py` minimal and novel-focused; do not eagerly import large module graphs. Reduce `tests/conftest.py` to the deterministic Novel Pi role fixture and remove ComfyUI stubs/RP fake fixtures.

- [ ] **Step 6: Run import and novel test groups**

Run:

```powershell
python -c "import awp_rp_runtime_v3; import awp_rp_runtime_v3.runtime.novel_engine"
python -m pytest tests/test_novel_agent_runtime.py tests/test_novel_engine.py tests/test_novel_stores.py -q
npm test
```

Expected: imports succeed, selected Python tests pass, and all Node Harness tests pass.

- [ ] **Step 7: Commit**

```powershell
git add -A
git commit -m "refactor: remove retired rp runtime"
```

### Task 5: Cleanup Verification and Documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/architecture/2026-07-26-novel-only-cleanup-audit.md`
- Create: `docs/handoffs/2026-07-26-novel-only-cleanup.md`

**Interfaces:**
- Consumes: the cleaned repository.
- Produces: accurate developer instructions and an evidence-backed cleanup handoff.

- [ ] **Step 1: Update project instructions**

Remove the two-mode identity, RP data flow, RP test count, ComfyUI node commands, and RP file map. Document the novel-only Pi interactive/role hosts, CLI/TUI, SQLite stores, authoring prerequisites, and test commands.

- [ ] **Step 2: Run repository residue searches**

Search tracked product files for:

```text
PersistentTurnEngine
ExecutionDispatcher
NODE_CLASS_MAPPINGS
/sessions
/cards
AWP RP
ComfyUI RP
```

Every remaining match must be either package compatibility naming, historical migration text needed by existing DBs, or explicitly documented.

- [ ] **Step 3: Run verification**

Run Node tests, Web build, all retained Python tests in bounded groups, `py_compile` on retained runtime modules, and `git diff --check`.

- [ ] **Step 4: Record counts and known compatibility debt**

The handoff records files removed, repository size reduction, exact tests passed, any baseline skips/failures, and why `awp_rp_runtime_v3` remains the Python import name.

- [ ] **Step 5: Commit**

```powershell
git add -- AGENTS.md docs/architecture/2026-07-26-novel-only-cleanup-audit.md docs/handoffs/2026-07-26-novel-only-cleanup.md
git commit -m "docs: hand off novel-only runtime"
```
