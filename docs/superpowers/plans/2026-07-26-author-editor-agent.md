# Author-Led Editor Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the default Pi interaction Agent a persistent, non-flattering writing editor that captures author ideas, develops an author-approved chapter plan, and starts Writer without an Architect rewrite.

**Architecture:** Add a project-bound authoring domain with append-only journals, material inbox entries, versioned author plans, and deterministic compilation to existing `ChapterPlan`/Writer contracts. The Pi Host gets an automatic collaboration Skill and constrained authoring tools; approval and execution are enforced across distinct author turns by Python.

**Tech Stack:** Python 3.10+, Pydantic v2, JSON/JSONL local files, embedded Pi Coding Agent 0.80.6, Node.js >=22.19, TypeBox, Textual, pytest, Node test runner.

## Global Constraints

- The default runtime is the dedicated Pi writing editor; legacy NovelBrain remains explicit fallback only.
- Authors never need `/skill` or a fixed invocation phrase.
- Every author message is written locally before it is sent to Pi.
- Unconfirmed material never enters canonical settings, chapter plans, or Writer input.
- The author-approved plan is the only plot authority.
- Default author-led execution never calls Architect.
- AuthorPlanCompiler is deterministic and makes no LLM calls.
- The conversational Agent does not write a full chapter itself.
- Proposal, approval, and execution occur on distinct author turns.
- Python is the only project file/state writer.
- All authoring paths are fixed under `<project>/.awp/authoring`; tools accept no arbitrary path.
- Writer output-format/mechanical rules may not override author-approved creative choices.

---

### Task 1: Define the Authoring Contracts

**Files:**
- Create: `contracts/novel_authoring.py`
- Modify: `contracts/__init__.py`
- Create: `tests/test_novel_authoring_contracts.py`

**Interfaces:**
- Produces:
  - `AuthorMaterial`
  - `AuthorScene`
  - `AuthorCharacterIntent`
  - `AuthorChapterPlan`
  - `AuthorPlanStatus`
  - `AuthorApproval`

- [ ] **Step 1: Write failing contract tests**

```python
def test_author_plan_defaults_to_draft_and_preserves_author_language():
    plan = AuthorChapterPlan.model_validate({
        "plan_id": "author-ch3",
        "project_id": "novel-1",
        "chapter_index": 3,
        "purpose": "让她第一次承认自己其实害怕被留下",
        "confirmed_events": ["她主动返回空教室", "她没有道歉，只把钥匙交出去"],
        "scenes": [{
            "scene_id": "s1",
            "summary": "两人在空教室交接钥匙",
            "change": "关系从回避变成暂时合作",
        }],
    })
    assert plan.status == AuthorPlanStatus.DRAFT
    assert plan.confirmed_events[1] == "她没有道歉，只把钥匙交出去"


def test_approved_plan_rejects_blocking_unresolved_questions():
    with pytest.raises(ValueError, match="unresolved"):
        AuthorChapterPlan.model_validate({
            "plan_id": "author-ch3",
            "project_id": "novel-1",
            "chapter_index": 3,
            "purpose": "让她第一次承认自己其实害怕被留下",
            "confirmed_events": ["她主动返回空教室"],
            "scenes": [{
                "scene_id": "s1",
                "summary": "她返回空教室",
                "change": "她决定交出钥匙",
            }],
            "status": "approved",
            "unresolved_questions": ["她为什么回来？"],
        })
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_novel_authoring_contracts.py -v`

Expected: FAIL because the contracts do not exist.

- [ ] **Step 3: Implement strict Pydantic contracts**

Use `ConfigDict(extra="forbid")`. Keep author text verbatim. `AuthorChapterPlan` includes:

```python
plan_id: str
project_id: str
chapter_index: int
revision: int = 1
status: AuthorPlanStatus = AuthorPlanStatus.DRAFT
title: str = ""
target_chars: int = 3000
purpose: str
target_reader_effect: str = ""
confirmed_events: list[str]
causal_chain: list[str] = []
scenes: list[AuthorScene]
character_intents: list[AuthorCharacterIntent] = []
world_constraints: list[str] = []
information_distribution: list[str] = []
must_keep: list[str] = []
must_not: list[str] = []
deliberate_ambiguities: list[str] = []
writer_freedom: list[str] = []
unresolved_questions: list[str] = []
source_material_ids: list[str] = []
proposal_turn: int = 0
approval: AuthorApproval | None = None
```

An `approved` plan must contain at least one scene and no unresolved questions.

- [ ] **Step 4: Run contract tests**

Run: `python -m pytest tests/test_novel_authoring_contracts.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add -- contracts/novel_authoring.py contracts/__init__.py tests/test_novel_authoring_contracts.py
git commit -m "feat: define authoring contracts"
```

### Task 2: Implement Safe Local Authoring Storage

**Files:**
- Create: `runtime/novel_authoring_service.py`
- Create: `tests/test_novel_authoring_service.py`

**Interfaces:**
- Consumes: `AuthorMaterial`, `AuthorChapterPlan`, fixed `project_root`.
- Produces:
  - `record_author_message(text: str, session_id: str, turn: int) -> str`
  - `capture_material(summary: str, category: str, source_message_ids: list[str]) -> AuthorMaterial`
  - `save_plan(plan: AuthorChapterPlan) -> AuthorChapterPlan`
  - `get_plan(plan_id: str, revision: int | None = None) -> AuthorChapterPlan`
  - `approve_plan(plan_id: str, revision: int, current_turn: int, current_message_id: str, current_author_message: str, confirmation_quote: str) -> AuthorChapterPlan`
  - `mark_executed(plan_id: str, revision: int, current_turn: int, current_message_id: str, current_author_message: str, confirmation_quote: str) -> AuthorChapterPlan`
  - `authoring_context(chapter_index: int | None = None) -> dict`

- [ ] **Step 1: Write failing persistence and path tests**

```python
def test_message_is_appended_before_any_agent_work(tmp_path):
    service = NovelAuthoringService(tmp_path, "novel-1")
    message_id = service.record_author_message("她其实不想赢。", "session-1", 1)
    rows = read_jsonl(tmp_path / ".awp/authoring/journal" / today_file())
    assert rows[0]["message_id"] == message_id
    assert rows[0]["text"] == "她其实不想赢。"


def test_plan_versions_never_overwrite(tmp_path):
    service.save_plan(plan_v1)
    saved_v2 = service.save_plan(plan_v1.model_copy(update={"purpose": "新目的"}))
    assert saved_v2.revision == 2
    assert service.get_plan(plan_v1.plan_id, 1).purpose == plan_v1.purpose


def test_service_never_accepts_an_external_path(tmp_path):
    assert "path" not in inspect.signature(service.save_plan).parameters
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_novel_authoring_service.py -v`

Expected: FAIL because the service does not exist.

- [ ] **Step 3: Implement fixed-layout, atomic storage**

Use:

```text
.awp/authoring/journal/YYYY-MM-DD.jsonl
.awp/authoring/inbox.jsonl
.awp/authoring/chapter-plans/<plan-id>.v<revision>.json
.awp/authoring/index.json
```

Append JSONL with UTF-8 and flush before returning. Write plan/index JSON through a sibling `.tmp`, `flush`, `os.fsync`, then `Path.replace`. Reject a resolved authoring root that is not beneath the resolved project root.

- [ ] **Step 4: Implement cross-turn approvals**

`approve_plan` requires:

```python
current_turn > plan.proposal_turn
confirmation_quote in current_author_message
is_explicit_approval(current_author_message)
plan.revision == latest_revision
```

Save approval message ID, quote, turn, timestamp, and content hash. Execution requires a later turn than approval and an explicit execution phrase.

- [ ] **Step 5: Run service tests**

Run: `python -m pytest tests/test_novel_authoring_service.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add -- runtime/novel_authoring_service.py tests/test_novel_authoring_service.py
git commit -m "feat: persist author conversations and plans"
```

### Task 3: Compile Author Plans Without Architect

**Files:**
- Create: `runtime/novel_author_plan_compiler.py`
- Modify: `runtime/novel_write_packet_builder.py`
- Modify: `runtime/novel_writer_context.py`
- Create: `tests/test_novel_author_plan_compiler.py`

**Interfaces:**
- Consumes: approved `AuthorChapterPlan`, project character store, prior plan identity.
- Produces:
  - `compile(plan: AuthorChapterPlan) -> ChapterPlan`
  - `render_writer_contract(plan: AuthorChapterPlan) -> str`
  - `compile_and_save(plan: AuthorChapterPlan, registry) -> ChapterPlan`

- [ ] **Step 1: Write failing no-invention tests**

```python
def test_compiler_preserves_scene_order_and_language():
    chapter = compiler.compile(author_plan)
    assert [beat.description for beat in chapter.scene_beats] == [
        "她返回空教室；变化：她决定交出钥匙",
        "他拒绝追问；变化：两人暂时合作",
    ]
    assert architect.calls == []


def test_writer_contract_contains_author_red_lines_verbatim():
    contract = compiler.render_writer_contract(author_plan)
    assert "不要让她道歉" in contract
    assert "可以自由设计钥匙交接时的动作" in contract
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_novel_author_plan_compiler.py -v`

Expected: FAIL because the compiler does not exist.

- [ ] **Step 3: Implement deterministic mapping**

Map each `AuthorScene` to exactly one `BeatDetail`; do not add or remove scenes. Derive only mechanical IDs and character budgets. Copy author text into `content_summary`, `plot_arrangement`, `character_appearance`, and `chapter_contract`; never call `NovelLLMFactory` or a role runtime.

Reject:

- non-approved plans;
- stale plan revisions;
- empty scenes;
- blocking unresolved questions;
- referenced characters not present in the project unless explicitly marked as a new character;
- a project/chapter mismatch.

- [ ] **Step 4: Load the approved contract into Writer packets**

`NovelWritePacketBuilder.build()` resolves the project root from project config, loads the approved plan mapped to the current chapter, and sets `packet.chapter_contract` to `render_writer_contract(plan)`. If no author plan exists, preserve legacy/autonomous behavior.

- [ ] **Step 5: Run compiler and Writer context tests**

Run:

```powershell
python -m pytest tests/test_novel_author_plan_compiler.py tests/test_novel_writer_context.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add -- runtime/novel_author_plan_compiler.py runtime/novel_write_packet_builder.py runtime/novel_writer_context.py tests/test_novel_author_plan_compiler.py
git commit -m "feat: compile author plans directly for writer"
```

### Task 4: Add Project-Bound Authoring Tools

**Files:**
- Modify: `runtime/novel_pi_tool_service.py`
- Modify: `runtime/novel_pi_bridge.py`
- Modify: `agent_harness/src/novel_tools.mjs`
- Modify: `agent_harness/src/novel_agent_host.mjs`
- Modify: `tests/test_novel_pi_tool_service.py`
- Modify: `tests/test_novel_pi_bridge.py`
- Modify: `agent_harness/test/novel_tools.test.mjs`
- Modify: `agent_harness/test/novel_agent_host.test.mjs`

**Interfaces:**
- Produces default interactive tools:
  - `project_status`
  - `read_chapter`
  - `audit_chapter`
  - `read_authoring_context`
  - `capture_author_material`
  - `save_author_plan`
  - `approve_author_plan`
  - `execute_author_plan`

`plan_chapter` and `write_chapter` are removed from the default interactive Pi allowlist; legacy/autonomous CLI paths retain them.

- [ ] **Step 1: Write failing Python permission tests**

```python
def test_default_tool_service_cannot_bypass_author_plan():
    assert "plan_chapter" not in NovelPiToolService.ALLOWED_TOOLS
    assert "write_chapter" not in NovelPiToolService.ALLOWED_TOOLS


def test_execute_author_plan_uses_compiler_then_streaming_engine():
    result = service.execute("execute_author_plan", approved_execute_args)
    assert compiler.saved_chapters == [3]
    assert engine.streamed_chapters == [3]
    assert architect.calls == []
```

- [ ] **Step 2: Run Python tests and verify failure**

Run: `python -m pytest tests/test_novel_pi_tool_service.py tests/test_novel_pi_bridge.py -v`

Expected: FAIL on the old tool allowlist.

- [ ] **Step 3: Implement Python routing and turn context**

`NovelPiBridge.run()` increments a turn counter, records the author message before sending a prompt, and supplies the current message/message ID/turn to `NovelPiToolService`. Tool failures return structured errors and never claim persistence.

- [ ] **Step 4: Write failing Node tool tests**

```javascript
assert.deepEqual(NOVEL_TOOL_NAMES, [
  "project_status", "read_chapter", "audit_chapter",
  "read_authoring_context", "capture_author_material",
  "save_author_plan", "approve_author_plan", "execute_author_plan",
]);
```

- [ ] **Step 5: Update TypeBox tool definitions**

Provide strict schemas with length bounds and `additionalProperties: false`. No authoring tool accepts `path`, `project_root`, or `project_id`; the bridge binds those values.

- [ ] **Step 6: Run Python and Node tests**

Run:

```powershell
python -m pytest tests/test_novel_pi_tool_service.py tests/test_novel_pi_bridge.py -q
npm test
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add -- runtime/novel_pi_tool_service.py runtime/novel_pi_bridge.py agent_harness/src agent_harness/test tests/test_novel_pi_tool_service.py tests/test_novel_pi_bridge.py
git commit -m "feat: expose safe authoring tools to pi"
```

### Task 5: Make the Default Pi Agent a Deep Writing Editor

**Files:**
- Rewrite: `agent_harness/resources/system-prompt.md`
- Create: `agent_harness/resources/skills/author-collaboration/SKILL.md`
- Modify: `agent_harness/test/novel_agent_host.test.mjs`

**Interfaces:**
- Consumes: safe authoring tools from Task 4.
- Produces: an automatically selected author-collaboration behavior with divergent and convergent editing loops.

- [ ] **Step 1: Add resource-loading assertions**

```javascript
assert.equal(skills.find((s) => s.name === "author-collaboration").disableModelInvocation, false);
assert.match(systemPrompt, /作品和目标读者/);
assert.match(systemPrompt, /不得直接创作整章正文/);
assert.match(systemPrompt, /自动使用.*author-collaboration/);
```

- [ ] **Step 2: Run Node tests and verify failure**

Run: `npm test`

Expected: FAIL because the current system prompt describes a restricted dispatcher and the Skill is absent.

- [ ] **Step 3: Write the editor system prompt**

The prompt must state:

- loyalty to the work and target reader, not author approval;
- no empty praise;
- distinguish confirmed/candidate/unresolved/prohibited;
- read existing project context before questions;
- automatically use the Skill for creative intent;
- persist material instead of relying on session memory;
- continue deep questioning until author explicitly converges;
- never directly write a full chapter;
- never call execution without distinct approval turns.

- [ ] **Step 4: Write the collaboration Skill**

The Skill defines:

```text
CAPTURE → DIVERGE → CHALLENGE → SYNTHESIZE → CONFIRM → HANDOFF
```

It asks high-value questions about motivation, scene change, cost, alternatives, information distribution, reader effect, character boundary, and cliché risk. Suggestions are labelled as candidates. It calls persistence tools as the conversation evolves.

- [ ] **Step 5: Run Node tests**

Run: `npm test`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add -- agent_harness/resources/system-prompt.md agent_harness/resources/skills/author-collaboration/SKILL.md agent_harness/test/novel_agent_host.test.mjs
git commit -m "feat: make pi a dedicated writing editor"
```

### Task 6: Remove Generic Writer Rules That Override the Author

**Files:**
- Modify: `runtime/novel_writer_adapter.py`
- Modify: `runtime/novel_prompt_assembler.py`
- Modify: `runtime/novel_writer_context.py`
- Modify: `tests/test_novel_writer_context.py`
- Create: `tests/test_novel_author_writer_rules.py`

**Interfaces:**
- Consumes: author plan marker and compiled chapter contract.
- Produces: author-led output rules containing only format/mechanical constraints plus plan-specific creative constraints.

- [ ] **Step 1: Write failing precedence tests**

```python
def test_author_mode_does_not_force_hook_dialogue_or_ratio(author_packet):
    _, prompt = adapter._build_chapter_prompt(author_packet)
    assert "结尾必须留悬念" not in prompt
    assert "必须有对话" not in prompt
    assert "60%以上" not in prompt
    assert "本章以无言分别收束" in prompt


def test_legacy_mode_preserves_existing_prompt_behavior(legacy_packet):
    _, prompt = adapter._build_chapter_prompt(legacy_packet)
    assert "只输出正文" in prompt
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_novel_author_writer_rules.py -v`

Expected: FAIL because generic creative rules currently override all plans.

- [ ] **Step 3: Separate mechanical from creative defaults**

In author mode retain:

-正文 only, no labels/JSON/meta;
- target length as a soft target;
- POV and factual continuity from the plan/context;
- do not write future scenes early.

Remove or subordinate universal hooks, mandatory dialogue, dialogue ratios, mandatory metaphor limits, and formulaic ending requirements. Preserve legacy defaults only when no approved author plan is attached.

- [ ] **Step 4: Run Writer tests**

Run:

```powershell
python -m pytest tests/test_novel_author_writer_rules.py tests/test_novel_writer_context.py tests/test_novel_pi_writer.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add -- runtime/novel_writer_adapter.py runtime/novel_prompt_assembler.py runtime/novel_writer_context.py tests/test_novel_author_writer_rules.py tests/test_novel_writer_context.py
git commit -m "refactor: let author plans control creative choices"
```

### Task 7: End-to-End Author-Led Flow

**Files:**
- Modify: `scripts/awp_tui.py`
- Modify: `runtime/novel_agent_runtime.py`
- Create: `tests/test_novel_author_editor_e2e.py`
- Modify: `agent_harness/README.md`
- Modify: `docs/novel_cli_guide.md`
- Create: `docs/handoffs/2026-07-26-author-editor-agent.md`

**Interfaces:**
- Consumes: default Pi editor, authoring storage, compiler, and execution tool.
- Produces: default TUI flow from raw author message through approved plan to Writer.

- [ ] **Step 1: Add an end-to-end policy test**

```python
def test_author_led_flow_records_then_confirms_then_writes(harness):
    harness.author("第三章我想让她回来，但不要道歉。")
    assert harness.journal_contains("不要道歉")
    assert not harness.engine.write_calls

    harness.agent_saves_pending_plan()
    harness.author("这个摘要准确，确认。")
    harness.agent_approves_plan()
    assert not harness.engine.write_calls

    harness.author("现在交给管线写第三章。")
    harness.agent_executes_plan()
    assert harness.architect.calls == []
    assert harness.engine.write_calls == [3]
```

- [ ] **Step 2: Run the test and verify failure**

Run: `python -m pytest tests/test_novel_author_editor_e2e.py -v`

Expected: FAIL until all integration wiring is present.

- [ ] **Step 3: Update TUI copy and runtime banner**

The welcome text identifies the default Agent as the专属写作编辑. Help text explains natural conversation, automatic local capture, and explicit confirmation; it does not advertise `/skill`.

- [ ] **Step 4: Run focused integration tests**

Run:

```powershell
python -m pytest tests/test_novel_author_editor_e2e.py tests/test_novel_agent_runtime.py tests/test_novel_pi_e2e.py -q
npm test
```

Expected: PASS.

- [ ] **Step 5: Run retained novel suite and compile checks**

Run retained Python tests in bounded groups, Node Harness tests, and `py_compile` for new modules. Record baseline skips or unrelated provider-dependent failures in the handoff.

- [ ] **Step 6: Update documentation**

Document local file layout, confirmation states, recovery after failure, default Pi editor behavior, and explicit legacy fallback.

- [ ] **Step 7: Commit**

```powershell
git add -- scripts/awp_tui.py runtime/novel_agent_runtime.py tests/test_novel_author_editor_e2e.py agent_harness/README.md docs/novel_cli_guide.md docs/handoffs/2026-07-26-author-editor-agent.md
git commit -m "feat: complete author-led writing workflow"
```
