# Novel Editor Sandbox Toolkit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the persistent Pi writing editor project-scoped file tools, pre-execution approval, visible browser tool activity, and one-level read-only worker agents.

**Architecture:** Pi exposes Coding-style tool names but delegates every operation to Python. `NovelProjectSandbox` resolves paths against the server-bound novel root, performs reads and versioned writes, classifies risk, and blocks protected or external targets. `EditorSessionManager` brokers author approvals over the existing durable WebSocket event stream; a nested Pi Session provides bounded read-only delegation.

**Tech Stack:** Python 3.10+, Pydantic v2, aiohttp WebSocket, React 18, TypeScript, Node 22.19+, `@earendil-works/pi-coding-agent` 0.80.6, pytest, Node test runner, Vitest.

## Global Constraints

- Tools may operate only inside the current server-bound novel project root.
- The model chooses tools automatically; the author does not invoke skills or slash commands.
- Python remains the only writer of project files and protected authoring state.
- `novel.db*`, `.novel_cli.json`, `.awp/authoring/**`, `.awp/pi-*/**`, approval state, audit state, and history state are not writable by generic tools.
- Absolute paths, `..`, symlink/Junction escapes, cross-project paths, network access, package installation, process launch, and ambiguous shell commands fail closed.
- Worker agents are read-only, one level deep, bounded, and cannot approve plans or start Writer.
- The editor cannot directly write a full chapter or approve its own author plan.
- Preserve all pre-existing uncommitted files under `.omo/` and `novels/daily_high_school/`.

---

## File Structure

- `contracts/novel_tool_approval.py`: strict approval mode, decision, risk, request, and result contracts.
- `runtime/novel_project_sandbox.py`: canonical path jail, protected paths, read/search, versioned text mutations, and safe command classification.
- `runtime/novel_pi_tool_service.py`: route Coding-style tool names through the sandbox and approval callback.
- `runtime/novel_brain.py`: add optional tool-event and blocking approval callbacks.
- `runtime/novel_pi_bridge.py`: forward tool activity and approval callbacks to the browser session manager.
- `runtime/novel_editor_session_manager.py`: own pending approval futures and resolve WebSocket decisions.
- `runtime/novel_websocket_api.py`: validate `tool_approval_decision` frames.
- `agent_harness/src/novel_project_tools.mjs`: Pi-compatible schemas for `read`, `ls`, `find`, `grep`, `write`, `edit`, `bash`, and `delegate_project_task`.
- `agent_harness/src/novel_worker_agent.mjs`: bounded read-only nested Pi Session.
- `agent_harness/src/novel_agent_host.mjs`: enable the new tool names and worker factory while retaining the closed resource loader.
- `agent_harness/resources/system-prompt.md`: teach the editor to inspect files before asking questions and to use tools without overstepping creative authority.
- `agent_harness/resources/skills/author-collaboration/SKILL.md`: include evidence-first project inspection and worker delegation.
- `web/src/state/editorEvents.ts`: reduce tool activity and approval events.
- `web/src/components/workspace/ToolActivity.tsx`: render tool status and approval cards.
- `web/src/components/workspace/EditorRoom.tsx`: send approval decisions.
- `web/src/components/workspace/EditorRoom.css`: keep approval controls visible and accessible.

---

### Task 1: Strict project path jail and read tools

**Files:**
- Create: `runtime/novel_project_sandbox.py`
- Create: `tests/test_novel_project_sandbox.py`

**Interfaces:**
- Produces: `NovelProjectSandbox(project_root: str | Path)`
- Produces: `resolve_relative(path: str, *, write: bool = False) -> Path`
- Produces: `execute_read(name: str, args: dict[str, Any]) -> str`

- [ ] **Step 1: Write failing containment and read tests**

```python
def test_rejects_absolute_parent_and_protected_write(tmp_path):
    sandbox = NovelProjectSandbox(tmp_path)
    with pytest.raises(ValueError, match="relative"):
        sandbox.resolve_relative(str(tmp_path / "outside.md"))
    with pytest.raises(ValueError, match="escaped"):
        sandbox.resolve_relative("../outside.md")
    with pytest.raises(ValueError, match="protected"):
        sandbox.resolve_relative(".awp/authoring/plans/x.json", write=True)

def test_reads_lists_finds_and_greps_project_text(tmp_path):
    (tmp_path / "world.md").write_text("旧礼堂\\n许妍", encoding="utf-8")
    sandbox = NovelProjectSandbox(tmp_path)
    assert "world.md" in sandbox.execute_read("ls", {"path": "."})
    assert "world.md" in sandbox.execute_read("find", {"pattern": "*.md"})
    assert "许妍" in sandbox.execute_read("grep", {"pattern": "许妍"})
    assert "旧礼堂" in sandbox.execute_read("read", {"path": "world.md"})
```

- [ ] **Step 2: Run the tests and verify missing implementation**

Run: `python -m pytest tests/test_novel_project_sandbox.py -q`  
Expected: FAIL because `NovelProjectSandbox` does not exist.

- [ ] **Step 3: Implement canonical containment**

```python
class NovelProjectSandbox:
    def __init__(self, project_root: str | Path):
        self.root = Path(project_root).resolve(strict=True)

    def resolve_relative(self, raw: str, *, write: bool = False) -> Path:
        if not raw or Path(raw).is_absolute():
            raise ValueError("project path must be relative")
        candidate = self.root.joinpath(*PurePath(raw.replace("\\", "/")).parts)
        resolved = candidate.resolve(strict=False)
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("project path escaped project root") from exc
        self._reject_reparse_escape(candidate)
        if write:
            self._reject_protected(resolved)
        return resolved
```

Implement bounded UTF-8 `read`, directory `ls`, `Path.rglob` plus `fnmatch` for `find`, and regex/literal `grep`. Skip `.awp/pi-*`, history, trash, database files, and files over the configured read limit during recursive search.

- [ ] **Step 4: Run containment tests**

Run: `python -m pytest tests/test_novel_project_sandbox.py -q`  
Expected: PASS, including Windows symlink/Junction tests when creation is permitted.

- [ ] **Step 5: Commit**

```powershell
git add -- runtime/novel_project_sandbox.py tests/test_novel_project_sandbox.py
git commit -m "feat: add novel project path sandbox"
```

### Task 2: Versioned writes and approval contracts

**Files:**
- Create: `contracts/novel_tool_approval.py`
- Modify: `runtime/novel_project_sandbox.py`
- Modify: `tests/test_novel_project_sandbox.py`
- Create: `tests/test_novel_tool_approval.py`

**Interfaces:**
- Produces: `ToolRisk = Literal["read", "write", "important", "hard_deny"]`
- Produces: `ToolApprovalRequest`
- Produces: `ToolApprovalDecision`
- Produces: `classify(name: str, args: dict[str, Any]) -> ToolApprovalRequest`
- Produces: `execute_write(name: str, args: dict[str, Any]) -> str`

- [ ] **Step 1: Write failing mutation and classification tests**

```python
def test_edit_backs_up_and_rejects_stale_hash(tmp_path):
    path = tmp_path / "outline.md"
    path.write_text("旧标题", encoding="utf-8")
    sandbox = NovelProjectSandbox(tmp_path)
    before = sandbox.content_hash("outline.md")
    sandbox.execute_write("edit", {
        "path": "outline.md",
        "expected_hash": before,
        "edits": [{"oldText": "旧标题", "newText": "新标题"}],
    })
    assert path.read_text(encoding="utf-8") == "新标题"
    assert list((tmp_path / ".awp" / "file-history").rglob("*.json"))
    with pytest.raises(ValueError, match="changed"):
        sandbox.execute_write("edit", {
            "path": "outline.md", "expected_hash": before,
            "edits": [{"oldText": "新标题", "newText": "覆盖"}],
        })

def test_risk_policy_is_fail_closed(tmp_path):
    sandbox = NovelProjectSandbox(tmp_path)
    assert sandbox.classify("read", {"path": "outline.md"}).risk == "read"
    assert sandbox.classify("write", {"path": "notes/idea.md", "content": "x"}).risk == "write"
    assert sandbox.classify("write", {"path": "output/chapter_02.md", "content": "x"}).risk == "important"
    assert sandbox.classify("bash", {"command": "curl https://example.com"}).risk == "hard_deny"
```

- [ ] **Step 2: Run focused tests**

Run: `python -m pytest tests/test_novel_project_sandbox.py tests/test_novel_tool_approval.py -q`  
Expected: FAIL on missing contracts and write methods.

- [ ] **Step 3: Implement atomic mutations and risk models**

Use Pydantic models with `extra="forbid"` and immutable fields. Write backups beneath `.awp/file-history/<escaped-relative-path>/<timestamp>-<hash>.json`, write temporary files beside the target, flush and `os.replace`, and append compact JSONL audit events beneath `.awp/tool-audit/`. Implement `write` and exact unique `edit`; send delete requests to `.awp/trash/`.

Classify `output/chapter_*.md`, multi-target operations, deletion, and large replacement as `important`. Mark all path escapes, protected writes, network/process/package commands, shell metacharacter ambiguity, and unknown tool names as `hard_deny`.

- [ ] **Step 4: Run mutation and approval tests**

Run: `python -m pytest tests/test_novel_project_sandbox.py tests/test_novel_tool_approval.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add -- contracts/novel_tool_approval.py runtime/novel_project_sandbox.py tests/test_novel_project_sandbox.py tests/test_novel_tool_approval.py
git commit -m "feat: add versioned sandbox mutations"
```

### Task 3: Pi Coding-style tools and execution routing

**Files:**
- Create: `agent_harness/src/novel_project_tools.mjs`
- Modify: `agent_harness/src/novel_tools.mjs`
- Modify: `agent_harness/src/novel_agent_host.mjs`
- Modify: `runtime/novel_pi_tool_service.py`
- Modify: `agent_harness/test/novel_agent_host.test.mjs`
- Create: `agent_harness/test/novel_project_tools.test.mjs`
- Modify: `tests/test_novel_pi_tool_service.py`

**Interfaces:**
- Consumes: `NovelProjectSandbox.classify`, `execute_read`, and `execute_write`
- Produces: `createNovelProjectTools(requestPython, options?)`
- Produces: tool service names `read`, `ls`, `find`, `grep`, `write`, `edit`, `bash`

- [ ] **Step 1: Write failing Node and Python routing tests**

```javascript
test("project tool schemas expose coding names through Python RPC", async () => {
  const calls = [];
  const tools = createNovelProjectTools(async (name, args) => {
    calls.push([name, args]);
    return { content: "ok" };
  });
  assert.deepEqual(tools.map((tool) => tool.name),
    ["read", "ls", "find", "grep", "write", "edit", "bash"]);
  await tools.find((tool) => tool.name === "read").execute("t1", { path: "outline.md" });
  assert.deepEqual(calls[0], ["read", { path: "outline.md" }]);
});
```

```python
def test_coding_tools_route_through_project_sandbox(reg, tmp_path):
    (tmp_path / "outline.md").write_text("第一章", encoding="utf-8")
    service = NovelPiToolService(reg, project_id="p1", project_dir=tmp_path)
    result = service.execute("read", {"path": "outline.md"})
    assert result["ok"] is True
    assert "第一章" in result["content"]
```

- [ ] **Step 2: Run focused tests**

Run: `cd agent_harness; npm test -- --test-name-pattern="project tool|closed tool"; cd ..; python -m pytest tests/test_novel_pi_tool_service.py -q`  
Expected: FAIL because the tool factory and allowlist entries are absent.

- [ ] **Step 3: Implement schemas and routing**

Define strict TypeBox schemas matching Pi names. Keep `executionMode: "sequential"`. Add the seven names to `NOVEL_TOOL_NAMES`, concatenate `createNovelProjectTools(requestPython)` with existing authoring tools, and route them through `NovelProjectSandbox`.

Before each operation:

```python
request = sandbox.classify(name, args)
if request.risk == "hard_deny":
    raise ValueError(request.reason)
decision = self._authorize(request)
if decision != "allow":
    raise ValueError("tool call denied")
```

`bash` accepts only the explicitly classified safe command forms; it never falls through to a raw subprocess for unknown syntax.

- [ ] **Step 4: Run Node and Python tool tests**

Run: `cd agent_harness; npm test; cd ..; python -m pytest tests/test_novel_pi_tool_service.py tests/test_novel_project_sandbox.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add -- agent_harness/src/novel_project_tools.mjs agent_harness/src/novel_tools.mjs agent_harness/src/novel_agent_host.mjs agent_harness/test runtime/novel_pi_tool_service.py tests/test_novel_pi_tool_service.py
git commit -m "feat: expose sandboxed Pi project tools"
```

### Task 4: Blocking approval broker and WebSocket protocol

**Files:**
- Modify: `runtime/novel_brain.py`
- Modify: `runtime/novel_pi_bridge.py`
- Modify: `runtime/novel_editor_session_manager.py`
- Modify: `runtime/novel_websocket_api.py`
- Modify: `tests/test_novel_pi_bridge.py`
- Modify: `tests/test_novel_editor_session_manager.py`
- Modify: `tests/test_novel_websocket_api.py`

**Interfaces:**
- Produces: `BrainCallbacks.on_tool_event(payload: dict[str, Any]) -> None`
- Produces: `BrainCallbacks.request_tool_approval(payload: dict[str, Any]) -> str`
- Produces: `EditorSessionManager.resolve_tool_approval(key, approval_id, decision, remember)`

- [ ] **Step 1: Write failing broker tests**

```python
@pytest.mark.asyncio
async def test_important_tool_waits_for_browser_decision(tmp_path):
    requested = asyncio.Event()
    runtime = _ApprovalRuntime(requested)
    manager = EditorSessionManager(_catalog(tmp_path), runtime_factory=lambda *a, **k: runtime)
    key = manager.key("p1", "book")
    turn = asyncio.create_task(manager.handle_author_message(key, "修改正文", "m1"))
    await asyncio.wait_for(requested.wait(), 1)
    approval_id = runtime.approval_id
    assert not runtime.executed
    await manager.resolve_tool_approval(key, approval_id, "allow", False)
    await turn
    assert runtime.executed
```

Add protocol tests for invalid decision, unknown approval ID, duplicate response, timeout, and denial.

- [ ] **Step 2: Run focused broker tests**

Run: `python -m pytest tests/test_novel_pi_bridge.py tests/test_novel_editor_session_manager.py tests/test_novel_websocket_api.py -q`  
Expected: FAIL because callbacks and decision frames are absent.

- [ ] **Step 3: Implement pending approval state**

Add `_RoomSession.pending_approvals: dict[str, asyncio.Future[str]]` and `session_approvals: set[tuple[str, str, str]]`. From the Pi worker thread, use `asyncio.run_coroutine_threadsafe` to emit `tool_approval_requested`, await the future for at most 120 seconds, and return `allow` or `deny`.

Validate this exact browser frame:

```json
{
  "type": "tool_approval_decision",
  "approval_id": "opaque-id",
  "decision": "allow",
  "remember": false
}
```

Persist `tool_activity`, `tool_approval_requested`, and `tool_approval_resolved` events. Never persist a still-executable capability token. On close, cancellation, timeout, or failure, resolve all pending futures as `deny`.

- [ ] **Step 4: Run broker tests**

Run: `python -m pytest tests/test_novel_pi_bridge.py tests/test_novel_editor_session_manager.py tests/test_novel_websocket_api.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add -- runtime/novel_brain.py runtime/novel_pi_bridge.py runtime/novel_editor_session_manager.py runtime/novel_websocket_api.py tests/test_novel_pi_bridge.py tests/test_novel_editor_session_manager.py tests/test_novel_websocket_api.py
git commit -m "feat: broker editor tool approvals"
```

### Task 5: Browser tool activity and approval UI

**Files:**
- Modify: `web/src/state/editorEvents.ts`
- Modify: `web/src/state/editorEvents.test.ts`
- Create: `web/src/components/workspace/ToolActivity.tsx`
- Modify: `web/src/components/workspace/EditorRoom.tsx`
- Modify: `web/src/components/workspace/EditorRoom.css`

**Interfaces:**
- Produces: `EditorEventState.toolActivity`
- Produces: `EditorEventState.pendingApprovals`
- Produces: `ToolActivity({ activity, approvals, onDecision })`

- [ ] **Step 1: Write failing reducer tests**

```typescript
it("tracks tool activity and removes resolved approvals", () => {
  let state = emptyEditorState();
  state = applyEditorEvent(state, {
    event_id: 1, type: "tool_approval_requested",
    payload: { approval_id: "a1", tool: "write", summary: "修改 outline.md" },
  });
  expect(state.pendingApprovals.a1.tool).toBe("write");
  state = applyEditorEvent(state, {
    event_id: 2, type: "tool_approval_resolved",
    payload: { approval_id: "a1", decision: "deny" },
  });
  expect(state.pendingApprovals.a1).toBeUndefined();
});
```

- [ ] **Step 2: Run the frontend test**

Run: `cd web; npm test -- --run src/state/editorEvents.test.ts`  
Expected: FAIL because the state fields are missing.

- [ ] **Step 3: Implement reducer and visible cards**

Render pending approvals above the composer with tool, normalized project-relative targets, risk reason, and buttons “本次允许”, “拒绝”, and “本会话允许同类操作”. Send `tool_approval_decision`; disable buttons after sending. Render compact tool activity in the message stream without exposing private reasoning or full file contents.

- [ ] **Step 4: Run frontend tests and build**

Run: `cd web; npm test -- --run; npm run build`  
Expected: PASS and Vite build succeeds.

- [ ] **Step 5: Commit**

```powershell
git add -- web/src/state/editorEvents.ts web/src/state/editorEvents.test.ts web/src/components/workspace/ToolActivity.tsx web/src/components/workspace/EditorRoom.tsx web/src/components/workspace/EditorRoom.css
git commit -m "feat: add browser tool approval cards"
```

### Task 6: One-level read-only worker Agent

**Files:**
- Create: `agent_harness/src/novel_worker_agent.mjs`
- Modify: `agent_harness/src/novel_project_tools.mjs`
- Modify: `agent_harness/src/novel_agent_host.mjs`
- Create: `agent_harness/test/novel_worker_agent.test.mjs`
- Modify: `runtime/novel_pi_tool_service.py`
- Modify: `tests/test_novel_pi_tool_service.py`

**Interfaces:**
- Produces: `createProjectWorkerAgent(initPayload, requestPython, resourcesDir, dependencies?)`
- Produces: `delegate_project_task({ task, focus_paths?, max_files? })`

- [ ] **Step 1: Write failing worker capability tests**

```javascript
test("worker receives only read-only project tools and cannot delegate", async () => {
  let captured;
  const worker = await createProjectWorkerAgent(init, requestPython, resources, {
    createSession: async (options) => {
      captured = options;
      return { session: fakeWorkerSession("证据：world.md:1") };
    },
  });
  const result = await worker.run({ task: "核对礼堂设定" });
  assert.deepEqual(captured.tools, ["read", "ls", "find", "grep"]);
  assert.equal(captured.tools.includes("write"), false);
  assert.equal(captured.tools.includes("delegate_project_task"), false);
  assert.match(result, /world\\.md:1/);
});
```

- [ ] **Step 2: Run worker tests**

Run: `cd agent_harness; npm test -- --test-name-pattern="worker"; cd ..`  
Expected: FAIL because the worker module is absent.

- [ ] **Step 3: Implement bounded nested Session**

Use the same in-memory provider connection and closed resource loader, a worker-only Chinese system prompt, a fresh session directory below `.awp/pi-sessions/workers`, and only read schemas. Validate task length, `focus_paths` count, `max_files <= 100`, 180-second timeout, and one active worker per editor turn. Dispose the Session in `finally`.

The main tool description must require evidence as `relative/path:line`. The worker cannot see authoring approval or pipeline tools.

- [ ] **Step 4: Run all harness tests**

Run: `cd agent_harness; npm test`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add -- agent_harness/src/novel_worker_agent.mjs agent_harness/src/novel_project_tools.mjs agent_harness/src/novel_agent_host.mjs agent_harness/test/novel_worker_agent.test.mjs runtime/novel_pi_tool_service.py tests/test_novel_pi_tool_service.py
git commit -m "feat: add read-only project worker agent"
```

### Task 7: Editor guidance and full verification

**Files:**
- Modify: `agent_harness/resources/system-prompt.md`
- Modify: `agent_harness/resources/skills/author-collaboration/SKILL.md`
- Modify: `agent_harness/test/novel_agent_host.test.mjs`
- Modify: `docs/superpowers/specs/2026-07-27-novel-editor-sandbox-toolkit-design.md`

**Interfaces:**
- Consumes all earlier tool names and policy behavior.

- [ ] **Step 1: Add failing prompt assertions**

```javascript
assert.match(systemPrompt, /先检索.*项目文件/s);
assert.match(systemPrompt, /不得用工具.*替作者决定剧情/s);
assert.match(systemPrompt, /delegate_project_task/);
```

- [ ] **Step 2: Run prompt tests**

Run: `cd agent_harness; npm test -- --test-name-pattern="real session factory"; cd ..`  
Expected: FAIL until prompt resources mention the new behavior.

- [ ] **Step 3: Update editor instructions**

Tell the editor to inspect relevant project evidence before asking the author to repeat known information, use read-only delegation for broad checks, summarize intended edits before important changes, avoid repeated denied calls, and preserve the capture/question/challenge/synthesize/confirm/handoff authoring loop.

Set the design document status to `已实施（2026-07-27）` only after verification.

- [ ] **Step 4: Run bounded full verification**

Run:

```powershell
python -m pytest tests/test_novel_project_sandbox.py tests/test_novel_tool_approval.py tests/test_novel_pi_tool_service.py tests/test_novel_pi_bridge.py tests/test_novel_editor_session_manager.py tests/test_novel_websocket_api.py -q
cd agent_harness
npm test
cd ..\web
npm test -- --run
npm run build
```

Expected: all tests pass and the frontend production build succeeds.

- [ ] **Step 5: Restart and smoke test**

Stop only the existing AWP server bound to `127.0.0.1:8188`, start `web.bat daily_high_school`, verify `/awp/api/v1/health`, connect to the editor WebSocket, and confirm the initialized Pi tool list contains the new sandboxed names. Do not send a real author message or modify generated novel files during the smoke test.

- [ ] **Step 6: Commit final integration**

```powershell
git add -- agent_harness/resources/system-prompt.md agent_harness/resources/skills/author-collaboration/SKILL.md agent_harness/test/novel_agent_host.test.mjs docs/superpowers/specs/2026-07-27-novel-editor-sandbox-toolkit-design.md
git commit -m "docs: teach editor to use sandbox tools"
```

