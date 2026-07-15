# Novel Autonomy Accepted-Commit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make autonomous NPC agendas generic, durable across chapters, and committed only after a chapter receives an `accept` quality verdict.

**Architecture:** Engine collects agenda mutations in memory. Curator persists them alongside selected action facts only after strict acceptance. The fallback Profile has no story data; project material comes solely from project inputs.

**Tech Stack:** Python 3.10+, Pydantic v2, SQLite, pytest, embedded Pi role runtime.

## Global Constraints

- Novel Mode only; do not alter RP data or code paths.
- Existing malformed/foreign Profiles fail before an LLM call; missing Profiles use the generic default.
- Director and Writer receive `VisibleConsequence`, never private agenda data or reasoning.
- Only verdict `value == "accept"` may write `npc_agenda`, `npc_action`, semantic character state, or memory.
- The novel pipeline remains synchronous and Python is the sole state writer.

---

### Task 1: Make the compatibility Profile story-neutral

**Files:**
- Modify: `contracts/novel_profile.py:34-89`
- Modify: `tests/test_novel_autonomous_npc_service.py`

**Interfaces:** `default_autonomous_profile() -> NovelWritingProfile` remains schema-valid with `mode="novel"`, but must contain generic Chinese narrative/agent rules and no fixed people, genre, location, chapter, event, or scene.

- [x] **Step 1: Write the failing test**

```python
def test_compatibility_profile_contains_no_fixed_story_material():
    serialized = default_autonomous_profile().model_dump_json()
    for text in ("刑侦", "匿名威胁", "警局", "第三章", "雨夜", "废弃仓库"):
        assert text not in serialized
```

- [x] **Step 2: Verify RED**

Run: `pytest tests/test_novel_autonomous_npc_service.py::test_compatibility_profile_contains_no_fixed_story_material -q`

Expected: FAIL because the current default includes hard-coded mystery content.

- [x] **Step 3: Implement the minimal generic Profile**

```python
narrative = {"language": "zh-CN", "tone": "服从项目既有风格与人物视角", "style": "展示角色选择及其可见后果", "objective": "推进本章计划并保持人物自主性"}
world = {"rules": ["以项目账本、人物和章节计划为唯一具体世界来源", "NPC 动机独立于主角意志"], "budget": "世界观约束不超过 5 条"}
history = {"facts": [], "constraints": "仅使用已接受的项目历史与账本事实"}
scene = {"budget": "场景约束不超过 5 条", "must_include": [], "constraints": ["仅执行章节计划定义的场景与节拍"]}
```

- [x] **Step 4: Verify GREEN**

Run: `pytest tests/test_novel_autonomous_npc_service.py tests/test_novel_autonomy_runtime_wiring.py::test_profile_is_nonempty_and_role_layered -q`

Expected: PASS.

- [x] **Step 5: Commit**

Run:

```bash
git add contracts/novel_profile.py tests/test_novel_autonomous_npc_service.py
git commit -m "fix: make default novel profile story neutral"
```

### Task 2: Stage agenda lifecycle records in memory

**Files:**
- Modify: `runtime/novel_npc_agenda_service.py:13-36`
- Modify: `runtime/novel_engine.py:50-60,536-607`
- Modify: `tests/test_novel_autonomous_npc_service.py`

**Interfaces:** Add `NpcAgendaService.to_ledger_item(agenda, chapter_plan, status="active") -> LedgerItem`. Add `AutonomousNpcTurn.agenda_updates: tuple[LedgerItem, ...]`. It contains stale existing records and new/advanced planner proposals but Engine must not write it.

- [x] **Step 1: Write the failing conversion test**

```python
def test_agenda_to_ledger_item_round_trips_stable_agenda_id():
    item = NpcAgendaService().to_ledger_item(_agenda("agenda-7"), _plan(4))
    restored = NpcAgenda.model_validate(json.loads(item.content))
    assert item.section == "npc_agenda"
    assert item.status == "active"
    assert restored.agenda_id == "agenda-7"
```

- [x] **Step 2: Verify RED**

Run: `pytest tests/test_novel_autonomous_npc_service.py::test_agenda_to_ledger_item_round_trips_stable_agenda_id -q`

Expected: FAIL with `AttributeError` because the converter is absent.

- [x] **Step 3: Implement staged conversion**

```python
def to_ledger_item(self, agenda, chapter_plan, *, status="active"):
    return LedgerItem(
        item_id=f"novel-ledger-{chapter_plan.project_id}-npc_agenda-{agenda.agenda_id}",
        project_id=chapter_plan.project_id, section="npc_agenda", entity=agenda.npc,
        content=agenda.model_dump_json(), status=status,
        source_chapter=chapter_plan.chapter_index, created_at=_now(), updated_at=_now(),
    )
```

Remove the pre-Quality `novel_ledger_store.upsert` loop. Return stale updates plus active items for each proposal, de-duplicated by `item_id` with a proposal winning.

- [x] **Step 4: Verify GREEN**

Run: `pytest tests/test_novel_autonomous_npc_service.py -q`

Expected: PASS.

- [x] **Step 5: Commit**

Run:

```bash
git add runtime/novel_npc_agenda_service.py runtime/novel_engine.py tests/test_novel_autonomous_npc_service.py
git commit -m "feat: stage novel agenda lifecycle updates"
```

### Task 3: Strictly gate agenda/action persistence

**Files:**
- Modify: `runtime/novel_engine.py:400-430,1085-1100`
- Modify: `runtime/novel_evolution_curator.py:58-118`
- Modify: `tests/test_novel_autonomous_npc_engine.py`

**Interfaces:** Extend `_update_ledger(..., selected_npc_actions=(), agenda_updates=())` and `NovelEvolutionCurator.curate(..., agenda_updates=())`. Curator writes neither batch member unless Quality strictly accepts.

- [x] **Step 1: Write failing lifecycle tests**

```python
def test_rejected_chapter_does_not_persist_expired_agenda(monkeypatch, reg, engine, fake_novel_role_runtime):
    _setup_real_path_project(reg)
    reg.novel_ledger_store.upsert(expired_agenda_item(project_id="p1"))
    monkeypatch.setattr(engine._quality_pipeline, "run_chapter", lambda *a, **k: (_rejected_quality_decision(), a[0]))
    engine.write_chapter(project_id="p1", chapter_index=1)
    assert reg.novel_ledger_store.list_by_project("p1", "npc_agenda")[0].status == "active"

def test_accepted_chapter_persists_planned_agenda_and_selected_action(monkeypatch, reg, engine, fake_novel_role_runtime):
    _setup_real_path_project(reg)
    monkeypatch.setattr(NovelNpcAgendaAdapter, "propose", lambda *a, **k: (_agenda(),))
    monkeypatch.setattr(NovelDirectorAdapter, "select_npc_actions", lambda *a, **k: (_selected(),))
    engine.write_chapter(project_id="p1", chapter_index=1)
    assert len(reg.novel_ledger_store.list_by_project("p1", "npc_agenda")) == 1
    assert len(reg.novel_ledger_store.list_by_project("p1", NpcAction.LEDGER_SECTION)) == 1
```

- [x] **Step 2: Verify RED**

Run: `pytest tests/test_novel_autonomous_npc_engine.py::test_rejected_chapter_does_not_persist_expired_agenda tests/test_novel_autonomous_npc_engine.py::test_accepted_chapter_persists_planned_agenda_and_selected_action -q`

Expected: FAIL because stale state is pre-written and planner proposals are not committed.

- [x] **Step 3: Pass only accepted batch data to Curator**

```python
accepted = quality_decision is not None and quality_decision.verdict.value == "accept"
effective_actions = selected_npc_actions if accepted else ()
effective_agendas = agenda_updates if accepted else ()
ledger_updates = [*effective_agendas, *npc_action_items]
```

In both `write_chapter` and `write_chapter_stream`, pass `npc_turn.agenda_updates` to `_update_ledger` only when `chapter_quality_accepted` is true. Do not change existing non-autonomy ledger policy.

- [x] **Step 4: Verify GREEN**

Run: `pytest tests/test_novel_autonomous_npc_engine.py tests/test_novel_autonomy_runtime_wiring.py -q`

Expected: PASS.

- [x] **Step 5: Commit**

Run:

```bash
git add runtime/novel_engine.py runtime/novel_evolution_curator.py tests/test_novel_autonomous_npc_engine.py
git commit -m "fix: commit npc agendas only after quality acceptance"
```

### Task 4: Verify cross-chapter continuity and regression boundaries

**Files:**
- Modify: `tests/test_novel_autonomy_runtime_wiring.py`
- Modify: `docs/handoffs/2026-07-15-novel-pipeline-completion-report.md`

**Interfaces:** An agenda accepted in chapter one must be fed to the chapter-two Planner with unchanged `agenda_id` and `thread_key`.

- [x] **Step 1: Write failing two-chapter test**

```python
def test_second_chapter_reads_the_first_accepted_agenda(monkeypatch, reg, engine, fake_novel_role_runtime):
    _setup_two_chapter_project(reg)
    seen = []
    monkeypatch.setattr(NovelNpcAgendaAdapter, "propose", lambda _self, _pid, _plan, _chars, active, _ctx: seen.append(active) or (_agenda(),))
    monkeypatch.setattr(NovelDirectorAdapter, "select_npc_actions", lambda *a, **k: (_selected(),))
    engine.write_chapter(project_id="p1", chapter_index=1)
    engine.write_chapter(project_id="p1", chapter_index=2)
    assert any(a.agenda_id == "agenda-1" and a.thread_key == "observe" for a in seen[1])
```

- [x] **Step 2: Verify RED**

Run: `pytest tests/test_novel_autonomy_runtime_wiring.py::test_second_chapter_reads_the_first_accepted_agenda -q`

Expected: FAIL before Task 3 persists accepted agendas.

- [x] **Step 3: Add only the two-chapter fixture support**

Create chapter two using the same named candidate NPC. Do not add another persistence mechanism or weaken Writer filtering.

- [x] **Step 4: Run focused and Node regression suites**

Run: `pytest tests/test_novel_autonomous_npc_contracts.py tests/test_novel_autonomous_npc_service.py tests/test_novel_autonomous_npc_planner.py tests/test_novel_autonomous_npc_engine.py tests/test_novel_autonomy_runtime_wiring.py tests/test_novel_autonomous_npc_e2e.py -q`

Expected: PASS; documented real-provider tests may be SKIPPED only without their environment flag.

Run in `agent_harness`: `npm test`

Expected: `17 passed, 0 failed`.

- [x] **Step 5: Update report and commit**

Append the acceptance semantics, two-chapter result, and environment skips to the handoff report.

Run:

```bash
git add tests/test_novel_autonomy_runtime_wiring.py docs/handoffs/2026-07-15-novel-pipeline-completion-report.md
git commit -m "test: verify durable accepted npc agendas"
```
