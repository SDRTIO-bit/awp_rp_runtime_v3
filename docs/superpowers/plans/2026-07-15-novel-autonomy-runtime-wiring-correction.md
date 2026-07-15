# 小说自主 NPC 运行时接线修正 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development. Track every checkbox.

**Goal:** 将已存在但未调用的 Profile、NPC 规划器、Director 选择和账本提交接入两条真实小说写章路径。

**Architecture:** `NovelEngine` 产生只在本轮内存存在的 `AutonomousNpcTurn`：Profile → 活跃/过期议程 → 候选角色 → Pi 规划器 → Director 选择。该对象把内部 `NpcAgenda` 和 Writer 安全的 `VisibleConsequence` 分开；Writer 只接收后者，Curator 只在质量通过后接收前者。

**Tech Stack:** Python 3.10+、Pydantic v2、SQLite `LedgerItem`、Pi Role Host、pytest。

## Global Constraints

- 仅 Novel Mode；RP 不得 import/load `autonomous_profile`。
- `load_autonomous_profile()` 在任何 LLM 调用前运行；缺失、版本不兼容或非 `mode="novel"` 直接失败。
- 保持同步；不新增表；候选议程只存本轮内存。
- Writer packet、Writer Pi read tool、Writer prompt 禁止出现 `NpcAgenda`、`SelectedNpcAction`、私密目标、事实 ID、资源、成本、下一步、触发、风险、期限、thread key、选择理由。
- 仅 `quality_decision.is_accepted()` 后提交 `npc_action`、`npc_agenda` 和过期更新。

## 已核实断点

`NovelEngine` 没有引用 `NovelProfileCompiler`、`NpcAgendaService` 或 `NovelNpcAgendaAdapter`；`select_npc_actions()` 从未在 `generate_guidance()` 调用；默认 Profile 的各层均为空；完整 `DirectorGuidance` 进入 Writer packet，不能存放内部选择数据。

### Task 1: 实现有效的分层 Profile

**Files:** Modify `contracts/novel_profile.py`, `runtime/novel_profile_compiler.py`; Create `tests/test_novel_autonomy_runtime_wiring.py`.

**Produce:**

```python
def compile_for(role: str, profile: NovelWritingProfile, *, world_rules: list[str], history: str, scene: str, character_context: dict[str, object]) -> dict[str, object]: ...
```

- [x] **Step 1: 写失败测试。**

```python
def test_profile_is_nonempty_and_role_layered():
    p = default_autonomous_profile()
    assert p.narrative["language"] == "zh-CN"
    assert p.agent_contracts["npc_planner"]["response_format"] == "npc_agenda_json"
    planner = NovelProfileCompiler().compile_for("npc_planner", p, world_rules=["守恒"], history="已接受", scene="雨夜", character_context={})
    writer = NovelProfileCompiler().compile_for("writer", p, world_rules=["守恒"], history="已接受", scene="雨夜", character_context={})
    assert planner["world_rules"] == ["守恒"]
    assert "world_rules" not in writer
```

- [x] **Step 2: Run.** `pytest tests/test_novel_autonomy_runtime_wiring.py::test_profile_is_nonempty_and_role_layered -v`; expected FAIL.
- [x] **Step 3: Implement.** Default profile must include Chinese pure-text narrative rules, world/history/scene budgets, and contracts for architect/npc_planner/director/writer. Compiler gives Architect/Planner/Director narrative+world+history+scene+characters; Writer gets only narrative and writer contract.
- [x] **Step 4: Run.** `pytest tests/test_novel_autonomy_runtime_wiring.py tests/test_novel_autonomous_npc_contracts.py -v`; expected PASS.
- [x] **Step 5: Commit.** `git add contracts/novel_profile.py runtime/novel_profile_compiler.py tests/test_novel_autonomy_runtime_wiring.py && git commit -m "fix: compile autonomous novel profile layers"`

### Task 2: 在真实 Engine 中调用 Profile、规划器和 Director

**Files:** Modify `contracts/novel_npc_agenda.py`, `runtime/novel_engine.py`, `runtime/novel_architect_adapter.py`, `runtime/novel_director_adapter.py`; Test `tests/test_novel_autonomy_runtime_wiring.py`.

**Produce:**

```python
@dataclass(frozen=True)
class AutonomousNpcTurn:
    active_agendas: tuple[NpcAgenda, ...]
    expired_ledger_updates: tuple[LedgerItem, ...]
    selected_agendas: tuple[NpcAgenda, ...]
    visible_consequences: tuple[VisibleConsequence, ...]

def _prepare_autonomous_npc_turn(self, project, plan, ledger_items, characters, history, previous_ending, revision) -> AutonomousNpcTurn: ...
```

- [x] **Step 1: 写失败测试。**

```python
def test_real_write_path_calls_planner_and_director(monkeypatch, engine):
    calls = []
    monkeypatch.setattr(NovelNpcAgendaAdapter, "propose", lambda *a, **k: calls.append("planner") or (_agenda(),))
    monkeypatch.setattr(NovelDirectorAdapter, "select_npc_actions", lambda *a, **k: calls.append("director") or (_selected(),))
    engine.write_chapter(project_id="p1", chapter_index=1)
    assert calls == ["planner", "director"]
```

- [x] **Step 2: Run.** `pytest tests/test_novel_autonomy_runtime_wiring.py::test_real_write_path_calls_planner_and_director -v`; expected FAIL.
- [x] **Step 3: Implement.** Import all three runtime components in `NovelEngine`. Both `write_chapter()` and `write_chapter_stream()` call the shared method before Director. It loads Profile, obtains active/expired agendas, chooses <=5 appeared related characters, calls Pi planner, then calls Director. Architect gets active-agenda summaries before plan generation. Director JSON gains `selected_agenda_ids`; `generate_guidance()` validates IDs through `select_npc_actions()` and exposes only `visible_consequences`. Full agendas stay only in `AutonomousNpcTurn`.
- [x] **Step 4: Run.** `pytest tests/test_novel_autonomy_runtime_wiring.py tests/test_novel_pi_architect_director.py tests/test_novel_autonomous_npc_planner.py -v`; expected PASS for stream and non-stream.
- [x] **Step 5: Commit.** `git add contracts runtime/novel_engine.py runtime/novel_architect_adapter.py runtime/novel_director_adapter.py tests/test_novel_autonomy_runtime_wiring.py && git commit -m "fix: wire autonomous npc planning into novel engine"`

### Task 3: 建立 Writer 安全边界和接受后提交

**Files:** Modify `runtime/novel_writer_context.py`, `runtime/novel_write_packet_builder.py`, `runtime/novel_evolution_curator.py`, `runtime/novel_ledger_curator.py`, `runtime/novel_engine.py`; Test `tests/test_novel_autonomy_runtime_wiring.py`, `tests/test_novel_writer_context.py`.

- [x] **Step 1: 写失败测试。**

```python
def test_writer_packet_contains_only_consequence():
    text = json.dumps(_packet_after_real_selection().to_dict(), ensure_ascii=False)
    for field in ("private_goal", "known_fact_ids", "resources", "cost", "next_action", "trigger", "risk", "deadline", "thread_key", "reasoning"):
        assert field not in text
    assert "药材已被截走" in text

def test_rejected_chapter_writes_no_autonomy_items():
    _write_with_quality_verdict("reject")
    assert not _ledger("npc_action") and not _ledger("npc_agenda")
```

- [x] **Step 2: Run.** `pytest tests/test_novel_autonomy_runtime_wiring.py -v`; expected FAIL.
- [x] **Step 3: Implement.** Packet builder accepts `visible_consequences`, not internal actions. Construct a Writer-safe Guidance copy with only beat fields, anchors and visible consequences. Curator returns immediately on non-accepted quality. On accepted quality only: upsert expired updates, `npc_action` for every selected agenda, and continuing `npc_agenda`; never pass raw agenda into Writer/memory.
- [x] **Step 4: Run.** `pytest tests/test_novel_autonomy_runtime_wiring.py tests/test_novel_writer_context.py tests/test_novel_evolution_curator.py -v`; expected PASS.
- [x] **Step 5: Commit.** `git add runtime tests && git commit -m "fix: enforce writer-safe npc consequence boundary"`

### Task 4: 两章真实管线验收

**Files:** Modify `tests/test_novel_autonomous_npc_e2e.py`, `docs/handoffs/2026-07-15-novel-pipeline-completion-report.md`.

- [x] **Step 1: 写失败验收测试。**

```python
def test_two_chapter_chain_uses_profile_and_recovers_consequence(monkeypatch, engine):
    _configure_architect_planner_director_writer(monkeypatch)
    first = engine.write_chapter(project_id="p1", chapter_index=1)
    second = engine.write_chapter(project_id="p1", chapter_index=2)
    assert first.status == second.status == "accepted"
    assert _ledger_count("npc_action") >= 1
    assert "截走药材" in second.text and "私密目标" not in second.text
```

- [x] **Step 2: Run.** `pytest tests/test_novel_autonomous_npc_e2e.py::test_two_chapter_chain_uses_profile_and_recovers_consequence -v`; expected FAIL.
- [x] **Step 3: Implement fixture/report.** Assert exact order `architect → npc_planner → director → writer → quality → curator`. Mark real DeepSeek V4 Pro test optional only under `RUN_NOVEL_REAL_E2E=1`; lack of credentials is SKIPPED, never PASS.
- [x] **Step 4: Run.** `pytest tests/test_novel_autonomy_runtime_wiring.py tests/test_novel_autonomous_npc_e2e.py tests/test_novel_pi_*.py -v`; then `npm test` in `agent_harness`; expected PASS.
- [x] **Step 5: Commit.** `git add tests docs/handoffs && git commit -m "test: verify autonomous npc runtime wiring"`

## Self-Review

- This plan fixes actual unused-code references, not the external report's claims.
- Full agenda objects never enter serializable `DirectorGuidance` or `NovelWritePacket`.
- Both stream and non-stream entrypoints share the same preparation method; rejection commits nothing.
