# Pi 小说 Agent Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Embed Pi 0.80.6 as the novel TUI Agent harness while Python `NovelEngine` remains the sole novel-business and persistence authority.

**Architecture:** A Node child process owns Pi `AgentSession` and exactly five custom novel tools. Those tools issue JSON Lines requests back to Python. Python validates requests, invokes the existing novel runtime, and maps its callbacks into the existing Textual panels.

**Tech Stack:** Python 3.10+, Pydantic v2, pytest, Node >=22.19, Node built-in `node:test`, `@earendil-works/pi-coding-agent@0.80.6`, Textual.

## Global Constraints

- Novel mode only; do not touch RP behavior, story outlines, or chapter text.
- Pin Pi to `0.80.6` and commit `agent_harness/package-lock.json`.
- Create Pi sessions with `noTools: "all"`. The model never sees Pi `bash`, `read`, `write`, `edit`, generic network, or arbitrary-path tools.
- `NovelEngine` remains the only writer of plans, drafts, ledger entries, and memory.
- Use child-process stdin/stdout JSON Lines only; do not open a port.
- `NOVEL_LLM_*` variables remain the only provider/model configuration. Persist no secret value.
- Default `NOVEL_AGENT_RUNTIME=pi`; `legacy` is manual recovery only and Pi failures never silently fall back.

---

### Task 1: Add protocol contracts and Pi connection resolution

**Files:** Create `contracts/novel_pi_protocol.py`, `tests/test_novel_pi_protocol.py`, `tests/test_novel_llm_factory.py`; modify `runtime/novel_llm_factory.py`.

**Interfaces:** `NovelPiFrame`, `NovelPiProtocolError`, `encode_frame()`, `decode_frame()`, and `NovelLLMFactory.get_pi_agent_connection()`.

- [ ] **Step 1: Write failing tests**

```python
def test_protocol_round_trip():
    frame = NovelPiFrame(kind="tool_call", request_id="r1", payload={"name": "project_status"})
    assert decode_frame(encode_frame(frame)) == frame

def test_opencode_global_model_override(monkeypatch):
    monkeypatch.setenv("NOVEL_LLM_PROVIDER", "opencode")
    monkeypatch.setenv("NOVEL_LLM_MODEL", "kimi-k2.6")
    assert NovelLLMFactory().get_pi_agent_connection().model == "kimi-k2.6"
```

- [ ] **Step 2: Run `pytest tests/test_novel_pi_protocol.py tests/test_novel_llm_factory.py -v` and verify failure**

- [ ] **Step 3: Implement the minimal protocol**

```python
class NovelPiFrame(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    kind: str
    request_id: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    def model_post_init(self, _: Any) -> None:
        if self.kind not in FRAME_KINDS:
            raise NovelPiProtocolError(f"unsupported frame kind: {self.kind}")
```

Add frozen `NovelPiConnectionConfig(provider, model, base_url, api_key_env, thinking_level="low", api_key=None)`. Its resolver maps opencode/mimo/deepseek to OpenAI-compatible endpoints and returns only the key environment-variable name. Change `get_adapter()` to use `_role_config(role)` so global `NOVEL_LLM_MODEL` applies to `brain` and Pi.

- [ ] **Step 4: Run `pytest tests/test_novel_pi_protocol.py tests/test_novel_llm_factory.py tests/test_novel_engine.py -v` and verify PASS**

- [ ] **Step 5: Commit: `git add contracts/novel_pi_protocol.py runtime/novel_llm_factory.py tests/test_novel_pi_protocol.py tests/test_novel_llm_factory.py; git commit -m "feat: add pi novel protocol contracts"`**

### Task 2: Build the closed Node Pi Host

**Files:** Create `agent_harness/package.json`, `src/novel_tools.mjs`, `src/novel_agent_host.mjs`, `resources/system-prompt.md`, three `resources/skills/*/SKILL.md` files, `test/novel_tools.test.mjs`, `test/novel_agent_host.test.mjs`, and `package-lock.json`.

**Interfaces:** `createNovelTools(requestPython)` returns exactly five `ToolDefinition`s: `project_status`, `read_chapter`, `plan_chapter`, `write_chapter`, `audit_chapter`. `NovelAgentHost.handleFrame()` accepts `init`, `prompt`, `cancel`, `tool_result`, and `shutdown`.

- [ ] **Step 1: Add the manifest and isolation test**

```json
{"name":"awp-novel-agent-harness","private":true,"type":"module","scripts":{"test":"node --test test/*.test.mjs"},"dependencies":{"@earendil-works/pi-coding-agent":"0.80.6","typebox":"1.1.38"}}
```

```javascript
test("only five project-bound tools exist", () => {
  const tools = createNovelTools(async () => ({ ok: true, content: "ok" }));
  assert.deepEqual(tools.map((tool) => tool.name), ["project_status", "read_chapter", "plan_chapter", "write_chapter", "audit_chapter"]);
});
```

- [ ] **Step 2: Run `npm install --package-lock-only && npm test` in `agent_harness/`; expected test failure before tool module exists**

- [ ] **Step 3: Implement custom tools and Host**

```javascript
import { defineTool } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

export function createNovelTools(requestPython) {
  const tool = (name, parameters) => defineTool({ name, label: name, parameters, executionMode: "sequential",
    async execute(_id, params, signal) {
      const result = await requestPython(name, params, signal);
      return { content: [{ type: "text", text: result.content }] };
    },
  });
  return [tool("project_status", Type.Object({})), tool("read_chapter", chapter), tool("plan_chapter", planArgs), tool("write_chapter", writeArgs), tool("audit_chapter", chapter)];
}
```

Import `Type` from the direct `typebox` dependency. Use `AuthStorage.inMemory()` and `ModelRegistry.inMemory()`, register the transient `openai-completions` provider with `apiKey: "$" + api_key_env`, and use `SessionManager.continueRecent(project_root, session_dir)`. Create `AgentSession` with `noTools: "all"`, the exact five-name `tools` allowlist, `customTools`, and an explicit resource loader returning only the checked-in system prompt and skills. Never call `DefaultResourceLoader`, `getAgentDir`, or user-installed extensions. Convert text deltas to `assistant_delta`, `agent_settled` to `turn_end`, and `cancel` to `session.abort()`.

- [ ] **Step 4: Run `npm test`; fake-session assertions must prove `noTools === "all"` and only five names are passed**

- [ ] **Step 5: Commit: `git add agent_harness; git commit -m "feat: add constrained pi novel agent host"`**

### Task 3: Add the Python tool service and stop blank drafts before save

**Files:** Create `runtime/novel_pi_tool_service.py`, `tests/test_novel_pi_tool_service.py`; modify `runtime/novel_engine.py`, `tests/test_novel_engine.py`.

**Interfaces:** `NovelPiToolService.execute(name, args)` is bound to exactly one current project. `NovelEngine.audit_chapter()` is read-only. Both write methods raise on blank writer output before quality, draft, ledger, or memory persistence.

- [ ] **Step 1: Write failing tests**

```python
def test_write_routes_through_streaming_engine(monkeypatch, reg):
    calls = []
    monkeypatch.setattr(NovelEngine, "write_chapter_stream", lambda self, **kw: calls.append(kw) or ChapterDraft(text="正文", char_count=2, status="accepted"))
    assert NovelPiToolService(reg, project_id="p1").execute("write_chapter", {"chapter": 1})["ok"]
    assert calls == [{"project_id": "p1", "chapter_index": 1, "write_guidance": ""}]

def test_blank_streaming_writer_does_not_save(engine, monkeypatch, reg):
    monkeypatch.setattr(engine, "_generate_with_beats_stream", lambda *args, **kwargs: "")
    with pytest.raises(RuntimeError, match="Writer returned empty output"): engine.write_chapter_stream(project_id="p1", chapter_index=1)
    assert reg.novel_chapter_draft_store.load_latest("ch1") is None
```

- [ ] **Step 2: Run `pytest tests/test_novel_pi_tool_service.py tests/test_novel_engine.py -v`; expected failure**

- [ ] **Step 3: Implement restricted dispatch**

```python
class NovelPiToolService:
    ALLOWED = frozenset({"project_status", "read_chapter", "plan_chapter", "write_chapter", "audit_chapter"})
    def execute(self, name: str, args: dict[str, object]) -> dict[str, object]:
        if name not in self.ALLOWED: raise ValueError(f"Pi tool is not allowed: {name}")
        if name == "project_status": return {"ok": True, "content": self._status()}
        chapter = int(args.get("chapter", 0))
        if chapter < 1: raise ValueError("chapter must be a positive integer")
        if name == "write_chapter":
            draft = self._engine().write_chapter_stream(project_id=self._project_id, chapter_index=chapter, write_guidance=str(args.get("write_guidance", "")))
            return {"ok": True, "content": f"第{chapter}章完成：{draft.char_count}字，{draft.status}"}
```

Never accept project ID, path, URL, SQL, or arbitrary tool names. Add `if not text or not text.strip(): raise RuntimeError("Writer returned empty output")` immediately after each `_generate_with_beats*()` result. Implement `audit_chapter()` with `NovelQualityPipeline.check_chapter()` and the existing continuity checker, returning a dict without any store save.

- [ ] **Step 4: Run `pytest tests/test_novel_pi_tool_service.py tests/test_novel_engine.py tests/test_novel_agents.py -v`; expected PASS**

- [ ] **Step 5: Commit: `git add runtime/novel_pi_tool_service.py runtime/novel_engine.py tests/test_novel_pi_tool_service.py tests/test_novel_engine.py; git commit -m "feat: route pi tools through novel engine"`**

### Task 4: Implement the locked Python bridge

**Files:** Create `runtime/novel_pi_bridge.py`, `tests/test_novel_pi_bridge.py`.

**Interfaces:** `NovelPiBridge(registry, callbacks, project_dir, project_id)` exposes `handle_message()`, `reset()`, `abort()`, and `close()`. It owns the Node child and maps Pi events to `BrainCallbacks`.

- [ ] **Step 1: Write a fake-Host lifecycle test**

```python
def test_bridge_answers_tool_call_and_forwards_delta(tmp_path, reg):
    host = write_fake_host(tmp_path, [
        {"kind":"tool_call","request_id":"r1","payload":{"tool_call_id":"t1","name":"project_status","arguments":{}}},
        {"kind":"event","request_id":"r1","payload":{"type":"assistant_delta","text":"已检查"}},
        {"kind":"turn_end","request_id":"r1","payload":{"text":"项目状态正常"}},
    ])
    bridge = NovelPiBridge(reg, BrainCallbacks(), project_dir=tmp_path, project_id="p1", host_command=[sys.executable, str(host)])
    assert bridge.handle_message("看状态") == "项目状态正常"
```

- [ ] **Step 2: Run `pytest tests/test_novel_pi_bridge.py -v`; expected failure**

- [ ] **Step 3: Implement correlated frame loop**

```python
def handle_message(self, text: str) -> str:
    with self._turn_lock:
        request_id = uuid.uuid4().hex
        self._write(NovelPiFrame(kind="prompt", request_id=request_id, payload={"text": text}))
        while True:
            frame = self._read_frame(timeout_seconds=self._TURN_TIMEOUT_SECONDS)
            self._assert_request(frame, request_id)
            if frame.kind == "tool_call": self._reply_to_tool_call(frame, request_id)
            elif frame.kind == "event": self._forward_event(frame.payload)
            elif frame.kind == "turn_end": return str(frame.payload.get("text", ""))
            elif frame.kind == "error": raise NovelPiBridgeError(str(frame.payload.get("message", "Pi Host failed")))
```

`_reply_to_tool_call()` invokes only `NovelPiToolService.execute(name, arguments)` and returns `tool_result` with original `tool_call_id`, `ok`, and string content. It maps expected validation/engine failures to `ok: false`. `_forward_event()` maps `assistant_delta` to `on_chat` and pipeline events to existing phase/beat/chunk/error callbacks. Timeout, malformed frame, unknown request ID, Host exit, and cancel return named `NovelPiBridgeError`s; init payload and environment are never logged.

- [ ] **Step 4: Run `pytest tests/test_novel_pi_protocol.py tests/test_novel_pi_tool_service.py tests/test_novel_pi_bridge.py -v`; expected PASS including timeout, tool error, cancellation, and project isolation**

- [ ] **Step 5: Commit: `git add runtime/novel_pi_bridge.py tests/test_novel_pi_bridge.py; git commit -m "feat: bridge pi sessions to novel tools"`**

### Task 5: Migrate Textual TUI with an explicit Legacy adapter

**Files:** Create `runtime/novel_agent_runtime.py`, `tests/test_novel_agent_runtime.py`; modify `scripts/awp_tui.py`.

**Interfaces:** `create_novel_agent_runtime(registry, callbacks, project_dir, project_id)` returns `PiNovelAgentRuntime` or `LegacyNovelAgentRuntime`. Both have `handle_message`, `reset`, `abort`, and `close`.

- [ ] **Step 1: Write failing selection tests**

```python
def test_pi_is_default(monkeypatch, reg, tmp_path):
    monkeypatch.delenv("NOVEL_AGENT_RUNTIME", raising=False)
    assert isinstance(create_novel_agent_runtime(reg, BrainCallbacks(), tmp_path, "p1"), PiNovelAgentRuntime)

def test_unknown_runtime_never_falls_back(monkeypatch, reg, tmp_path):
    monkeypatch.setenv("NOVEL_AGENT_RUNTIME", "other")
    with pytest.raises(ValueError, match="NOVEL_AGENT_RUNTIME"): create_novel_agent_runtime(reg, BrainCallbacks(), tmp_path, "p1")
```

- [ ] **Step 2: Run `pytest tests/test_novel_agent_runtime.py -v`; expected failure**

- [ ] **Step 3: Implement adapter and TUI changes**

```python
def create_novel_agent_runtime(registry, callbacks, project_dir: Path, project_id: str):
    runtime = os.environ.get("NOVEL_AGENT_RUNTIME", "pi").lower()
    if runtime == "pi": return PiNovelAgentRuntime(registry, callbacks, project_dir, project_id)
    if runtime == "legacy": return LegacyNovelAgentRuntime(registry, callbacks, project_dir)
    raise ValueError(f"Unsupported NOVEL_AGENT_RUNTIME: {runtime}")
```

Replace direct `_brain` creation and `handle_message` calls in `awp_tui.py` with `_agent_runtime`. Preserve `BrainCallbacks` phase, beat, chunk, and error display. Header displays `Agent: Pi` or `Agent: Legacy`. Keep `/open`, `/new`, `/list`, `/status`, session save/load, `/help`, and Ctrl+R. In Pi mode, `/search`, `/mode`, `/compress`, downloader commands, and Ctrl+S show `受限 Pi 小说 Agent 不提供此命令`. Add Ctrl+X to call `abort()` while busy, and call `close()` at unmount.

- [ ] **Step 4: Run `pytest tests/test_novel_agent_runtime.py tests/test_novel_pi_bridge.py -v` and `python -m py_compile runtime/novel_agent_runtime.py runtime/novel_pi_bridge.py scripts/awp_tui.py`; expected PASS**

- [ ] **Step 5: Commit: `git add runtime/novel_agent_runtime.py scripts/awp_tui.py tests/test_novel_agent_runtime.py; git commit -m "feat: run novel tui through pi harness"`**

### Task 6: Document and validate the harness

**Files:** Create `agent_harness/README.md`, `tests/test_novel_pi_e2e.py`; modify `AGENTS.md`, `docs/superpowers/specs/2026-07-14-pi-novel-harness-design.md`.

- [ ] **Step 1: Write opt-in read-only smoke test**

```python
@pytest.mark.skipif(os.environ.get("NOVEL_PI_E2E") != "1", reason="requires configured Pi model provider")
def test_pi_status_turn_is_read_only(seeded_registry, tmp_path):
    bridge = NovelPiBridge(seeded_registry, BrainCallbacks(), project_dir=tmp_path, project_id="p1")
    try: assert bridge.handle_message("查看当前项目状态")
    finally: bridge.close()
    assert seeded_registry.novel_chapter_draft_store.load_latest("ch-p1-1") is None
```

- [ ] **Step 2: Document commands and security boundary**

Add this exact block to `agent_harness/README.md`:

```powershell
cd F:\12\语英\awp_rp_runtime_v3\agent_harness
npm ci
npm test
$env:NOVEL_AGENT_RUNTIME = 'pi'
python scripts\awp_tui.py novels\<project-name>
```

Document `$env:NOVEL_AGENT_RUNTIME = 'legacy'` as the only manual recovery path. Update `AGENTS.md` with Host, bridge, service, five-tool allowlist, and Node test command.

- [ ] **Step 3: Run `npm test` in `agent_harness/`, then `pytest tests/test_novel_pi_*.py tests/test_novel_agent_runtime.py tests/test_novel_engine.py -v`, then `git diff --check`; expected all deterministic tests PASS and E2E SKIPPED**

- [ ] **Step 4: Only if `NOVEL_PI_E2E=1`, run `pytest tests/test_novel_pi_e2e.py -v`; expected a status-only Pi turn and no draft write**

- [ ] **Step 5: Commit: `git add agent_harness/README.md tests/test_novel_pi_e2e.py AGENTS.md docs/superpowers/specs/2026-07-14-pi-novel-harness-design.md; git commit -m "docs: verify pi novel harness integration"`**
