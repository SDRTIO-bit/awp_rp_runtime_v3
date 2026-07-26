# Novel Coding Web Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the terminal-first author workflow with a local browser workspace that streams editor and Writer output, preserves author-controlled plans, versions documents and prompts, and exposes the novel pipeline without restoring retired RP code.

**Architecture:** Extend the existing aiohttp server and React 18 application. Python owns project discovery, WebSocket sessions, local append-only events, prompt/document versions, Pi bridges, Writer execution, and all file/database mutations. React owns a three-column Coding-style workspace and renders durable server events; it never receives filesystem paths or bypasses approval rules.

**Tech Stack:** Python 3.10+, aiohttp, Pydantic v2, SQLite, embedded Pi JSONL hosts, React 18, TypeScript 5.6, Vite 6, Ant Design 5, Vitest, Testing Library.

## Global Constraints

- Default server binding is `127.0.0.1:8188`.
- Novel projects are discovered only from repository-local `novels/*/.novel_cli.json`.
- Browser requests never provide or receive arbitrary filesystem paths.
- Every author message is durably appended before it reaches Pi.
- Full-book and chapter rooms have separate Pi sessions and histories.
- Editor and Writer output use real WebSocket streaming; no simulated typing.
- Approval and execution remain separate author actions and reuse `NovelAuthoringService`.
- Author-led writing skips Architect, Director, and autonomous NPC planning.
- Documents, drafts, and prompts are read-only until explicit edit mode.
- Every save creates a new local version; no historical version is overwritten.
- A running task uses immutable author-plan and prompt snapshots.
- The UI never displays private chain-of-thought.
- Existing `.omo` files and `novels/daily_high_school/output` files are user data and must not be staged.

---

### Task 1: Project workspace catalog and server binding

**Files:**
- Create: `runtime/novel_workspace_catalog.py`
- Modify: `scripts/awp_server.py`
- Test: `tests/test_novel_workspace_catalog.py`
- Test: `tests/test_awp_server.py`

**Interfaces:**
- Produces: `NovelWorkspace(project_id: str, root: Path, db_path: Path, state: dict[str, Any])`
- Produces: `NovelWorkspaceCatalog(repository_root: Path).list() -> list[NovelWorkspace]`
- Produces: `NovelWorkspaceCatalog.require(project_id: str) -> NovelWorkspace`
- Produces: `NovelWorkspaceCatalog.registry(project_id: str) -> SessionRuntimeStoreRegistry`
- Produces: aiohttp app keys `WORKSPACE_CATALOG_KEY` and `EDITOR_SESSION_MANAGER_KEY`

- [ ] **Step 1: Write catalog path and duplicate-ID tests**

```python
def test_catalog_discovers_only_bound_novel_directories(tmp_path):
    valid = tmp_path / "novels" / "book"
    valid.mkdir(parents=True)
    (valid / ".novel_cli.json").write_text(
        json.dumps({"project_id": "book-1", "db_path": str(valid / "novel.db")}),
        encoding="utf-8",
    )
    catalog = NovelWorkspaceCatalog(tmp_path)
    workspace = catalog.require("book-1")
    assert workspace.root == valid.resolve()
    assert workspace.db_path == (valid / "novel.db").resolve()


def test_catalog_rejects_db_path_outside_project(tmp_path):
    project = tmp_path / "novels" / "book"
    project.mkdir(parents=True)
    (project / ".novel_cli.json").write_text(
        json.dumps({"project_id": "book-1", "db_path": str(tmp_path / "outside.db")}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="database escaped project root"):
        NovelWorkspaceCatalog(tmp_path).list()
```

- [ ] **Step 2: Run the new tests and verify RED**

Run: `python -m pytest tests/test_novel_workspace_catalog.py -q`
Expected: FAIL because `novel_workspace_catalog` does not exist.

- [ ] **Step 3: Implement the immutable workspace catalog**

```python
@dataclass(frozen=True)
class NovelWorkspace:
    project_id: str
    root: Path
    db_path: Path
    state: dict[str, Any]


class NovelWorkspaceCatalog:
    def __init__(self, repository_root: Path):
        self.repository_root = repository_root.resolve()
        self.novels_root = (self.repository_root / "novels").resolve()

    def list(self) -> list[NovelWorkspace]:
        workspaces = [self._load(path) for path in self.novels_root.glob("*/.novel_cli.json")]
        ids = [workspace.project_id for workspace in workspaces]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate novel project id")
        return sorted(workspaces, key=lambda item: item.project_id)

    def require(self, project_id: str) -> NovelWorkspace:
        for workspace in self.list():
            if workspace.project_id == project_id:
                return workspace
        raise KeyError(f"novel workspace not found: {project_id}")
```

The `_load` method resolves the project root and database, verifies both are under
`novels_root` and the project root respectively, and returns a copied state dictionary.
`registry` initializes the bound database and returns `SessionRuntimeStoreRegistry`.

- [ ] **Step 4: Bind the HTTP app to the catalog**

Change `create_app` to accept `workspace_catalog: NovelWorkspaceCatalog | None`,
store it on the app, and retain `registry_factory` only as an explicit compatibility
fixture for existing API unit tests. Add `/awp/api/v1/health` returning:

```json
{"data":{"status":"ok","projects":1}}
```

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_novel_workspace_catalog.py tests/test_awp_server.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add runtime/novel_workspace_catalog.py scripts/awp_server.py tests/test_novel_workspace_catalog.py tests/test_awp_server.py
git commit -m "feat: discover bound novel workspaces"
```

---

### Task 2: Durable room conversations and replayable events

**Files:**
- Create: `contracts/novel_web_event.py`
- Create: `runtime/novel_conversation_store.py`
- Modify: `contracts/__init__.py`
- Test: `tests/test_novel_conversation_store.py`

**Interfaces:**
- Produces: `NovelRoomId.parse("book" | "chapter:3") -> NovelRoomId`
- Produces: `NovelWebEvent(event_id: int, project_id: str, room: str, type: str, payload: dict, created_at: str)`
- Produces: `NovelConversationStore.append(room, type, payload) -> NovelWebEvent`
- Produces: `NovelConversationStore.replay(room, after_event_id=0, limit=500) -> list[NovelWebEvent]`
- Produces: `NovelConversationStore.complete_editor_message(room, message_id, text) -> NovelWebEvent`

- [ ] **Step 1: Write append, room isolation, and replay tests**

```python
def test_event_ids_are_durable_and_room_histories_are_isolated(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    first = store.append("book", "author_message_saved", {"text": "总纲想法"})
    second = store.append("chapter:1", "author_message_saved", {"text": "第一章想法"})
    restarted = NovelConversationStore(tmp_path, "p1")
    third = restarted.append("chapter:1", "editor_message_completed", {"text": "追问"})
    assert [first.event_id, second.event_id, third.event_id] == [1, 2, 3]
    assert [event.payload["text"] for event in restarted.replay("chapter:1")] == [
        "第一章想法",
        "追问",
    ]


def test_partial_editor_deltas_are_not_replayed_as_completed_messages(tmp_path):
    store = NovelConversationStore(tmp_path, "p1")
    store.append("chapter:1", "editor_delta", {"message_id": "m1", "text": "半句"})
    events = store.replay("chapter:1")
    assert all(event.type != "editor_message_completed" for event in events)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_novel_conversation_store.py -q`
Expected: FAIL because the contract and store do not exist.

- [ ] **Step 3: Add strict contracts**

```python
class NovelRoomId(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["book", "chapter"]
    chapter_index: int | None = Field(default=None, ge=1)

    @classmethod
    def parse(cls, value: str) -> "NovelRoomId":
        if value == "book":
            return cls(kind="book")
        if value.startswith("chapter:") and value[8:].isdigit():
            return cls(kind="chapter", chapter_index=int(value[8:]))
        raise ValueError("invalid novel room")


class NovelWebEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    event_id: int = Field(ge=1)
    project_id: str
    room: str
    type: str
    payload: dict[str, Any]
    created_at: str
```

- [ ] **Step 4: Implement append-only storage**

Store events under `.awp/authoring/conversations/<safe-room>.jsonl`. Allocate project-wide
event IDs under the same lock used by `NovelAuthoringService`, persist the last ID in
`.awp/authoring/index.json`, call `flush` and `os.fsync`, and reject malformed existing
lines instead of silently skipping them.

- [ ] **Step 5: Run focused tests**

Run: `python -m pytest tests/test_novel_conversation_store.py tests/test_novel_authoring_service.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add contracts/novel_web_event.py contracts/__init__.py runtime/novel_conversation_store.py tests/test_novel_conversation_store.py
git commit -m "feat: persist novel editor room events"
```

---

### Task 3: Pi room sessions and WebSocket editor streaming

**Files:**
- Create: `runtime/novel_editor_session_manager.py`
- Create: `runtime/novel_websocket_api.py`
- Modify: `runtime/novel_pi_bridge.py`
- Modify: `runtime/novel_agent_runtime.py`
- Modify: `scripts/awp_server.py`
- Test: `tests/test_novel_editor_session_manager.py`
- Test: `tests/test_novel_websocket_api.py`

**Interfaces:**
- Consumes: `NovelWorkspaceCatalog`, `NovelConversationStore`, `NovelPiBridge`
- Produces: `EditorRoomKey(project_id: str, room: str)`
- Produces: `EditorSessionManager.subscribe(key, websocket) -> EditorSubscription`
- Produces: `EditorSessionManager.handle_author_message(key, text, client_message_id) -> None`
- Produces: `EditorSessionManager.cancel(key) -> None`
- Produces: WebSocket route `/awp/ws/v1/novels/{project_id}/editor/{room}`

- [ ] **Step 1: Write a failing test for true deltas and completion**

```python
async def test_websocket_streams_real_editor_deltas_and_durable_completion(aiohttp_client, app):
    client = await aiohttp_client(app)
    ws = await client.ws_connect("/awp/ws/v1/novels/p1/editor/chapter:1")
    await ws.send_json({
        "type": "author_message",
        "client_message_id": "client-1",
        "text": "第一章从礼堂事故开始",
    })
    frames = [await ws.receive_json() for _ in range(4)]
    assert frames[0]["type"] == "author_message_saved"
    assert "".join(
        frame["payload"]["text"] for frame in frames if frame["type"] == "editor_delta"
    ) == "先确定事故伤害了谁。"
    assert frames[-1]["type"] == "editor_message_completed"
```

- [ ] **Step 2: Run WebSocket tests and verify RED**

Run: `python -m pytest tests/test_novel_editor_session_manager.py tests/test_novel_websocket_api.py -q`
Expected: FAIL because the manager and route do not exist.

- [ ] **Step 3: Make Pi bridge room-aware and preserve stderr diagnostics**

Add `session_id` and `session_dir` constructor parameters with safe defaults. Feed `on_chat`
deltas to the manager while preserving the existing callback API. Capture a bounded stderr
tail from the Host and include it in `NovelPiBridgeError` when stdout closes before a protocol
frame. Add a regression host that writes `missing module` to stderr and exits.

- [ ] **Step 4: Implement serialized room sessions**

Each room owns one Pi bridge and one lock. The manager:

```python
async def handle_author_message(self, key, text, client_message_id):
    session = self._require_session(key)
    async with session.turn_lock:
        saved = session.store.append(
            key.room,
            "author_message_saved",
            {"client_message_id": client_message_id, "text": text},
        )
        await session.broadcast(saved)
        result = await asyncio.to_thread(session.bridge.handle_message, text)
        completed = session.store.complete_editor_message(
            key.room, uuid.uuid4().hex, result
        )
        await session.broadcast(completed)
```

Delta callbacks use `loop.call_soon_threadsafe` to enqueue bounded events. Control events are
never dropped; adjacent `editor_delta` events may be coalesced for a slow client.

- [ ] **Step 5: Implement protocol validation and replay**

The handler accepts only:

```python
class AuthorMessageFrame(TypedDict):
    type: Literal["author_message"]
    client_message_id: str
    text: str
```

It also accepts `resume_from` and `cancel`. Reject text over 20,000 characters, unknown
types, invalid rooms, and cross-project access with structured WebSocket error events.

- [ ] **Step 6: Run focused tests**

Run: `python -m pytest tests/test_novel_pi_bridge.py tests/test_novel_editor_session_manager.py tests/test_novel_websocket_api.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add runtime/novel_pi_bridge.py runtime/novel_agent_runtime.py runtime/novel_editor_session_manager.py runtime/novel_websocket_api.py scripts/awp_server.py tests/test_novel_pi_bridge.py tests/test_novel_editor_session_manager.py tests/test_novel_websocket_api.py
git commit -m "feat: stream editor rooms over websocket"
```

---

### Task 4: Safe Web actions for plans and live Writer pipeline

**Files:**
- Modify: `runtime/novel_editor_session_manager.py`
- Modify: `runtime/novel_websocket_api.py`
- Modify: `runtime/novel_engine.py`
- Modify: `runtime/novel_trace.py`
- Test: `tests/test_novel_websocket_author_actions.py`
- Test: `tests/test_novel_websocket_pipeline.py`

**Interfaces:**
- Consumes: `NovelPiToolService.execute`, `NovelStreamCallbacks`
- Produces: `approve_plan` and `execute_plan` WebSocket input frames
- Produces: durable `author_plan_approved`, `pipeline_phase`, `writer_delta`, `quality_issue`, and `draft_version_saved` events

- [ ] **Step 1: Write authorization button tests**

```python
async def test_approve_and_execute_are_distinct_durable_author_actions(editor_socket):
    await editor_socket.send_json({
        "type": "approve_plan",
        "plan_id": "chapter-1",
        "revision": 3,
    })
    approved = await receive_type(editor_socket, "author_plan_approved")
    assert approved["payload"]["revision"] == 3

    await editor_socket.send_json({
        "type": "execute_plan",
        "plan_id": "chapter-1",
        "revision": 3,
    })
    started = await receive_type(editor_socket, "pipeline_phase")
    assert started["payload"]["phase"] == "author_plan_compile"
```

Also assert that execution before approval, stale revisions, unresolved questions, and a
plan from another project produce `action_rejected` without Writer calls.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `python -m pytest tests/test_novel_websocket_author_actions.py tests/test_novel_websocket_pipeline.py -q`
Expected: FAIL because the frames are unsupported.

- [ ] **Step 3: Route buttons through the existing safety service**

Create a canonical author action message:

```python
APPROVE_TEXT = "我确认这个计划。"
EXECUTE_TEXT = "现在执行这个计划。"
```

Allocate a new durable turn, record the canonical action as an author message with
`source="web_action"`, and call `NovelPiToolService` with the exact plan ID, revision, and
confirmation quote. Do not call `NovelAuthoringService.approve_plan` or
`NovelEngine.write_chapter_stream` directly from the socket.

- [ ] **Step 4: Forward real pipeline callbacks**

Map `NovelStreamCallbacks` to durable Web events:

```python
callbacks = NovelStreamCallbacks(
    on_phase=lambda event, name, data: emit("pipeline_phase", {
        "event": event, "phase": name, "data": public_phase_data(data),
    }),
    on_chunk=lambda text: emit("writer_delta", {"text": text}),
    on_error=lambda phase, message: emit("turn_failed", {
        "phase": phase, "message": message,
    }),
)
```

Add an explicit `skipped` phase for Architect, Director, and autonomous NPC planning in
author-led mode. Emit `draft_version_saved` only after Quality accepts and the draft store
commit completes.

- [ ] **Step 5: Verify cancellation has zero formal side effects**

Add a test that cancels during Writer streaming and asserts no new accepted draft, ledger
item, or executed status is committed. Temporary streamed text remains in a failed/cancelled
run event.

- [ ] **Step 6: Run focused and author-led regression tests**

Run: `python -m pytest tests/test_novel_websocket_author_actions.py tests/test_novel_websocket_pipeline.py tests/test_novel_author_editor_e2e.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add runtime/novel_editor_session_manager.py runtime/novel_websocket_api.py runtime/novel_engine.py runtime/novel_trace.py tests/test_novel_websocket_author_actions.py tests/test_novel_websocket_pipeline.py
git commit -m "feat: stream safe author-led pipeline actions"
```

---

### Task 5: Versioned project documents and manual draft edits

**Files:**
- Create: `contracts/novel_document.py`
- Create: `runtime/novel_document_service.py`
- Modify: `runtime/novel_api.py`
- Modify: `contracts/__init__.py`
- Test: `tests/test_novel_document_service.py`
- Test: `tests/test_novel_document_api.py`

**Interfaces:**
- Produces: `NovelDocumentKind = Literal["outline", "world", "characters", "draft"]`
- Produces: `NovelDocumentVersion(document_id, kind, revision, content_hash, source, created_at)`
- Produces: `NovelDocumentService.read(kind, resource_id="")`
- Produces: `NovelDocumentService.save(kind, content, expected_revision, resource_id="", source="author")`
- Produces: REST resources under `/awp/api/v1/novels/{project_id}/documents`

- [ ] **Step 1: Write version and optimistic-concurrency tests**

```python
def test_document_save_creates_versions_without_overwriting_history(tmp_path):
    service = NovelDocumentService(workspace(tmp_path))
    first = service.save("world", "旧世界观", expected_revision=0)
    second = service.save("world", "新世界观", expected_revision=1)
    assert service.read_version("world", 1).content == "旧世界观"
    assert second.revision == 2


def test_stale_expected_revision_is_rejected(tmp_path):
    service = NovelDocumentService(workspace(tmp_path))
    service.save("outline", "v1", expected_revision=0)
    with pytest.raises(DocumentConflictError):
        service.save("outline", "冲突内容", expected_revision=0)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_novel_document_service.py -q`
Expected: FAIL because the service does not exist.

- [ ] **Step 3: Implement allowlisted version storage**

Store metadata and immutable content under:

```text
.awp/versions/documents/<kind>/<resource-id>/v000001.json
```

Use atomic replacement for the current project file and `fsync` for version metadata.
`outline` maps only to `outline.md`, `world` maps only to `world.md`, characters map to
structured character records, and draft saves create a new `ChapterDraft` revision with
`source="author_edit"`. Recompile or update deterministic stores in the same lock before
reporting success.

- [ ] **Step 4: Add REST endpoints**

Add GET current, GET versions, GET exact version, and PUT current with:

```json
{"content":"new text","expected_revision":2}
```

Return HTTP 409 with current revision on conflict and HTTP 400 for unknown document kinds.

- [ ] **Step 5: Run service and API tests**

Run: `python -m pytest tests/test_novel_document_service.py tests/test_novel_document_api.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add contracts/novel_document.py contracts/__init__.py runtime/novel_document_service.py runtime/novel_api.py tests/test_novel_document_service.py tests/test_novel_document_api.py
git commit -m "feat: version novel documents and author edits"
```

---

### Task 6: Project prompt studio and immutable run snapshots

**Files:**
- Create: `contracts/novel_prompt_version.py`
- Create: `runtime/novel_prompt_service.py`
- Modify: `runtime/novel_llm_factory.py`
- Modify: `runtime/novel_role_runtime.py`
- Modify: `runtime/novel_api.py`
- Modify: `contracts/novel_draft.py`
- Test: `tests/test_novel_prompt_service.py`
- Test: `tests/test_novel_prompt_snapshot.py`
- Test: `tests/test_novel_prompt_api.py`

**Interfaces:**
- Produces: `PromptRole` allowlist matching actual role names
- Produces: `NovelPromptService.list_roles()`
- Produces: `NovelPromptService.resolve(role) -> ResolvedPrompt`
- Produces: `NovelPromptService.save_override(role, content, expected_revision)`
- Produces: `NovelPromptSnapshot(snapshot_id, versions: dict[str, str], hashes: dict[str, str])`

- [ ] **Step 1: Write override, rollback, and snapshot immutability tests**

```python
def test_project_override_does_not_modify_system_prompt(tmp_path):
    service = NovelPromptService(workspace(tmp_path), prompts_root=fixture_prompts())
    system = service.resolve("writer")
    override = service.save_override("writer", "项目 Writer", expected_revision=0)
    assert service.resolve("writer").content == "项目 Writer"
    assert fixture_prompts().joinpath("writer.md").read_text(encoding="utf-8") == system.content
    assert override.revision == 1


def test_running_snapshot_does_not_change_after_prompt_edit(tmp_path):
    service = NovelPromptService(workspace(tmp_path), prompts_root=fixture_prompts())
    snapshot = service.snapshot({"editor", "writer", "quality"})
    service.save_override("writer", "新 Writer", expected_revision=0)
    assert service.load_snapshot(snapshot.snapshot_id).hashes == snapshot.hashes
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_novel_prompt_service.py tests/test_novel_prompt_snapshot.py -q`
Expected: FAIL because the service and snapshot do not exist.

- [ ] **Step 3: Implement prompt roles, validation, and versions**

Allow only roles that exist in the Pi host or Python pipeline. Reject empty content, content
over 100,000 characters, missing Writer author-contract markers, and unknown roles. Store
overrides under:

```text
.awp/versions/prompts/<role>/v000001.json
.awp/prompts/<role>.md
```

Diffs are computed server-side with `difflib.unified_diff`; rollback creates a new revision
whose content equals the selected old revision.

- [ ] **Step 4: Bind snapshots to runs and drafts**

At editor or Writer task start, resolve the required roles once and create a snapshot.
Pass resolved text into the Pi resource loader/role task rather than rereading disk mid-run.
Add `prompt_snapshot_id` to the persisted draft and pipeline-run metadata.

- [ ] **Step 5: Add Prompt REST endpoints**

Expose role list, current content, version list, unified diff, save override, and restore.
Never return API keys, model connection objects, or filesystem paths.

- [ ] **Step 6: Run focused tests**

Run: `python -m pytest tests/test_novel_prompt_service.py tests/test_novel_prompt_snapshot.py tests/test_novel_prompt_api.py tests/test_novel_pi_writer.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add contracts/novel_prompt_version.py contracts/novel_draft.py runtime/novel_prompt_service.py runtime/novel_llm_factory.py runtime/novel_role_runtime.py runtime/novel_api.py tests/test_novel_prompt_service.py tests/test_novel_prompt_snapshot.py tests/test_novel_prompt_api.py
git commit -m "feat: add versioned project prompt studio"
```

---

### Task 7: Frontend test foundation and design system

**Files:**
- Modify: `web/package.json`
- Modify: `web/package-lock.json`
- Modify: `web/src/main.tsx`
- Create: `web/src/styles/tokens.css`
- Create: `web/src/styles/global.css`
- Create: `web/src/test/setup.ts`
- Create: `web/vitest.config.ts`
- Create: `web/src/components/workspace/ThemeProvider.tsx`
- Test: `web/src/components/workspace/ThemeProvider.test.tsx`

**Interfaces:**
- Produces: `WorkspaceTheme = "paper" | "graphite" | "studio"`
- Produces: `useWorkspaceTheme()`
- Produces: CSS variables for layout, typography, surfaces, borders, accents, status colors, spacing, and motion

- [ ] **Step 1: Install explicit frontend test dependencies**

Run:

```powershell
cd web
npm install --save-dev vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

Expected: `package.json` and lockfile contain exact installed versions.

- [ ] **Step 2: Write a failing theme persistence test**

```tsx
it("defaults to paper and persists graphite", async () => {
  render(<ThemeProvider><ThemeProbe /></ThemeProvider>);
  expect(screen.getByTestId("theme")).toHaveTextContent("paper");
  await userEvent.click(screen.getByRole("button", { name: "graphite" }));
  expect(localStorage.getItem("novel-coding-theme")).toBe("graphite");
  expect(document.documentElement.dataset.theme).toBe("graphite");
});
```

- [ ] **Step 3: Run the test and verify RED**

Run: `cd web; npm test -- ThemeProvider.test.tsx`
Expected: FAIL because the provider and test script do not exist.

- [ ] **Step 4: Configure Vitest and implement theme tokens**

Add scripts:

```json
{
  "test": "vitest run",
  "test:watch": "vitest"
}
```

Implement one semantic token set and override values under
`html[data-theme="graphite"]` and `html[data-theme="studio"]`. Keep manuscript
surfaces light in all themes. Respect `prefers-reduced-motion`.

- [ ] **Step 5: Run frontend tests and build**

Run: `cd web; npm test; npm run build`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add web/package.json web/package-lock.json web/vitest.config.ts web/src/test/setup.ts web/src/main.tsx web/src/styles web/src/components/workspace/ThemeProvider.tsx web/src/components/workspace/ThemeProvider.test.tsx
git commit -m "feat: establish novel workspace design system"
```

---

### Task 8: Three-column Novel Coding application shell

**Files:**
- Replace: `web/src/components/Layout.tsx`
- Create: `web/src/pages/NovelWorkspace.tsx`
- Create: `web/src/pages/NovelWorkspace.css`
- Create: `web/src/components/workspace/ProjectTree.tsx`
- Create: `web/src/components/workspace/RoomSwitcher.tsx`
- Create: `web/src/components/workspace/DocumentPane.tsx`
- Create: `web/src/api/workspace.ts`
- Modify: `web/src/main.tsx`
- Test: `web/src/pages/NovelWorkspace.test.tsx`

**Interfaces:**
- Consumes: project/document REST APIs
- Produces: route `/novels/:id/workspace/:room?`
- Produces: responsive left project tree, central room outlet, right document tabs
- Produces: `WorkspaceSelection` state containing project, room, document tab, and edit mode

- [ ] **Step 1: Write a failing shell interaction test**

```tsx
it("keeps editor conversation central while switching the right document tab", async () => {
  renderWorkspace("/novels/p1/workspace/chapter:1");
  expect(await screen.findByRole("main", { name: "第一章编辑对话" })).toBeVisible();
  await userEvent.click(screen.getByRole("tab", { name: "正文" }));
  expect(screen.getByRole("main", { name: "第一章编辑对话" })).toBeVisible();
  expect(screen.getByRole("tabpanel", { name: "正文" })).toBeVisible();
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `cd web; npm test -- NovelWorkspace.test.tsx`
Expected: FAIL because the workspace route and components do not exist.

- [ ] **Step 3: Implement focused components**

`Layout.tsx` owns only global frame and theme controls. `NovelWorkspace.tsx` composes:

```tsx
<WorkspaceShell
  projectTree={<ProjectTree selection={selection} onSelect={setSelection} />}
  conversation={<EditorRoom projectId={id} room={room} />}
  document={<DocumentPane selection={selection} />}
/>
```

Use CSS Grid `220px minmax(420px, 1fr) 360px`. Under 1000px, show the project tree and
document pane as accessible drawers. Do not reproduce the current Ant Design card grid.

- [ ] **Step 4: Add read-only document tabs and route state**

Load plan, current draft, and annotations through `web/src/api/workspace.ts`. Show explicit
empty, loading, failure, and version states. Do not add edit behavior until Task 10.

- [ ] **Step 5: Run tests and build**

Run: `cd web; npm test -- NovelWorkspace.test.tsx; npm run build`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add web/src/components/Layout.tsx web/src/pages/NovelWorkspace.tsx web/src/pages/NovelWorkspace.css web/src/components/workspace/ProjectTree.tsx web/src/components/workspace/RoomSwitcher.tsx web/src/components/workspace/DocumentPane.tsx web/src/api/workspace.ts web/src/main.tsx web/src/pages/NovelWorkspace.test.tsx
git commit -m "feat: build novel coding workspace shell"
```

---

### Task 9: Streaming editor, plan cards, and pipeline visibility

**Files:**
- Create: `web/src/hooks/useEditorSocket.ts`
- Create: `web/src/state/editorEvents.ts`
- Create: `web/src/components/workspace/EditorRoom.tsx`
- Create: `web/src/components/workspace/MessageComposer.tsx`
- Create: `web/src/components/workspace/AuthorPlanCard.tsx`
- Create: `web/src/components/workspace/PipelineTimeline.tsx`
- Create: `web/src/components/workspace/EditorRoom.css`
- Test: `web/src/hooks/useEditorSocket.test.tsx`
- Test: `web/src/components/workspace/EditorRoom.test.tsx`

**Interfaces:**
- Consumes: Task 3 and Task 4 WebSocket events
- Produces: `useEditorSocket({projectId, room})`
- Produces: ordered and deduplicated `EditorEventState`
- Produces: real incremental editor and Writer rendering, reconnect, cancel, approve, and execute controls

- [ ] **Step 1: Write reducer tests for dedupe and delta completion**

```ts
it("deduplicates replay and replaces deltas with the completed message", () => {
  const state = reduceEvents(emptyState, [
    event(1, "editor_delta", { message_id: "m1", text: "先" }),
    event(2, "editor_delta", { message_id: "m1", text: "确定" }),
    event(2, "editor_delta", { message_id: "m1", text: "确定" }),
    event(3, "editor_message_completed", { message_id: "m1", text: "先确定" }),
  ]);
  expect(state.messages).toEqual([{ id: "m1", role: "editor", text: "先确定" }]);
  expect(state.lastEventId).toBe(3);
});
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd web; npm test -- useEditorSocket.test.tsx EditorRoom.test.tsx`
Expected: FAIL because the hook, reducer, and components do not exist.

- [ ] **Step 3: Implement resilient WebSocket lifecycle**

Open a URL derived from `window.location`, send `resume_from` with the last durable event,
use exponential reconnect delays capped at 10 seconds, and keep one unsent composer draft
in `sessionStorage`. Never automatically resend a message whose acknowledgement state is
unknown.

- [ ] **Step 4: Implement editor message and action UI**

Render author messages, editor messages, decision cards, plan cards, and error cards as
semantic components. `AuthorPlanCard` enables approval only for a latest pending plan with
no unresolved questions, and enables execution only after approval. Buttons send WebSocket
actions; they never call legacy REST write endpoints.

- [ ] **Step 5: Implement visible pipeline and streaming manuscript**

`PipelineTimeline` maps phases to waiting/running/completed/failed/skipped. `writer_delta`
updates a temporary manuscript buffer in `DocumentPane`; `draft_version_saved` replaces it
with the accepted server version. Failed or cancelled buffers remain visible with a
non-final banner.

- [ ] **Step 6: Run tests and build**

Run: `cd web; npm test; npm run build`
Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add web/src/hooks/useEditorSocket.ts web/src/state/editorEvents.ts web/src/components/workspace/EditorRoom.tsx web/src/components/workspace/MessageComposer.tsx web/src/components/workspace/AuthorPlanCard.tsx web/src/components/workspace/PipelineTimeline.tsx web/src/components/workspace/EditorRoom.css web/src/hooks/useEditorSocket.test.tsx web/src/components/workspace/EditorRoom.test.tsx
git commit -m "feat: stream editor and pipeline in web workspace"
```

---

### Task 10: Document and Prompt editing with version history

**Files:**
- Create: `web/src/components/workspace/VersionedEditor.tsx`
- Create: `web/src/components/workspace/VersionHistory.tsx`
- Create: `web/src/pages/PromptStudio.tsx`
- Create: `web/src/pages/PromptStudio.css`
- Create: `web/src/api/prompts.ts`
- Modify: `web/src/components/workspace/DocumentPane.tsx`
- Modify: `web/src/components/workspace/ProjectTree.tsx`
- Modify: `web/src/main.tsx`
- Test: `web/src/components/workspace/VersionedEditor.test.tsx`
- Test: `web/src/pages/PromptStudio.test.tsx`

**Interfaces:**
- Consumes: Task 5 document APIs and Task 6 Prompt APIs
- Produces: explicit read/edit modes, optimistic saves, diff, restore, and unsaved-change guards

- [ ] **Step 1: Write failing read-only and conflict tests**

```tsx
it("does not expose an editable field until edit mode is entered", async () => {
  render(<VersionedEditor resource={worldResource} />);
  expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "编辑" }));
  expect(screen.getByRole("textbox")).toHaveValue("现有世界观");
});


it("keeps the author buffer when the server reports a revision conflict", async () => {
  server.use(conflictingSaveHandler);
  render(<VersionedEditor resource={worldResource} />);
  await enterAndSave("作者的新世界观");
  expect(screen.getByRole("textbox")).toHaveValue("作者的新世界观");
  expect(screen.getByText(/服务器已有更新/)).toBeVisible();
});
```

- [ ] **Step 2: Run tests and verify RED**

Run: `cd web; npm test -- VersionedEditor.test.tsx PromptStudio.test.tsx`
Expected: FAIL because the components do not exist.

- [ ] **Step 3: Implement versioned document editor**

Use a controlled text area, exact `expected_revision`, explicit save/cancel, and
`beforeunload` plus route blockers for dirty buffers. Version history loads on demand and
restoring an old version creates a new revision.

- [ ] **Step 4: Implement Prompt Studio**

Show roles in the left project tree. The page contains current source, system/project badge,
read/edit mode, version list, server unified diff, validation messages, restore, and remove
override. Display a fixed notice: “修改只影响之后启动的任务。”

- [ ] **Step 5: Run frontend tests and build**

Run: `cd web; npm test; npm run build`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add web/src/components/workspace/VersionedEditor.tsx web/src/components/workspace/VersionHistory.tsx web/src/pages/PromptStudio.tsx web/src/pages/PromptStudio.css web/src/api/prompts.ts web/src/components/workspace/DocumentPane.tsx web/src/components/workspace/ProjectTree.tsx web/src/main.tsx web/src/components/workspace/VersionedEditor.test.tsx web/src/pages/PromptStudio.test.tsx
git commit -m "feat: edit versioned novel documents and prompts"
```

---

### Task 11: One-click browser launcher and complete verification

**Files:**
- Create: `web.bat`
- Create: `scripts/awp_web_launcher.py`
- Modify: `README.md`
- Modify: `docs/novel_cli_guide.md`
- Modify: `docs/handoffs/2026-07-26-author-editor-agent.md`
- Test: `tests/test_awp_web_launcher.py`
- Test: `tests/test_novel_web_e2e.py`

**Interfaces:**
- Produces: `web.bat [project-name]`
- Produces: dependency preflight, health wait, browser open, and existing-server reuse
- Produces: tested author-message → plan → approve → execute → streamed draft flow

- [ ] **Step 1: Write failing launcher tests**

```python
def test_launcher_reuses_healthy_server_and_opens_workspace(monkeypatch):
    opened = []
    launcher = WebLauncher(
        repository_root=fixture_repository(),
        health_probe=lambda: True,
        browser_open=opened.append,
    )
    result = launcher.start("daily_high_school")
    assert result.started_process is False
    assert opened == ["http://127.0.0.1:8188/awp/novels/daily-high-school/workspace/chapter:1"]


def test_launcher_reports_incomplete_pi_dependencies(tmp_path):
    launcher = WebLauncher(repository_root=tmp_path)
    with pytest.raises(LauncherError, match="agent_harness.*npm ci"):
        launcher.preflight()
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_awp_web_launcher.py -q`
Expected: FAIL because the launcher does not exist.

- [ ] **Step 3: Implement deterministic launcher**

`web.bat` calls `python scripts\awp_web_launcher.py %*`. The Python launcher verifies Node,
the Pi package entrypoint, built frontend assets, and project state. It starts
`scripts/awp_server.py` hidden only when the health endpoint is unavailable, polls health
for at most 15 seconds, opens the browser, and prints a bounded actionable error on failure.

- [ ] **Step 4: Add the full local end-to-end test**

Use fake Pi and role hosts while exercising a real aiohttp app and WebSocket client. Assert:

```text
author message persisted
→ editor deltas received
→ author plan saved
→ approval action persisted
→ execution action persisted
→ author-led skip events received
→ Writer deltas received
→ accepted draft version received
→ reconnect replays no duplicates
```

- [ ] **Step 5: Run every verification layer**

Run:

```powershell
python -m pytest -q
cd agent_harness
npm test
cd ..\web
npm test
npm run build
cd ..
git diff --check
```

Expected: all tests and build pass; only explicit credential acceptance tests may skip.

- [ ] **Step 6: Perform browser fidelity and interaction QA**

Start `web.bat daily_high_school`. Verify desktop 1440×900 and a narrow viewport:

- project tree and room switching
- editor streaming and stop
- plan approve/execute state separation
- Writer stream and pipeline phase visibility
- plan/body/comment tabs
- read-only to edit transition and version history
- Prompt Studio save/diff/restore
- paper, graphite, and studio themes
- refresh/reconnect history restoration

Capture the browser implementation and compare it with the approved B mockup. Check layout,
typography, palette, manuscript treatment, spacing, icons, copy, and responsive drawers.

- [ ] **Step 7: Update user documentation**

Make `web.bat daily_high_school` the default workflow. Keep TUI documented as a compatibility
diagnostic interface, not the recommended author experience.

- [ ] **Step 8: Commit**

```powershell
git add web.bat scripts/awp_web_launcher.py tests/test_awp_web_launcher.py tests/test_novel_web_e2e.py README.md docs/novel_cli_guide.md docs/handoffs/2026-07-26-author-editor-agent.md
git commit -m "feat: launch and verify novel coding workspace"
```

---

## Plan Self-Review

- Spec coverage: workspace catalog, room isolation, local persistence, WebSocket streaming,
  safe plan actions, pipeline visibility, versioned documents, Prompt Studio, three themes,
  one-click launch, recovery, security, and testing each have an implementing task.
- Type consistency: room strings use only `book` and `chapter:<positive integer>`;
  WebSocket events use project-wide integer `event_id`; document and Prompt writes use
  `expected_revision`; accepted drafts store `prompt_snapshot_id`.
- Boundary consistency: only Python mutates files and SQLite; React sends resource IDs and
  structured content; Pi retains the existing tool allowlist.
- No implementation task restores RP, accepts arbitrary paths, displays private reasoning,
  or allows a UI button to bypass `NovelPiToolService`.
