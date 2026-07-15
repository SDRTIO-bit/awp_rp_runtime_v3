# 自主 NPC 与预设编译层 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 在 Novel Mode 加入受版本化 Profile 约束的自主 NPC 行动，并让 Writer 只能看到可见后果。

**Architecture:** `NovelProject.config["autonomous_profile"]` 保存 Novel-only Profile。规划器生成严格 `NpcAgenda`，Director 选择至多两项并转成 `VisibleConsequence`；候选只存在本轮内存，Curator 仅在质量接受后提交账本。

**Tech Stack:** Python 3.10+、Pydantic v2、现有 dataclass 合约、SQLite `LedgerItem`、Pi Host、React 18、pytest、Node。

## Global Constraints

- 仅 Novel Mode；RP 绝不加载 `autonomous_profile`。
- 小说引擎与适配器保持同步；不引入 `async`/`await`。
- 不建新表；只新增 `LedgerItem.section`：`npc_agenda`、`npc_action`。
- 拒绝、取消、超时、JSON 失败时，议程、行动、记忆与语义角色状态零写入。
- `NpcAgenda`/`VisibleConsequence` 经过 Pydantic 严格校验；不从自由散文猜字段。
- Writer 只消费 `VisibleConsequence`；原始议程、私密字段与 Director 选择理由禁止进入写作包、Pi read tool 或 prompt。
- 活跃议程上限 8；只可按相同 `(npc, thread_key)` 合并；不做 FIFO/LRU 自动淘汰。

## 文件映射

| 文件 | 变更 |
|---|---|
| `contracts/novel_profile.py`（新） | Profile 版本与 `mode="novel"` 校验、内置默认 Profile。 |
| `contracts/novel_npc_agenda.py`（新） | `NpcAgenda`、`SelectedNpcAction`、`VisibleConsequence`。 |
| `runtime/novel_profile_compiler.py`、`runtime/novel_npc_agenda_service.py`（新） | 分层上下文与确定性议程规则。 |
| `runtime/novel_npc_agenda_adapter.py`（新） | Pi `npc_planner` 严格 JSON 适配器。 |
| `runtime/novel_engine.py`、`runtime/novel_*_adapter.py`、`runtime/novel_evolution_curator.py` | 管线接入、Writer 隔离与接受后提交。 |
| `contracts/novel_*guidance.py`、`contracts/novel_write_packet.py`、`contracts/novel_pi_role_protocol.py` | 新合约字段与 Pi role 注册。 |
| `agent_harness/resources/roles/npc_planner/`、`agent_harness/src/novel_role_*.mjs` | 新角色资源和只读工具 allowlist。 |
| `runtime/management_api.py`、`scripts/novel_cli.py`、`web/src/...` | 非剧透计数和人工状态提升。 |

### Task 1: 定义 Profile、议程与可见后果合约

**Files:** Create `contracts/novel_profile.py`, `contracts/novel_npc_agenda.py`; Modify `contracts/novel_director_guidance.py`, `contracts/novel_write_packet.py`, `scripts/novel_cli.py`; Test `tests/test_novel_autonomous_npc_contracts.py`.

**Interfaces:** `load_autonomous_profile(config) -> NovelWritingProfile`; `NpcAgenda.model_validate_json`; `DirectorGuidance.visible_consequences`; `NovelWritePacket.visible_consequences`。

- [x] **Step 1: 写失败测试。**

```python
def test_profile_and_agenda_are_strict():
    with pytest.raises(NovelProfileError): load_autonomous_profile({})
    with pytest.raises(NovelProfileError): load_autonomous_profile({"autonomous_profile": {"mode": "rp"}})
    assert NpcAgenda.model_validate(_payload()).known_fact_ids == ("ledger-p1-7",)
    with pytest.raises(ValidationError): NpcAgenda.model_validate({**_payload(), "known_fact_ids": ["摘要"]})
```

- [x] **Step 2: 验证失败。** Run `pytest tests/test_novel_autonomous_npc_contracts.py -v`; expected: FAIL，模块不存在。
- [x] **Step 3: 实现。** `NovelWritingProfile` 使用 `ConfigDict(extra="forbid", frozen=True)`，字段为 `schema_id`、`schema_version`、`mode: Literal["novel"]`、`name`、`narrative`、`world`、`history`、`scene`、`agent_contracts`。`NpcAgenda` 使用 `agenda_id`、`thread_key`、`npc`、`private_goal`、`known_fact_ids: tuple[str, ...]`、资源/成本/行动/触发/风险/可见性/期限；`VisibleConsequence` 只允许 `agenda_id`、`beat_id`、`observable_event`、`observable_clue`、`affected_characters`。同步所有 `to_dict/from_dict`。`init`/`seed` 写默认 Profile；旧项目只能通过显式 `profile-init` 命令配置。
- [x] **Step 4: 验证通过。** Run `pytest tests/test_novel_autonomous_npc_contracts.py tests/test_novel_stores.py -v`; expected: PASS。
- [x] **Step 5: Commit.** `git add contracts scripts/novel_cli.py tests/test_novel_autonomous_npc_contracts.py && git commit -m "feat: add novel autonomy contracts and profile"`

### Task 2: 编译 Profile，筛选与隔离账本上下文

**Files:** Create `runtime/novel_profile_compiler.py`, `runtime/novel_npc_agenda_service.py`; Modify `runtime/novel_architect_adapter.py`, `runtime/novel_write_packet_builder.py`, `runtime/novel_writer_context.py`; Test `tests/test_novel_autonomous_npc_service.py`, `tests/test_novel_writer_context.py`.

**Interfaces:** `NpcAgendaService.active(...)`、`eligible_characters(...)`、`expire(...)`；`NovelProfileCompiler.compile_for(role, ...) -> dict`。

- [x] **Step 1: 写失败测试。**

```python
def test_candidates_are_related_and_bounded():
    assert [c.name for c in service.eligible_characters(_fifty_chars(), _plan(), 4)] == ["沈砚", "陆遥"]
def test_writer_packet_has_no_agenda_data():
    text = json.dumps(builder.build(..., ledger_items=[_agenda_item()]).to_dict(), ensure_ascii=False)
    assert "npc_agenda" not in text and "private_goal" not in text
```

- [x] **Step 2: 验证失败。** Run `pytest tests/test_novel_autonomous_npc_service.py tests/test_novel_writer_context.py -v`; expected: FAIL。
- [x] **Step 3: 实现。** 只选择已登场且文本/动机与章节有关角色，稳定排序后截断 5 名。无效 agenda JSON 仅产出诊断；超过 `deadline_chapter` 标 `stale`；满 8 条只推进/解决或同一 `(npc, thread_key)` 合并。Architect 获得活跃议程摘要。Writer 使用允许列表：过滤所有 `npc_agenda` 和 `npc_action`，只接收 `visible_consequences`。
- [x] **Step 4: 验证通过。** Run `pytest tests/test_novel_autonomous_npc_service.py tests/test_novel_writer_context.py tests/test_novel_pi_architect_director.py -v`; expected: PASS。
- [x] **Step 5: Commit.** `git add runtime tests && git commit -m "feat: compile novel profile and isolate agenda context"`

### Task 3: 增加 Pi 规划角色与 Director 选择

**Files:** Create `runtime/novel_npc_agenda_adapter.py`, `agent_harness/resources/roles/npc_planner/system-prompt.md`, `agent_harness/resources/roles/npc_planner/skills/core/SKILL.md`; Modify `contracts/novel_pi_role_protocol.py`, `runtime/novel_llm_factory.py`, `agent_harness/src/novel_role_tools.mjs`, `agent_harness/src/novel_role_resources.mjs`, `runtime/novel_director_adapter.py`; Test `tests/test_novel_autonomous_npc_planner.py`, `agent_harness/test/novel_role_{tools,resources}.test.mjs`.

**Interfaces:** `NovelNpcAgendaAdapter.propose(...) -> tuple[NpcAgenda, ...]`; Director 产出至多两个 `SelectedNpcAction` 与 `VisibleConsequence`。

- [x] **Step 1: 写失败测试。**

```python
def test_planner_is_a_dedicated_pi_role(monkeypatch, reg):
    result = _adapter_with_recording_pi(monkeypatch, reg).propose("p1", _plan(), _candidates(), (), _profile())
    assert result[0].agenda_id == "agenda-1"
    assert _recorded_task().role == "npc_planner"
```

- [x] **Step 2: 验证失败。** Run `pytest tests/test_novel_autonomous_npc_planner.py -v`; then `npm test` in `agent_harness`; expected: FAIL。
- [x] **Step 3: 实现。** 注册 `npc_planner` 到 `NOVEL_PI_ROLES` 和工厂配置（`deepseek-v4-pro`）。只给它 `read_project_contract`、`read_chapter_plan`、`read_ledger`、`read_characters`。它必须返回 `{"agendas":[...]}`；逐项 `NpcAgenda.model_validate`，丢弃无效项。Director 仅返回候选 ID 对应的可见字段；拒绝未知 ID、超过两项、资源不够或冲突的选择。
- [x] **Step 4: 验证通过。** Run `pytest tests/test_novel_autonomous_npc_planner.py tests/test_novel_pi_architect_director.py -v`; Run `npm test` in `agent_harness`; expected: PASS。
- [x] **Step 5: Commit.** `git add runtime contracts agent_harness tests && git commit -m "feat: add pi npc agenda planner"`

### Task 4: 接入写章管线，接受后提交

**Files:** Modify `runtime/novel_engine.py`, `runtime/novel_evolution_curator.py`, `runtime/novel_ledger_curator.py`, `runtime/novel_continuity_checker.py`; Test `tests/test_novel_autonomous_npc_engine.py`, `tests/test_novel_evolution_curator.py`.

**Interfaces:** `_prepare_autonomous_npc_context(...) -> AutonomousNpcTurn`; `NovelEvolutionCurator.curate(..., selected_npc_actions=())`。

- [x] **Step 1: 写失败测试。**

```python
def test_rejection_has_zero_autonomy_side_effects(monkeypatch, reg):
    _configure_rejected_autonomous_turn(monkeypatch, reg)
    NovelEngine(reg).write_chapter(project_id="p1", chapter_index=1)
    assert not reg.novel_ledger_store.list_by_project("p1", "npc_action")
    assert not reg.novel_ledger_store.list_by_project("p1", "npc_agenda")
```

- [x] **Step 2: 验证失败。** Run `pytest tests/test_novel_autonomous_npc_engine.py -v`; expected: FAIL。
- [x] **Step 3: 实现。** `write_chapter` 与 `write_chapter_stream` 共用：Profile 校验 → 过期议程 → Architect → 确定性候选 → Planner → Director → Writer → Quality。只将 `VisibleConsequence` 放入 `NovelWritePacket`。仅 `is_accepted()` 后把所选动作转成 `npc_action`，未完结动作转成 `npc_agenda`；Curator 白名单认识新 section。`NpcAction` 是自动事实来源；不得自动改写 `NovelCharacter.current_state` 的受伤、关系、知识等语义字段。Quality 检查后果存在、资源/动机/事实连续、无私密泄露、无主角抢功。
- [x] **Step 4: 验证通过。** Run `pytest tests/test_novel_autonomous_npc_engine.py tests/test_novel_evolution_curator.py tests/test_novel_engine.py tests/test_novel_pi_quality_roles.py -v`; expected: PASS。
- [x] **Step 5: Commit.** `git add runtime tests && git commit -m "feat: commit accepted autonomous npc actions"`

### Task 5: 安全可观测性、人工状态提升与验收

**Files:** Modify `runtime/management_api.py`, `scripts/novel_cli.py`, `web/src/api/client.ts`, `web/src/pages/NovelDetail.tsx`, `docs/handoffs/2026-07-15-novel-pipeline-completion-report.md`; Create `tests/test_novel_autonomous_npc_api.py`, `tests/test_novel_autonomous_npc_e2e.py`; Modify `tests/test_novel_agent_runtime.py`.

**Interfaces:** `GET /novels/{id}/autonomy-summary -> {active_count, stale_count, chapter_action_counts}`；`POST /novels/{id}/characters/{character_id}/state-promotions` body `{source_item_id, patch}`；`novel_cli.py promote-state`。

- [x] **Step 1: 写失败的隐私、提升和两章测试。**

```python
def test_summary_does_not_leak_private_plan(client, project_id):
    data = client.get(f"/novels/{project_id}/autonomy-summary").json()["data"]
    assert data["active_count"] == 1
    assert "private_goal" not in json.dumps(data, ensure_ascii=False)
def test_two_chapters_have_action_but_writer_never_sees_secret(monkeypatch, reg):
    drafts, packets = _run_two_chapter_fixture(monkeypatch, reg)
    assert all(d.status == "accepted" for d in drafts)
    assert all("private_goal" not in json.dumps(p.to_dict(), ensure_ascii=False) for p in packets)
```

- [x] **Step 2: 验证失败。** Run `pytest tests/test_novel_autonomous_npc_api.py tests/test_novel_autonomous_npc_e2e.py -v`; expected: FAIL。
- [x] **Step 3: 实现。** 普通 ledger API/CLI/页面隐藏 `npc_agenda.content`，摘要只给计数。提升端点验证同项目、来源是已接受 `npc_action`、patch 为 object；用 `dataclasses.replace` 写 `current_state`，附 `promoted_from_item_id`/时间，拒绝身份、动机和 `known_fact_ids` 键。UI 只显示计数与作者可展开的已接受 action；不请求 agenda 原文。真实模型测试仅在 `RUN_NOVEL_REAL_E2E=1` 有凭据时执行；否则跳过，普通两章 fake-E2E 是发布门槛。补充报告命令和人工核查项。
- [x] **Step 4: 完整验证。** Run `pytest tests/test_novel_autonomous_npc_*.py tests/test_novel_pi_*.py -v`; Run `npm test` in `agent_harness`; Run `npm run build` in `web`; expected: PASS。Optional: `$env:RUN_NOVEL_REAL_E2E='1'; pytest tests/test_novel_autonomous_npc_e2e.py -m real_model -v`; expected: PASS 或无凭据 SKIPPED。
- [x] **Step 5: Commit.** `git add runtime scripts web tests docs/handoffs && git commit -m "feat: review autonomous novel npc state"`

## Self-Review

- 覆盖设计的 Profile/mode 隔离、事实 ID、容量/期限、Pi 规划、可见后果、Writer 允许列表、接受后提交、手动状态提升、非剧透 UI、两章验收和 RP 回归。
- 不创建表、不引入多 worker、不扩展 RP；每项先测失败再最小实现并独立提交。
- 自主数据链固定为 `NpcAgenda → SelectedNpcAction → VisibleConsequence`；Writer 只消费末端，Curator 只接收中间项。
