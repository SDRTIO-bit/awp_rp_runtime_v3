# Pi Novel Role Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every direct novel-role LLM call with a real Pi Agent Session while keeping Python as the only state, quality, and file commit layer.

**Architecture:** A dedicated Node `NovelRoleHost` creates Pi sessions for Architect, Director, Writer, Auditor, Cleaner, and Ledger roles. Python sends typed role tasks through a synchronous JSONL bridge, services only project-bound read tools, validates results, and preserves the existing `NovelEngine` persistence flow. The existing interactive Pi Host remains separate so nested `write_chapter` calls cannot deadlock.

**Tech Stack:** Python 3.10+, Pydantic v2, synchronous subprocess/JSONL, Node.js 22.19+, `@earendil-works/pi-coding-agent` 0.80.6, TypeBox, pytest, Node test runner.

## Global Constraints

- `NOVEL_AGENT_RUNTIME=pi` is the default; only explicit `legacy` may use direct LLM adapters.
- RP mode must not change.
- Pi may not write SQLite, state, ledger, or novel files.
- Pi role sessions receive only role-allowlisted read tools; no shell, arbitrary files, network tools, `plan_chapter`, or `write_chapter`.
- The interactive Pi Host and the role Pi Host are separate processes.
- Writer sessions are keyed by `project_id + chapter_index + revision`; other role sessions are task-scoped.
- Quality rejection and invalid role output must preserve zero side effects.
- API key values remain environment-only and never enter JSONL, session files, traces, or errors.
- Pi failures never silently fall back to legacy.

---

### Task 1: Typed role protocol and execution context

**Files:**
- Create: `contracts/novel_pi_role_protocol.py`
- Create: `runtime/novel_role_context.py`
- Test: `tests/test_novel_pi_role_protocol.py`
- Test: `tests/test_novel_role_context.py`

**Interfaces:**
- Produces: `NovelPiRoleTask`, `NovelPiRoleResult`, `NovelRoleContext`, `novel_role_scope()`, `get_novel_role_context()`.
- Consumes: existing `NovelPiFrame` JSONL encoding conventions.

- [ ] **Step 1: Write failing protocol tests**

```python
def test_role_task_rejects_unknown_role():
    with pytest.raises(ValidationError):
        NovelPiRoleTask(role="shell", project_id="p1", chapter_index=1,
                        session_key="p1:1:1:writer", task_contract="x",
                        input_payload={})

def test_role_task_serialization_contains_no_api_key_value():
    task = NovelPiRoleTask(role="writer", project_id="p1", chapter_index=1,
                           revision=1, session_key="p1:1:1:writer",
                           task_contract="write beat", input_payload={"beat": 1})
    assert "api_key" not in task.model_dump_json()
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_novel_pi_role_protocol.py tests/test_novel_role_context.py -v`  
Expected: FAIL because the modules do not exist.

- [ ] **Step 3: Implement the protocol and context scope**

```python
NOVEL_PI_ROLES = frozenset({
    "architect", "director", "writer", "continuity_checker",
    "style_cleaner", "ledger_curator",
})

class NovelPiRoleTask(BaseModel):
    role: str
    project_id: str
    chapter_index: int = Field(ge=0)
    revision: int = Field(default=1, ge=1)
    phase: str = ""
    session_key: str
    task_contract: str
    input_payload: dict[str, Any]
    stream: bool = False

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in NOVEL_PI_ROLES:
            raise ValueError(f"unsupported Pi novel role: {value}")
        return value

@dataclass(frozen=True)
class NovelRoleContext:
    registry: Any
    project_id: str
    chapter_index: int
    revision: int = 1
    phase: str = ""
```

- [ ] **Step 4: Run tests and verify pass**

Run: `pytest tests/test_novel_pi_role_protocol.py tests/test_novel_role_context.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add contracts/novel_pi_role_protocol.py runtime/novel_role_context.py tests/test_novel_pi_role_protocol.py tests/test_novel_role_context.py
git commit -m "feat: add pi novel role task contracts"
```

### Task 2: Project-bound read-only role tools

**Files:**
- Create: `runtime/novel_pi_read_service.py`
- Test: `tests/test_novel_pi_read_service.py`

**Interfaces:**
- Consumes: `NovelRoleContext.registry`, project-bound novel stores.
- Produces: `NovelPiReadService.execute(name: str, arguments: dict[str, Any]) -> dict[str, Any]`.

- [ ] **Step 1: Write failing allowlist and isolation tests**

```python
def test_read_service_rejects_write_tools(service):
    with pytest.raises(ValueError, match="unsupported Pi role read tool"):
        service.execute("write_chapter", {"chapter_index": 1})

def test_read_service_cannot_select_another_project(service):
    with pytest.raises(ValueError, match="unexpected arguments"):
        service.execute("read_chapter", {"project_id": "other", "chapter_index": 1})

def test_read_service_truncates_large_payload(service):
    result = service.execute("read_ledger", {"limit": 200})
    assert len(result["content"]) <= service.MAX_CONTENT_CHARS
```

- [ ] **Step 2: Run test and verify failure**

Run: `pytest tests/test_novel_pi_read_service.py -v`  
Expected: FAIL because `NovelPiReadService` does not exist.

- [ ] **Step 3: Implement exact tools**

```python
class NovelPiReadService:
    MAX_CONTENT_CHARS = 24_000
    TOOL_NAMES = frozenset({
        "project_status", "read_project_contract", "read_chapter_plan",
        "read_chapter", "read_ledger", "read_characters", "read_write_packet",
    })

    def __init__(self, context: NovelRoleContext):
        self._context = context

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self.TOOL_NAMES:
            raise ValueError(f"unsupported Pi role read tool: {name}")
        handler = getattr(self, f"_{name}")
        content = handler(self._validate_arguments(name, arguments))
        return {"ok": True, "content": content[:self.MAX_CONTENT_CHARS]}
```

- [ ] **Step 4: Run tests and verify pass**

Run: `pytest tests/test_novel_pi_read_service.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add runtime/novel_pi_read_service.py tests/test_novel_pi_read_service.py
git commit -m "feat: add read-only pi novel role tools"
```

### Task 3: Role resources, Skill loader, and Node tool registry

**Files:**
- Create: `agent_harness/src/novel_role_tools.mjs`
- Create: `agent_harness/src/novel_role_resources.mjs`
- Create: `agent_harness/resources/roles/architect/system-prompt.md`
- Create: `agent_harness/resources/roles/director/system-prompt.md`
- Create: `agent_harness/resources/roles/writer/system-prompt.md`
- Create: `agent_harness/resources/roles/continuity_checker/system-prompt.md`
- Create: `agent_harness/resources/roles/style_cleaner/system-prompt.md`
- Create: `agent_harness/resources/roles/ledger_curator/system-prompt.md`
- Create: one focused `SKILL.md` below each role's `skills/core/` directory
- Test: `agent_harness/test/novel_role_resources.test.mjs`
- Test: `agent_harness/test/novel_role_tools.test.mjs`

**Interfaces:**
- Produces: `ROLE_TOOL_ALLOWLISTS`, `createRoleTools(role, requestPython)`, `createRoleResourceLoader(role, resourcesRoot, projectRoot)`.
- Consumes: Pi `createExtensionRuntime`, `createSyntheticSourceInfo`, TypeBox schemas.

- [ ] **Step 1: Write failing Node tests**

```javascript
test("writer gets read tools but never recursive write tools", () => {
  const names = createRoleTools("writer", async () => "").map((tool) => tool.name);
  assert(names.includes("read_write_packet"));
  assert(!names.includes("write_chapter"));
  assert(!names.includes("bash"));
});

test("role loader ignores global pi resources", () => {
  const loader = createRoleResourceLoader("writer", resourcesRoot, projectRoot);
  assert.equal(loader.getExtensions().extensions.length, 0);
  assert(loader.getSkills().skills.every((skill) => skill.filePath.startsWith(resourcesRoot) || skill.filePath.startsWith(projectRoot)));
});
```

- [ ] **Step 2: Run tests and verify failure**

Run: `cd agent_harness; npm test`  
Expected: FAIL because role resources and tools are missing.

- [ ] **Step 3: Implement role allowlists and closed resource loading**

```javascript
export const ROLE_TOOL_ALLOWLISTS = Object.freeze({
  architect: ["project_status", "read_project_contract", "read_chapter", "read_ledger", "read_characters"],
  director: ["read_project_contract", "read_chapter_plan", "read_chapter", "read_ledger", "read_characters"],
  writer: ["read_chapter_plan", "read_chapter", "read_ledger", "read_characters", "read_write_packet"],
  continuity_checker: ["read_chapter_plan", "read_chapter", "read_ledger", "read_characters"],
  style_cleaner: [],
  ledger_curator: ["read_chapter_plan", "read_chapter", "read_ledger", "read_characters"],
});
```

The loader must read built-in role resources and optional `<projectRoot>/agent/skills/*/SKILL.md`, but never `~/.pi`, `<projectRoot>/.pi`, or third-party packages.

- [ ] **Step 4: Run Node tests and verify pass**

Run: `cd agent_harness; npm test`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add agent_harness/src/novel_role_tools.mjs agent_harness/src/novel_role_resources.mjs agent_harness/resources/roles agent_harness/test
git commit -m "feat: add pi role skills and read tools"
```

### Task 4: Dedicated Pi Role Host and session lifecycle

**Files:**
- Create: `agent_harness/src/novel_role_host.mjs`
- Test: `agent_harness/test/novel_role_host.test.mjs`
- Modify: `contracts/novel_pi_protocol.py`

**Interfaces:**
- Consumes: `NovelPiRoleTask`, role resource loader, role tools, provider connection metadata.
- Produces: JSONL `role_init`, `role_prompt`, `event`, `tool_call`, `role_end`, `cancel`, `shutdown` handling.

- [ ] **Step 1: Write failing host tests**

```javascript
test("host creates a real Pi session with no built-in tools", async () => {
  const calls = [];
  await createNovelRoleSession(task, requestPython, resourcesRoot, {
    createSession: async (options) => { calls.push(options); return fakeSession(); },
  });
  assert.equal(calls[0].noTools, "all");
  assert.deepEqual(calls[0].tools, ROLE_TOOL_ALLOWLISTS.writer);
});

test("writer reuses only the same chapter revision session", async () => {
  await host.handleFrame(rolePrompt("p1:4:1:writer"));
  await host.handleFrame(rolePrompt("p1:4:1:writer"));
  await host.handleFrame(rolePrompt("p1:4:2:writer"));
  assert.equal(createdSessions, 2);
});
```

- [ ] **Step 2: Run tests and verify failure**

Run: `cd agent_harness; npm test`  
Expected: FAIL because `novel_role_host.mjs` does not exist.

- [ ] **Step 3: Implement the host**

```javascript
export class NovelRoleHost {
  constructor({ createSession = createNovelRoleSession, writeFrame = writeLine } = {}) {
    this._createSession = createSession;
    this._writeFrame = writeFrame;
    this._sessions = new Map();
    this._active = new Map();
    this._pendingTools = new Map();
  }

  async handleFrame(frame) {
    if (frame.kind === "role_prompt") return this._startRole(frame);
    if (frame.kind === "tool_result") return this._resolveTool(frame);
    if (frame.kind === "cancel") return this._cancel(frame);
    if (frame.kind === "shutdown") return this._shutdown();
    return this._error(frame.request_id, `unsupported role frame: ${frame.kind}`);
  }
}
```

Task-scoped roles are disposed after `role_end`; Writer is retained by `session_key` until `close_session`, failure, cancel, or shutdown.

- [ ] **Step 4: Run Node tests and verify pass**

Run: `cd agent_harness; npm test`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add agent_harness/src/novel_role_host.mjs agent_harness/test/novel_role_host.test.mjs contracts/novel_pi_protocol.py
git commit -m "feat: add dedicated pi novel role host"
```

### Task 5: Python Role Host bridge and receipts

**Files:**
- Create: `runtime/novel_pi_role_bridge.py`
- Create: `runtime/novel_role_receipt.py`
- Test: `tests/test_novel_pi_role_bridge.py`

**Interfaces:**
- Consumes: `NovelPiRoleTask`, `NovelRoleContext`, `NovelPiReadService`.
- Produces: `NovelPiRoleBridge.run(task, *, on_chunk=None) -> NovelPiRoleResult`, `close_session(session_key)`, `cancel(request_id)`, `close()`.

- [ ] **Step 1: Write failing bridge tests**

```python
def test_bridge_routes_only_read_tools(fake_host, role_context):
    bridge = NovelPiRoleBridge(host_command=fake_host.command)
    result = bridge.run(writer_task(), context=role_context)
    assert result.text == "正文"
    assert fake_host.received_tool_results[0]["ok"] is True

def test_bridge_does_not_fallback_when_host_fails(monkeypatch):
    bridge = NovelPiRoleBridge(host_command=["missing-pi-host"])
    with pytest.raises(NovelPiRoleBridgeError):
        bridge.run(writer_task(), context=context())
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_novel_pi_role_bridge.py -v`  
Expected: FAIL because the bridge does not exist.

- [ ] **Step 3: Implement synchronous JSONL routing**

```python
class NovelPiRoleBridge:
    def run(self, task: NovelPiRoleTask, *, context: NovelRoleContext,
            on_chunk: Callable[[str], None] | None = None) -> NovelPiRoleResult:
        request_id = uuid.uuid4().hex
        self._write(NovelPiFrame(kind="role_prompt", request_id=request_id,
                                 payload=task.model_dump()))
        while True:
            frame = self._read_frame(timeout_seconds=self._TURN_TIMEOUT_SECONDS)
            self._assert_request(frame, request_id)
            if frame.kind == "tool_call":
                self._reply_read_tool(frame, context)
            elif frame.kind == "event" and frame.payload.get("type") == "text_delta":
                if on_chunk:
                    on_chunk(str(frame.payload.get("text", "")))
            elif frame.kind == "role_end":
                return NovelPiRoleResult.model_validate(frame.payload)
            elif frame.kind == "error":
                raise NovelPiRoleBridgeError(str(frame.payload.get("message", "Pi role failed")))
```

Create `ProviderAttemptReceipt` equivalents from Pi usage/model/timing fields without logging secrets.

- [ ] **Step 4: Run bridge tests and verify pass**

Run: `pytest tests/test_novel_pi_role_bridge.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add runtime/novel_pi_role_bridge.py runtime/novel_role_receipt.py tests/test_novel_pi_role_bridge.py
git commit -m "feat: bridge python novel roles to pi sessions"
```

### Task 6: Role runtime router and explicit legacy boundary

**Files:**
- Create: `runtime/novel_role_runtime.py`
- Modify: `runtime/novel_llm_factory.py`
- Test: `tests/test_novel_role_runtime.py`
- Modify: `tests/test_novel_llm_factory.py`

**Interfaces:**
- Produces: `get_novel_role_runtime()`, `PiNovelRoleRuntime.run()`, `LegacyNovelRoleRuntime.run()`.
- Consumes: role bridge, existing direct adapters, role model configs.

- [ ] **Step 1: Write failing runtime selection tests**

```python
def test_pi_is_default_and_does_not_create_direct_adapter(monkeypatch):
    monkeypatch.delenv("NOVEL_AGENT_RUNTIME", raising=False)
    factory = NovelLLMFactory()
    with patch.object(factory, "get_adapter", side_effect=AssertionError("direct adapter used")):
        runtime = create_novel_role_runtime(llm_factory=factory, bridge=fake_bridge())
        assert runtime.runtime_name == "PiRoles"

def test_legacy_requires_explicit_env(monkeypatch):
    monkeypatch.setenv("NOVEL_AGENT_RUNTIME", "legacy")
    assert create_novel_role_runtime().runtime_name == "LegacyRoles"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_novel_role_runtime.py tests/test_novel_llm_factory.py -v`  
Expected: FAIL because the role runtime router is missing.

- [ ] **Step 3: Implement runtime routing and per-role connection maps**

```python
def create_novel_role_runtime(*, llm_factory=None, bridge=None):
    mode = os.environ.get("NOVEL_AGENT_RUNTIME", "pi").lower()
    if mode == "pi":
        return PiNovelRoleRuntime(bridge=bridge, llm_factory=llm_factory)
    if mode == "legacy":
        return LegacyNovelRoleRuntime(llm_factory=llm_factory)
    raise ValueError(f"Unsupported NOVEL_AGENT_RUNTIME: {mode}")

class PiNovelRoleRuntime:
    runtime_name = "PiRoles"

    def run(self, task, *, context, on_chunk=None):
        return self._bridge.run(task, context=context, on_chunk=on_chunk)
```

Add `NovelLLMFactory.get_pi_role_connections()` returning non-secret connection metadata for every role. Keep `get_adapter()` reachable only from legacy runtime and RP-independent tests.

- [ ] **Step 4: Run tests and verify pass**

Run: `pytest tests/test_novel_role_runtime.py tests/test_novel_llm_factory.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add runtime/novel_role_runtime.py runtime/novel_llm_factory.py tests/test_novel_role_runtime.py tests/test_novel_llm_factory.py
git commit -m "feat: route novel roles through pi by default"
```

### Task 7: Migrate Architect and Director to role tasks

**Files:**
- Modify: `runtime/novel_architect_adapter.py`
- Modify: `runtime/novel_director_adapter.py`
- Modify: `runtime/novel_engine.py`
- Modify: `tests/test_novel_agents.py`
- Create: `tests/test_novel_pi_architect_director.py`

**Interfaces:**
- Consumes: `get_novel_role_runtime()`, `novel_role_scope()`, task/result contracts.
- Produces: Architect/Director outputs through Pi in default mode with existing parsing/validation preserved.

- [ ] **Step 1: Write failing migration tests**

```python
def test_architect_uses_pi_role_runtime(monkeypatch, reg):
    runtime = recording_role_runtime(json_result=valid_plan_json())
    monkeypatch.setattr(novel_architect_adapter, "get_novel_role_runtime", lambda: runtime)
    plan = NovelArchitectAdapter(reg).plan_chapter("p1", 1, None, [], [], {})
    assert runtime.tasks[0].role == "architect"
    assert plan.scene_beats

def test_director_uses_task_scoped_pi_session(monkeypatch, reg):
    runtime = recording_role_runtime(json_result=valid_director_json())
    guidance = NovelDirectorAdapter(reg).generate_guidance(valid_plan(), {}, [], "")
    assert runtime.tasks[0].role == "director"
    assert runtime.tasks[0].session_key.startswith("task:")
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_novel_pi_architect_director.py tests/test_novel_agents.py -v`  
Expected: FAIL because both adapters still call `NovelLLMFactory.get_adapter()`.

- [ ] **Step 3: Replace direct calls with role tasks**

```python
task = NovelPiRoleTask(
    role="architect",
    project_id=project_id,
    chapter_index=chapter_index,
    session_key=f"task:{uuid.uuid4().hex}",
    task_contract=system_prompt,
    input_payload={"prompt": user_prompt, "response_format": "chapter_plan_json"},
)
result = get_novel_role_runtime().run(task, context=get_novel_role_context())
text = result.text
```

Wrap `NovelEngine.plan_chapter()` and Director execution in `novel_role_scope(registry, project_id, chapter_index, revision)`.

- [ ] **Step 4: Run tests and verify pass**

Run: `pytest tests/test_novel_pi_architect_director.py tests/test_novel_agents.py tests/test_novel_engine.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add runtime/novel_architect_adapter.py runtime/novel_director_adapter.py runtime/novel_engine.py tests/test_novel_agents.py tests/test_novel_pi_architect_director.py
git commit -m "feat: run architect and director as pi agents"
```

### Task 8: Migrate Writer with chapter session and streaming

**Files:**
- Modify: `runtime/novel_writer_adapter.py`
- Modify: `runtime/novel_engine.py`
- Create: `tests/test_novel_pi_writer.py`
- Modify: `tests/test_novel_beat_continuity.py`

**Interfaces:**
- Consumes: Writer role task, chapter-scoped context, role runtime streaming.
- Produces: same-session beat generation and existing `NovelStreamCallbacks.on_chunk` behavior.

- [ ] **Step 1: Write failing session and stream tests**

```python
def test_writer_beats_share_chapter_revision_session(monkeypatch, packet):
    runtime = recording_role_runtime(text_results=["第一段", "第二段"])
    writer = NovelWriterAdapter(registry)
    writer.generate_beat(packet, beat_index=0)
    writer.generate_beat(packet, beat_index=1)
    assert runtime.tasks[0].session_key == runtime.tasks[1].session_key
    assert runtime.tasks[0].session_key == f"{packet.project_id}:{packet.chapter_index}:{packet.revision}:writer"

def test_streamed_text_equals_final_writer_result(monkeypatch, packet):
    chunks = []
    text = writer.generate_beat_stream(packet, 0, on_chunk=chunks.append)
    assert text == "".join(chunks)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_novel_pi_writer.py tests/test_novel_beat_continuity.py -v`  
Expected: FAIL because Writer calls direct adapters.

- [ ] **Step 3: Implement Writer role calls**

```python
session_key = f"{context.project_id}:{context.chapter_index}:{context.revision}:writer"
task = NovelPiRoleTask(
    role="writer",
    project_id=context.project_id,
    chapter_index=context.chapter_index,
    revision=context.revision,
    phase=f"beat:{beat_index}",
    session_key=session_key,
    task_contract=system_prompt,
    input_payload={"prompt": prompt, "beat_index": beat_index},
    stream=on_chunk is not None,
)
result = get_novel_role_runtime().run(task, context=context, on_chunk=on_chunk)
```

Close the Writer session only after a chapter succeeds, fails, or is cancelled. Preserve existing empty/truncated output checks before persistence.

- [ ] **Step 4: Run tests and verify pass**

Run: `pytest tests/test_novel_pi_writer.py tests/test_novel_beat_continuity.py tests/test_novel_engine.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add runtime/novel_writer_adapter.py runtime/novel_engine.py tests/test_novel_pi_writer.py tests/test_novel_beat_continuity.py
git commit -m "feat: run chapter writer as a pi agent session"
```

### Task 9: Migrate continuity, cleaner, and ledger roles

**Files:**
- Modify: `runtime/novel_continuity_checker.py`
- Modify: `runtime/novel_style_cleaner.py`
- Modify: `runtime/novel_ledger_curator.py`
- Create: `tests/test_novel_pi_quality_roles.py`

**Interfaces:**
- Consumes: role runtime and current role context.
- Produces: all remaining novel LLM roles through Pi; deterministic validators unchanged.

- [ ] **Step 1: Write failing role coverage test**

```python
@pytest.mark.parametrize("role", ["continuity_checker", "style_cleaner", "ledger_curator"])
def test_quality_role_uses_pi_runtime(role, role_harness):
    role_harness.invoke(role)
    assert role_harness.runtime.tasks[-1].role == role
    assert role_harness.direct_adapter_calls == 0
```

- [ ] **Step 2: Run test and verify failure**

Run: `pytest tests/test_novel_pi_quality_roles.py -v`  
Expected: FAIL because these roles call direct adapters.

- [ ] **Step 3: Replace all remaining direct calls**

Use `NovelPiRoleTask` with task-scoped `session_key`, existing system contracts, and explicit output formats. Style Cleaner receives no tools; Continuity and Ledger receive only their role allowlists.

```python
result = get_novel_role_runtime().run(
    NovelPiRoleTask(
        role="continuity_checker",
        project_id=context.project_id,
        chapter_index=context.chapter_index,
        session_key=f"task:{uuid.uuid4().hex}",
        task_contract=system_prompt,
        input_payload={"prompt": user_prompt, "response_format": "continuity_json"},
    ),
    context=context,
)
```

- [ ] **Step 4: Prove no pi-mode direct model calls remain**

Run: `Select-String -Path runtime\novel_* -Pattern 'get_adapter\('`  
Expected: matches only `novel_llm_factory.py` and the explicit legacy runtime.

Run: `pytest tests/test_novel_pi_quality_roles.py tests/test_novel_agents.py tests/test_novel_memory_pipeline.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add runtime/novel_continuity_checker.py runtime/novel_style_cleaner.py runtime/novel_ledger_curator.py tests/test_novel_pi_quality_roles.py
git commit -m "feat: run novel quality roles as pi agents"
```

### Task 10: Make CLI and TUI expose the real role runtime

**Files:**
- Modify: `scripts/novel_cli.py`
- Modify: `scripts/awp_tui.py`
- Modify: `agent_harness/README.md`
- Modify: `AGENTS.md`
- Create: `tests/test_novel_cli_pi_runtime.py`

**Interfaces:**
- Consumes: role runtime router and Pi dependency diagnostics.
- Produces: visible runtime/model banners and actionable startup failures.

- [ ] **Step 1: Write failing CLI routing tests**

```python
def test_cli_plan_reports_pi_role_runtime(monkeypatch, capsys):
    monkeypatch.delenv("NOVEL_AGENT_RUNTIME", raising=False)
    command = cli_parser().parse_args(["plan", str(project_dir), "4"])
    with patch("awp_rp_runtime_v3.runtime.novel_role_runtime.get_novel_role_runtime", return_value=fake_pi_runtime()):
        command.func(command)
    assert "Agent Runtime: Pi role agents" in capsys.readouterr().out

def test_cli_pi_missing_dependencies_does_not_fallback(monkeypatch):
    monkeypatch.delenv("NOVEL_AGENT_RUNTIME", raising=False)
    with pytest.raises(RuntimeError, match="npm ci"):
        assert_pi_role_runtime_ready(project_root)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_novel_cli_pi_runtime.py -v`  
Expected: FAIL because the banner and readiness check are absent.

- [ ] **Step 3: Add runtime diagnostics and documentation**

```python
def _print_agent_runtime_banner() -> None:
    runtime = get_novel_role_runtime()
    model = NovelLLMFactory.get_instance().get_model("writer")
    provider = NovelLLMFactory.get_instance()._provider_choice("writer")
    print(f"Agent Runtime: {runtime.display_name}")
    print(f"Provider/Model: {provider} / {model}")
```

Call the readiness check only for `plan/write/batch/run`, not `status/export`. Document `npm ci`, default Pi behavior, and explicit legacy override.

- [ ] **Step 4: Run CLI/TUI tests and verify pass**

Run: `pytest tests/test_novel_cli_pi_runtime.py tests/test_novel_agent_runtime.py -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add scripts/novel_cli.py scripts/awp_tui.py agent_harness/README.md AGENTS.md tests/test_novel_cli_pi_runtime.py
git commit -m "feat: expose pi role agents in novel cli"
```

### Task 11: Nested-host integration, full regression, and real Kimi acceptance

**Files:**
- Create: `tests/test_novel_pi_nested_hosts.py`
- Create: `tests/test_novel_pi_role_e2e.py`
- Modify: `docs/superpowers/specs/2026-07-14-pi-novel-role-agents-design.md`

**Interfaces:**
- Consumes: completed interactive host, role host, CLI, fake and real providers.
- Produces: evidence that the selected architecture is live end-to-end.

- [ ] **Step 1: Add nested-host integration test**

```python
def test_top_level_pi_write_tool_can_complete_via_separate_role_host(tmp_project):
    top_host = FakeTopLevelPiHost(tool="write_chapter")
    role_host = FakeRolePiHost(results=complete_role_results())
    runtime = create_novel_agent_runtime(top_host=top_host, role_host=role_host)
    runtime.prompt("规划并写第4章")
    assert role_host.roles == ["architect", "director", "writer", "continuity_checker", "ledger_curator"]
    assert top_host.completed_without_deadlock
```

- [ ] **Step 2: Run focused integration tests**

Run: `pytest tests/test_novel_pi_nested_hosts.py tests/test_novel_pi_bridge.py tests/test_novel_pi_role_bridge.py -v`  
Expected: PASS.

- [ ] **Step 3: Run complete local verification**

Run: `cd agent_harness; npm test`  
Expected: all Node tests pass.

Run: `pytest -q` from a package-valid workspace path named `awp_rp_runtime_v3`.  
Expected: all tests pass; opt-in external-model tests may skip.

Run: `python -m py_compile runtime/novel_pi_role_bridge.py runtime/novel_role_runtime.py runtime/novel_engine.py scripts/novel_cli.py`  
Expected: exit code 0.

- [ ] **Step 4: Run opt-in real Kimi single-chapter acceptance**

```powershell
$env:NOVEL_AGENT_RUNTIME = 'pi'
$env:NOVEL_LLM_PROVIDER = 'opencode'
$env:NOVEL_LLM_MODEL = 'kimi-k2.6'
$env:NOVEL_PI_ROLE_E2E = '1'
pytest tests/test_novel_pi_role_e2e.py -v
```

Expected: plan -> write -> audit -> export succeeds; trace proves every LLM role used a Pi Session and no direct adapter.

- [ ] **Step 5: Record verification and commit**

Update the design document's status and verification section with exact commands/results.

```powershell
git add tests/test_novel_pi_nested_hosts.py tests/test_novel_pi_role_e2e.py docs/superpowers/specs/2026-07-14-pi-novel-role-agents-design.md
git commit -m "test: verify pi novel role agent migration"
```

