# Workspace and LLM Defect Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore clear author/editor conversation behavior, compact tool activity, valid plan approval controls, discoverable model settings, and reliable project-level provider/model selection.

**Architecture:** Keep the current Novel Workspace and Prompt Studio architecture. Fix each defect at its first faulty boundary: React projection/layout for workspace defects, and `NovelLLMFactory` precedence/provider resolution for configuration defects. Preserve backend authoring invariants and project-scoped runtime snapshots.

**Tech Stack:** React 18, TypeScript, Vitest, Testing Library, CSS Grid/Flexbox, Python 3.10+, pytest, aiohttp, embedded Pi Coding Agent harness.

---

## Scope and File Map

The implementation is split into two independently testable areas.

**Workspace behavior**

- Modify `web/src/components/workspace/EditorRoom.tsx`: render each streaming message independently and choose a single compact tool-activity surface.
- Modify `web/src/components/workspace/EditorRoom.css`: define all workspace grid rows explicitly; keep conversation history above messages; constrain tool activity.
- Modify `web/src/components/workspace/ConversationToolbar.tsx`: give session history a component-specific class and visible label.
- Modify `web/src/components/workspace/AuthorPlanCard.tsx`: prevent approval while blocking questions remain.
- Modify `web/src/components/workspace/TurnActivity.tsx`: make historical activity collapsed by default if it remains rendered.
- Modify `web/src/components/workspace/ProjectTree.tsx`: expose model settings as a clearly named first-level tool.
- Create `web/src/components/workspace/EditorRoom.test.tsx`: cover alternating messages, separate streams, and non-duplicated activity.
- Create `web/src/components/workspace/ToolActivity.test.tsx`: cover compact recent activity and pending approval behavior.
- Create `web/src/components/workspace/ProjectTree.test.tsx`: cover the visible model-settings entry.
- Create `web/src/pages/PromptStudio.test.tsx`: cover direct LLM-tab navigation and provider selection semantics.
- Modify `web/src/components/workspace/AuthorPlanCard.test.tsx`: replace the current regression expectation with the required gate.
- Modify `web/src/state/editorEvents.test.ts`: characterize alternating completed turns and independent partial buffers.

**Model configuration**

- Modify `runtime/novel_llm_factory.py`: enforce project-first model precedence and resolve custom OpenAI-compatible connections without falling through to DeepSeek.
- Modify `runtime/novel_api.py`: validate custom provider connection fields at the HTTP boundary while keeping secrets out of persisted data.
- Modify `web/src/pages/PromptStudio.tsx`: use an explicit custom provider ID and explain activation semantics.
- Modify `tests/test_novel_llm_factory.py`: cover provider/model precedence and custom connection resolution.
- Modify `tests/test_novel_api.py`: cover accepted and rejected custom configuration payloads.
- Modify `tests/test_novel_api_http_smoke.py`: cover persistence and retrieval of a custom provider configuration.

Do not modify the backend rule in `runtime/novel_authoring_service.py` that rejects plans with unresolved questions. Do not replace project snapshots with mutable global configuration.

## Task 1: Lock Alternating and Streaming Message Semantics

**Files:**
- Modify: `web/src/state/editorEvents.test.ts`
- Create: `web/src/components/workspace/EditorRoom.test.tsx`
- Modify: `web/src/components/workspace/EditorRoom.tsx:21-153`

- [ ] **Step 1: Add a reducer characterization for two alternating completed turns**

Append a test that applies these events in order:

```ts
it("preserves alternating author and editor messages across turns", () => {
  let state = emptyEditorState();
  const events = [
    { event_id: 1, turn_id: "t1", type: "author_message_saved", payload: { client_message_id: "a1", text: "第一问" } },
    { event_id: 2, turn_id: "t1", type: "editor_message_completed", payload: { message_id: "e1", text: "第一答" } },
    { event_id: 3, turn_id: "t1", type: "turn_completed", payload: {} },
    { event_id: 4, turn_id: "t2", type: "author_message_saved", payload: { client_message_id: "a2", text: "第二问" } },
    { event_id: 5, turn_id: "t2", type: "editor_message_completed", payload: { message_id: "e2", text: "第二答" } },
    { event_id: 6, turn_id: "t2", type: "turn_completed", payload: {} },
  ];
  for (const event of events) state = applyEditorEvent(state, event);

  expect(state.messages.map(({ id, role, turnId }) => ({ id, role, turnId }))).toEqual([
    { id: "a1", role: "author", turnId: "t1" },
    { id: "e1", role: "editor", turnId: "t1" },
    { id: "a2", role: "author", turnId: "t2" },
    { id: "e2", role: "editor", turnId: "t2" },
  ]);
});
```

- [ ] **Step 2: Run the reducer test and record the green baseline**

Run:

```powershell
cd web
npm test -- --run src/state/editorEvents.test.ts
```

Expected: PASS. This establishes that completed-message multiplicity is already correct and must not be changed while fixing streaming projection.

- [ ] **Step 3: Add a failing EditorRoom test for independent partial messages**

Mock `useEditorSocket` to return an `EditorEventState` with:

```ts
partial: { "stream-1": "第一段", "stream-2": "第二段" }
```

Render `EditorRoom` inside `MemoryRouter` and assert:

```ts
expect(screen.getAllByLabelText("编辑正在回应")).toHaveLength(2);
expect(screen.getByText("第一段")).toBeVisible();
expect(screen.getByText("第二段")).toBeVisible();
```

- [ ] **Step 4: Run the new component test and verify RED**

Run:

```powershell
cd web
npm test -- --run src/components/workspace/EditorRoom.test.tsx
```

Expected: FAIL because current code joins all partial values into one string and renders one streaming article.

- [ ] **Step 5: Render partial entries by message ID**

Replace the scalar joined `partial` value with memoized entries:

```ts
const partialMessages = useMemo(() => Object.entries(state.partial), [state.partial]);
```

Use `partialMessages.length` in the welcome-state condition and render each pair independently:

```tsx
{partialMessages.map(([messageId, text]) => (
  <article
    className="message editor streaming"
    key={messageId}
    aria-label="编辑正在回应"
    data-message-id={messageId}
  >
    <div>编辑 · 正在回应</div>
    <p>{text}<span className="cursor" /></p>
  </article>
))}
```

- [ ] **Step 6: Run focused tests and verify GREEN**

Run:

```powershell
cd web
npm test -- --run src/state/editorEvents.test.ts src/components/workspace/EditorRoom.test.tsx
```

Expected: both test files pass.

## Task 2: Fix the Workspace Row Contract and Session-History Ownership

**Files:**
- Modify: `web/src/components/workspace/EditorRoom.css:1-10`
- Modify: `web/src/components/workspace/ConversationToolbar.tsx:74-125`
- Modify: `web/src/components/workspace/EditorRoom.test.tsx`

- [ ] **Step 1: Add a structural test for the session-history region**

In `EditorRoom.test.tsx`, mock the conversation API to return one branch and assert that the toolbar has a dedicated region and visible label:

```ts
expect(screen.getByRole("toolbar", { name: "会话历史" })).toBeVisible();
expect(screen.getByText("会话历史")).toBeVisible();
```

Also assert that the toolbar appears before the message log in DOM order.

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
cd web
npm test -- --run src/components/workspace/EditorRoom.test.tsx
```

Expected: FAIL because the current toolbar has no visible label and uses the shared `.conversation-toolbar` class.

- [ ] **Step 3: Give history a dedicated class and label**

Change the wrapper in `ConversationToolbar.tsx` to:

```tsx
<div className="conversation-history-toolbar" role="toolbar" aria-label="会话历史">
  <span className="conversation-history-label">会话历史</span>
  {/* existing select and actions remain */}
</div>
```

Do not rename the page-level `.conversation-toolbar` in `NovelWorkspace.tsx`; the new class removes the ownership collision.

- [ ] **Step 4: Define all EditorRoom grid rows explicitly**

Change `.editor-room` to reserve rows for connection state, session history, scrollable messages, optional compact activity, and composer:

```css
.editor-room {
  min-height: 0;
  display: grid;
  grid-template-rows: 28px auto minmax(0, 1fr) auto auto;
  background: var(--surface-raised);
}
```

Rename the toolbar CSS selector to `.conversation-history-toolbar` and preserve the existing token-based colors, spacing, and controls. Add `.conversation-history-label` as a compact non-wrapping label. Keep `.message-scroll` as the only flexible scrolling row.

- [ ] **Step 5: Run the focused component test and build**

Run:

```powershell
cd web
npm test -- --run src/components/workspace/EditorRoom.test.tsx
npm run build
```

Expected: test passes and production build exits 0.

## Task 3: Restore the Plan Approval Gate

**Files:**
- Modify: `web/src/components/workspace/AuthorPlanCard.test.tsx`
- Modify: `web/src/components/workspace/AuthorPlanCard.tsx:1-16`

- [ ] **Step 1: Replace the incorrect unresolved-question test**

Change the first test to use `userEvent` and require the valid behavior:

```tsx
it("blocks confirmation while unresolved questions remain", async () => {
  const onApprove = vi.fn();
  render(
    <AuthorPlanCard
      plan={{
        plan_id: "chapter-1",
        revision: 1,
        status: "pending_confirmation",
        unresolved_questions: ["持钥人为什么选中陈默？"],
      }}
      onApprove={onApprove}
      onExecute={vi.fn()}
    />,
  );

  const confirm = screen.getByRole("button", { name: "确认计划" });
  expect(confirm).toBeDisabled();
  await userEvent.click(confirm);
  expect(onApprove).not.toHaveBeenCalled();
  expect(screen.getByText(/持钥人为什么选中陈默/)).toBeVisible();
});
```

- [ ] **Step 2: Run the card test and verify RED**

Run:

```powershell
cd web
npm test -- --run src/components/workspace/AuthorPlanCard.test.tsx
```

Expected: FAIL because the current button is disabled only after approval.

- [ ] **Step 3: Restore the frontend gate without changing backend rules**

Use the existing `requiresClarification` value:

```tsx
<button
  className="quiet-button"
  disabled={approved || requiresClarification}
  onClick={onApprove}
>
  确认计划
</button>
```

Keep the current blocker paragraph and execution-button rules.

- [ ] **Step 4: Run card and backend invariant tests**

Run:

```powershell
cd web
npm test -- --run src/components/workspace/AuthorPlanCard.test.tsx
cd ..
python -m pytest tests/test_novel_authoring_contracts.py tests/test_novel_websocket_author_actions.py -q
```

Expected: frontend tests pass; backend tests pass without weakening `cannot approve a plan with unresolved questions`.

## Task 4: Remove Duplicate Expanded Tool Activity From the Chat Layout

**Files:**
- Create: `web/src/components/workspace/ToolActivity.test.tsx`
- Modify: `web/src/components/workspace/EditorRoom.test.tsx`
- Modify: `web/src/components/workspace/EditorRoom.tsx:155-162`
- Modify: `web/src/components/workspace/ToolActivity.tsx:14-46`
- Modify: `web/src/components/workspace/TurnActivity.tsx:17-69`
- Modify: `web/src/components/workspace/EditorRoom.css:7,18-19`

- [ ] **Step 1: Add a failing EditorRoom test for single-surface activity**

Mock a running turn whose `activity` contains one tool entry and whose global `toolActivity` contains the same `approval_id`. Assert that the summary appears once:

```ts
expect(screen.getAllByText("读取 outline.md")).toHaveLength(1);
```

- [ ] **Step 2: Add ToolActivity behavior tests**

Cover two behaviors:

```tsx
it("renders recent completed tools as a compact strip", () => {
  // approvals is empty; activity contains completed entries
  expect(screen.getByRole("region", { name: "编辑工具活动" })).toBeVisible();
  expect(screen.queryByText("需要你的审批")).not.toBeInTheDocument();
});

it("renders pending approval actions instead of the recent strip", () => {
  // approvals contains one waiting item
  expect(screen.getByText("需要你的审批")).toBeVisible();
  expect(screen.getByRole("button", { name: "本次允许" })).toBeEnabled();
});
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```powershell
cd web
npm test -- --run src/components/workspace/EditorRoom.test.tsx src/components/workspace/ToolActivity.test.tsx
```

Expected: the duplicate-summary assertion fails because `TurnActivity` and `ToolActivity` both render the same event.

- [ ] **Step 4: Make ToolActivity the only persistent tool surface**

Remove the standalone active-turn `TurnActivity` block from `EditorRoom`. Keep `ToolActivity` for pending approval controls and the five-item compact recent strip. `state.turns` continues to retain activity and changes for the right-side Changes view; only duplicate central rendering is removed.

If `TurnActivity` remains used elsewhere or is retained for future turn diagnostics, change its expansion default from:

```ts
const isOpen = expanded[key] !== false;
```

to:

```ts
const isOpen = expanded[key] === true;
```

This prevents any future placement from expanding every record by default.

- [ ] **Step 5: Constrain compact activity to one non-growing row**

Add an explicit state modifier in `ToolActivity.tsx`:

```tsx
<section
  className={`tool-workbench ${pending.length ? "pending" : "compact"}`}
  aria-label="编辑工具活动"
>
```

Update CSS so `.tool-workbench.compact` uses `overflow-x: auto`, `overflow-y: hidden`, and a one-row maximum height. Keep `.tool-workbench.pending` allowed to grow up to the existing approval-card limit and wrap action buttons. Add `min-width: 0` and `white-space: nowrap` to `.tool-state` so long summaries scroll horizontally instead of becoming a vertical stack.

- [ ] **Step 6: Run focused tests and reducer tests**

Run:

```powershell
cd web
npm test -- --run src/components/workspace/EditorRoom.test.tsx src/components/workspace/ToolActivity.test.tsx src/state/editorEvents.test.ts
```

Expected: all focused tests pass, and the reducer still records tool activity for history/audit consumers.

## Task 5: Make AI Model Settings Discoverable

**Files:**
- Create: `web/src/components/workspace/ProjectTree.test.tsx`
- Create: `web/src/pages/PromptStudio.test.tsx`
- Modify: `web/src/components/workspace/ProjectTree.tsx:35-36`
- Modify: `web/src/pages/NovelWorkspace.tsx:28-37`
- Modify: `web/src/pages/PromptStudio.tsx:101-111,145-161`

- [ ] **Step 1: Add a failing navigation-label test**

Render `ProjectTree` with an empty chapter list and assert:

```ts
expect(screen.getByRole("button", { name: /AI 模型设置/ })).toBeVisible();
expect(screen.getByText(/供应商、模型与角色提示词/)).toBeVisible();
```

Click the button and assert `onPrompt` is called once.

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
cd web
npm test -- --run src/components/workspace/ProjectTree.test.tsx
```

Expected: FAIL because the current entry is named `Prompt Studio` and mentions only prompt versions.

- [ ] **Step 3: Rename the existing entry without adding a second settings system**

Use the existing route and callback, but render:

```tsx
<button onClick={onPrompt}>
  <span aria-hidden="true">⚙</span>
  <span>AI 模型设置<small>供应商、模型与角色提示词</small></span>
</button>
```

Do not add a second route or modal. Prompt Studio remains the single editor for prompts and LLM configuration.

- [ ] **Step 4: Default Prompt Studio to the LLM tab when opened from the model entry**

Change `onPrompt` navigation in `NovelWorkspace.tsx` to include `?tab=llm`. In `PromptStudio`, read `tab` from `useSearchParams`, initialize from `llm` or `prompts`, and update the query string when switching tabs. Add a component test that opens `/prompts?tab=llm` and sees the `LLM 模型配置` heading without a second click.

- [ ] **Step 5: Run navigation and Prompt Studio tests**

Run:

```powershell
cd web
npm test -- --run src/components/workspace/ProjectTree.test.tsx src/pages/PromptStudio.test.tsx
```

Expected: the first click from the workspace opens model configuration directly, while the prompt tab remains reachable.

## Task 6: Enforce Project-First Provider and Model Precedence

**Files:**
- Modify: `tests/test_novel_llm_factory.py`
- Modify: `runtime/novel_llm_factory.py:298-362`

- [ ] **Step 1: Add parameterized failing precedence tests**

Add a test for `opencode`, `mimo`, and `siliconflow`. Set conflicting environment values and a distinct project model:

```python
@pytest.mark.parametrize("provider", ["opencode", "mimo", "siliconflow"])
def test_project_model_wins_over_provider_environment_defaults(monkeypatch, provider):
    monkeypatch.setenv("NOVEL_LLM_PROVIDER", provider)
    monkeypatch.setenv("NOVEL_LLM_MODEL", "environment-model")
    snapshot = NovelLLMFactory.for_project(
        "project-a",
        {"writer": {"provider": provider, "model": "project-model"}},
    )

    assert snapshot.get_pi_role_connection("writer").model == "project-model"
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m pytest tests/test_novel_llm_factory.py -k "project_model_wins" -q
```

Expected: FAIL for providers whose provider-specific default calculation currently replaces `base["model"]`.

- [ ] **Step 3: Apply one explicit precedence rule**

In `_role_config_for`, calculate the model with this order:

1. `project.get("model")`
2. `NOVEL_LLM_MODEL_<ROLE>`
3. `NOVEL_LLM_MODEL`
4. provider-specific default
5. role base model

Do not overwrite a project model after it has been merged. Preserve existing GLM adjustments and Writer thinking rules.

- [ ] **Step 4: Run the full factory and snapshot suites**

Run:

```powershell
python -m pytest tests/test_novel_llm_factory.py tests/test_novel_role_runtime_snapshot.py tests/test_novel_editor_session_manager.py -q
```

Expected: all tests pass, including project isolation and immutable snapshot tests.

## Task 7: Complete Custom OpenAI-Compatible Provider Resolution

**Files:**
- Modify: `tests/test_novel_llm_factory.py`
- Modify: `tests/test_novel_api.py`
- Modify: `tests/test_novel_api_http_smoke.py`
- Modify: `runtime/novel_llm_factory.py:383-489`
- Modify: `runtime/novel_api.py:633-659`
- Modify: `web/src/pages/PromptStudio.tsx:18-23,182-217`

- [ ] **Step 1: Add a failing custom connection test**

Add:

```python
def test_custom_provider_uses_project_connection_fields(monkeypatch):
    monkeypatch.setenv("NOVEL_LLM_PROVIDER", "deepseek")
    snapshot = NovelLLMFactory.for_project(
        "project-a",
        {
            "writer": {
                "provider": "openai-compatible",
                "model": "vendor-model",
                "api_base": "https://vendor.example/v1",
                "api_key_env": "VENDOR_API_KEY",
            }
        },
    )

    connection = snapshot.get_pi_role_connection("writer")
    assert connection.provider == "awp-openai-compatible"
    assert connection.model == "vendor-model"
    assert connection.base_url == "https://vendor.example/v1"
    assert connection.api_key_env == "VENDOR_API_KEY"
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
python -m pytest tests/test_novel_llm_factory.py -k "custom_provider" -q
```

Expected: FAIL because the current unknown-provider fallback returns an `awp-deepseek` connection.

- [ ] **Step 3: Add an explicit custom-provider branch**

Use one canonical frontend/backend value: `openai-compatible`. In `_pi_role_connection_for`, require project `api_base` and `api_key_env`, and return:

```python
NovelPiConnectionConfig(
    provider="awp-openai-compatible",
    model=model,
    base_url=p_base,
    api_key_env=p_key_env,
    thinking_level=thinking_level,
    max_tokens=max_tokens,
)
```

Keep `api_key` as `None`; only the environment-variable name is persisted and transferred.

- [ ] **Step 4: Validate custom provider fields at the API boundary**

In `update_llm_config`, when a role uses `provider == "openai-compatible"`, reject missing `model`, `api_base`, or `api_key_env` with HTTP 400. Reject unsupported provider identifiers rather than silently treating them as DeepSeek. Add API tests for one accepted custom payload and one rejected incomplete payload.

- [ ] **Step 5: Align the frontend provider value**

Change the custom option ID in `PromptStudio.tsx` from `custom` to `openai-compatible`. Selecting it must preserve editable `api_base`, `api_key_env`, and `model` fields. For built-in providers, remove the provider override only when the selected provider equals `cfg._default.provider`; do not assume DeepSeek is always the effective default. The UI must not store actual secret values.

- [ ] **Step 6: Add HTTP persistence coverage**

PUT a custom Writer override, GET it back, and assert that provider, model, base URL, and key environment-variable name remain project-scoped. Use different values for project A and B so isolation cannot pass accidentally.

- [ ] **Step 7: Run model configuration suites**

Run:

```powershell
python -m pytest tests/test_novel_llm_factory.py tests/test_novel_api.py tests/test_novel_api_http_smoke.py tests/test_novel_editor_session_manager.py -q
cd web
npm test -- --run src/api/client.test.ts src/pages/PromptStudio.test.tsx
```

Expected: all tests pass and no response contains an API key value.

## Task 8: Full Verification and Manual QA

**Files:**
- Verify all modified files; no additional production edits unless a verification failure is caused by this work.

- [ ] **Step 1: Run frontend diagnostics and full tests**

Run:

```powershell
cd web
npm test
npm run build
```

Expected: all Vitest files pass; TypeScript/Vite production build exits 0.

- [ ] **Step 2: Run focused Python suites**

Run:

```powershell
python -m pytest tests/test_novel_authoring_contracts.py tests/test_novel_websocket_author_actions.py tests/test_novel_llm_factory.py tests/test_novel_role_runtime_snapshot.py tests/test_novel_editor_session_manager.py tests/test_novel_api.py tests/test_novel_api_http_smoke.py -q
```

Expected: all selected tests pass. Existing deprecation warnings may remain only if unrelated to the changed code.

- [ ] **Step 3: Run agent harness tests**

Run:

```powershell
cd agent_harness
npm test
```

Expected: provider registration and role-host tests pass with the new `awp-openai-compatible` connection metadata.

- [ ] **Step 4: Start or reuse the local web server**

Use the existing project launcher:

```powershell
.\web.bat <existing-project-name>
```

Expected: server is reachable at `http://127.0.0.1:8188/awp/` without changing project content solely for QA.

- [ ] **Step 5: Verify workspace layout at three viewports**

At `1280x900`, `768x1024`, and `375x812`, verify:

- conversation history has its own visible row above messages;
- history controls do not overlap the first message;
- author/editor completed messages remain separate and ordered;
- independent stream IDs render as independent streaming cards in the component test fixture;
- recent tool activity occupies one compact horizontal row;
- pending approval controls remain usable;
- the message area retains the flexible share of available height.

- [ ] **Step 6: Verify model-settings flow**

From the workspace, click `AI 模型设置` and verify that the LLM tab opens directly. Confirm that changing a project role shows the intended provider/model values after save and reload. Do not enter an actual API key; enter only an environment-variable name.

- [ ] **Step 7: Inspect console and network behavior**

Expected:

- zero browser console errors;
- LLM configuration GET/PUT requests return 2xx;
- unresolved plans expose a disabled confirmation button and send no approval frame;
- tool activity summaries are not duplicated in the center column.

- [ ] **Step 8: Review the final diff against scope**

Run:

```powershell
git status --short
git diff -- web/src runtime/novel_llm_factory.py runtime/novel_api.py tests
```

Expected: only the planned files changed. Preserve unrelated pre-existing worktree edits, especially the current changes in `runtime/novel_editor_session_manager.py`, `runtime/novel_pi_tool_service.py`, and `tests/test_novel_websocket_author_actions.py`.

## Execution Order and Checkpoints

Execute Tasks 1-4 first and stop for a workspace checkpoint after frontend tests and build pass. Then execute Tasks 5-7 and stop for a model-configuration checkpoint after Python/API tests pass. Task 8 is the final integrated gate.

Do not create commits unless explicitly requested. If commits are later requested, keep workspace fixes and model-configuration fixes in separate commits so either group can be reverted independently.
