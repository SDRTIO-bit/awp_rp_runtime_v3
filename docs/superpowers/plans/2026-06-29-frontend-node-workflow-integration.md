# 前端功能对接节点/工作流（双轨执行引擎）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让管理面板前端能真正"聊天"（玩家输入→新回合）+ "管理"（导入/删除卡、新建/删除会话），生成类动作走 ComfyUI 工作流队列或 Python 直调（双轨可切），并把 Reviser 修订重试补进 PersistentTurnEngine。

**Architecture:** 在 `management_api.py` 加执行调度层，按动作重量分轨：生成类（玩家回合/首回合/AI续写）受 `AWP_EXECUTION_MODE` 开关影响，hybrid 轨读 `workflows/api/` 真 API 格式工作流填参后提交 `/prompt` 队列并轮询取结果，python 轨直接 `node.execute()`；管理类（导入/删除卡、新建/删除会话、列表）恒走 Python 直调。工作流选择器扫描 `workflows/api/` 让用户切换执行用的工作流。

**Tech Stack:** Python（aiohttp/ComfyUI server）、React 18 + Vite + Antd、SQLite 存储层、ComfyUI prompt 队列 API。

**Spec:** `docs/superpowers/specs/2026-06-29-frontend-node-workflow-integration-design.md`

---

## 关键调研结论（实现前必读）

1. **Reviser 已有 runtime**：`runtime/reviser_runtime.py:26` `ReviserRuntime(writer_adapter, max_revisions=1)`，方法 `revise(RevisionRequest, WriterInputBundle)`，复用 writer_adapter 生成修订稿。引擎顶部未 import，需新增。
2. **引擎质量门位置**：`runtime/persistent_turn_engine.py:800` 调 `_quality_check`，`:820` 处 `if not quality_decision.allows_side_effects():` 直接拒绝返回。Reviser 补丁要改这个分支。
3. **真 API 格式工作流**：用户已导出 `03_send_turn.api.json`（顶层 `{"1": {"inputs":{...}, "class_type":"AWPV2PersistentContinuationTurn"}}`）。填参 = 改节点1的 `inputs.session_id`/`player_input`。`workflows/api/` 现有5个文件是**图形格式**（误导命名），需移走。
4. **`APIWorkflowLoader` 已存在**：`testing/api_workflow_loader.py`，`load(name)`/`list_workflows()`/`validate()`，指向 `workflows/api/`，期望 `{name}.api.json`。
5. **`ComfyAPIClient` 已存在**：`testing/comfy_api_client.py`，`queue_prompt(workflow)`/`wait_for_completion(prompt_id, timeout)`。
6. **registry 缺 `card_definition_store`**：`SessionRuntimeStoreRegistry`（`runtime/session_runtime_registry.py:34-46`）没有这个属性，但 `management_api.py:65,104,180` 在用它，被 try/except 静默吞掉。计划要补上。
7. **存储层缺删除方法**：所有 store 都没有 `delete`/`delete_by_session`，外键未设 ON DELETE CASCADE，需手写级联删除 SQL。
8. **bootstrap 节点**：`AWPV2PersistentBootstrap.execute(source_path, session_id, greeting_id, ...)`，内部走 `CardSessionBootstrapPipeline`。
9. **Writer 预设**：`presets/writer_preset_loader.py` `WriterPresetLoader` 有 `list_presets()`/`load(name)`/`get_preset_path(name)`。

---

## 文件结构

### 新建
- `workflows/api/send_turn.api.json` — 玩家回合真 API 格式工作流（用户提供，重命名）
- `workflows/api/first_turn.api.json` — 首回合真 API 格式（模板推导）
- `workflows/api/continue_world.api.json` — AI续写真 API 格式（模板推导）
- `runtime/execution_dispatcher.py` — 执行调度层（双轨分支、工作流填参、入队轮询）
- `runtime/session_deletion_service.py` — 会话/卡级联删除服务
- `tests/test_reviser_in_engine.py` — Reviser 补丁测试
- `tests/test_execution_dispatcher.py` — 调度层测试
- `tests/test_session_deletion_service.py` — 删除服务测试
- `tests/test_management_api_new_endpoints.py` — 新端点测试
- `tests/test_workflow_selector.py` — 工作流清单端点测试
- `tests/test_history_loading.py` — 历史加载验收测试
- `web/src/components/WorkflowSelector.tsx` — 工作流选择器组件
- `web/src/components/NewSessionModal.tsx` — 新建会话弹窗
- `web/src/components/PresetViewer.tsx` — Writer 预设查看组件

### 修改
- `runtime/persistent_turn_engine.py` — 补 Reviser 修订重试
- `runtime/session_runtime_registry.py` — 加 `card_definition_store` 属性
- `runtime/management_api.py` — 新增端点 + 接调度层
- `storage/sqlite/card_definition_store.py` — 加 `delete`/`list_by_card`
- `storage/sqlite/session_stores.py` — 各 store 加 `delete`/`delete_by_session`/`list_by_card`
- `storage/sqlite/turn_record_store.py` — 加 `delete_by_session`
- `web/src/api/client.ts` — 新增 API 函数
- `web/src/pages/SessionChat.tsx` — 输入框+发送+选择器+预设
- `web/src/pages/Cards.tsx` — 导入/删除/详情
- `web/src/pages/Sessions.tsx` — 新建/删除
- `web/src/main.tsx` — 路由（如需）

---

## Task 1: 给 registry 补 card_definition_store 属性

**Files:**
- Modify: `runtime/session_runtime_registry.py:34-46`
- Test: `tests/test_session_runtime_registry.py`（新建或复用）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_session_runtime_registry.py
from awp_rp_runtime_v2.runtime.session_runtime_registry import SessionRuntimeStoreRegistry

def test_registry_exposes_card_definition_store(tmp_path):
    db_path = str(tmp_path / "test.db")
    registry = SessionRuntimeStoreRegistry(db_path)
    assert registry.card_definition_store is not None
    # list_all 应可调用且不抛
    assert isinstance(registry.card_definition_store.list_all(), list)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_session_runtime_registry.py::test_registry_exposes_card_definition_store -v`
Expected: FAIL with `AttributeError: card_definition_store`

- [ ] **Step 3: 加属性**

在 `runtime/session_runtime_registry.py` 顶部 import 加：
```python
from ..storage.sqlite.card_definition_store import SqliteCardDefinitionStore
```
在 `__init__` 的 `self.rag_memory_store = ...` 之后加：
```python
        self.card_definition_store = SqliteCardDefinitionStore(db)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_session_runtime_registry.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add runtime/session_runtime_registry.py tests/test_session_runtime_registry.py
git commit -m "fix: 给 registry 补 card_definition_store 属性"
```

---

## Task 2: 存储层加删除方法

**Files:**
- Modify: `storage/sqlite/card_definition_store.py`（加 `delete`, `list_by_card`）
- Modify: `storage/sqlite/session_stores.py`（各 store 加 `delete`/`delete_by_session`）
- Modify: `storage/sqlite/turn_record_store.py`（加 `delete_by_session`）
- Test: `tests/test_store_deletion_methods.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_store_deletion_methods.py
from awp_rp_runtime_v2.runtime.session_runtime_registry import SessionRuntimeStoreRegistry

def _registry(tmp_path):
    return SessionRuntimeStoreRegistry(str(tmp_path / "t.db"))

def test_card_definition_delete(tmp_path):
    from awp_rp_runtime_v2.tests.factories import make_card_definition
    reg = _registry(tmp_path)
    cd = make_card_definition(logical_card_id="card-1")
    reg.card_definition_store.save(cd)
    assert reg.card_definition_store.get_latest("card-1") is not None
    reg.card_definition_store.delete("card-1")
    assert reg.card_definition_store.get_latest("card-1") is None

def test_binding_delete_and_list_by_card(tmp_path):
    from awp_rp_runtime_v2.tests.factories import make_binding
    reg = _registry(tmp_path)
    b = make_binding(session_id="s1", logical_card_id="card-1")
    reg.card_session_binding_store.save(b)
    assert len(reg.card_session_binding_store.list_by_card("card-1")) == 1
    reg.card_session_binding_store.delete("s1")
    assert reg.card_session_binding_store.load("s1") is None
    assert len(reg.card_session_binding_store.list_by_card("card-1")) == 0

def test_turn_record_delete_by_session(tmp_path):
    from awp_rp_runtime_v2.tests.factories import make_turn_record
    reg = _registry(tmp_path)
    t = make_turn_record(session_id="s1")
    reg.turn_record_store.save(t)
    assert len(reg.turn_record_store.list_by_session("s1")) == 1
    reg.turn_record_store.delete_by_session("s1")
    assert len(reg.turn_record_store.list_by_session("s1")) == 0
```

> 注：`make_card_definition`/`make_binding`/`make_turn_record` 若不存在，先在 `tests/factories.py` 新建（参考现有 test_fixtures）。先确认它们是否已存在：`grep -rn "def make_card_definition\|def make_binding" tests/`。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_store_deletion_methods.py -v`
Expected: FAIL with `AttributeError: delete` 等

- [ ] **Step 3: 实现 card_definition_store.delete / list_by_card**

在 `storage/sqlite/card_definition_store.py` 加：
```python
    def delete(self, logical_card_id: str) -> None:
        self.db.execute(
            "DELETE FROM card_definitions WHERE logical_card_id = ?",
            (logical_card_id,),
        )
        self.db.commit()

    def list_by_card(self, logical_card_id: str) -> list:
        # 复用现有 list_all 逻辑过滤
        return [c for c in self.list_all() if c.logical_card_id == logical_card_id]
```
> 实现前先读该文件确认表名（应为 `card_definitions`）和 `self.db` 用法。

- [ ] **Step 4: 实现 binding store delete / list_by_card**

在 `storage/sqlite/session_stores.py` 的 `SqliteCardSessionBindingStore` 加：
```python
    def delete(self, session_id: str) -> None:
        self.db.execute(
            "DELETE FROM card_session_bindings WHERE session_id = ?",
            (session_id,),
        )
        self.db.commit()

    def list_by_card(self, logical_card_id: str) -> list:
        rows = self.db.fetchall(
            "SELECT * FROM card_session_bindings WHERE logical_card_id = ?",
            (logical_card_id,),
        )
        return [self._row_to_binding(r) for r in rows]
```
> 实现前读该文件确认 `_row_to_binding` 方法名和表名。

- [ ] **Step 5: 实现 turn_record_store.delete_by_session**

在 `storage/sqlite/turn_record_store.py` 加：
```python
    def delete_by_session(self, session_id: str) -> None:
        self.db.execute(
            "DELETE FROM turn_records WHERE session_id = ?",
            (session_id,),
        )
        self.db.commit()
```

- [ ] **Step 6: 实现其余 store 的 delete_by_session**

对 `SqliteOpeningRecordStore`、`SqliteWorldbookBindingStore`、`SqliteBootstrapReceiptStore` 各加 `delete_by_session(session_id)`，模式同上（`DELETE FROM <表> WHERE session_id = ?`）。读文件确认各表名。

- [ ] **Step 7: 跑测试确认通过**

Run: `python -m pytest tests/test_store_deletion_methods.py -v`
Expected: PASS

- [ ] **Step 8: 跑全量回归**

Run: `python -m pytest tests/ -x -q`
Expected: 无新增失败

- [ ] **Step 9: 提交**

```bash
git add storage/sqlite/ tests/test_store_deletion_methods.py tests/factories.py
git commit -m "feat: 存储层加删除方法（card/binding/turn/opening/worldbook/receipt）"
```

---

## Task 3: 会话/卡级联删除服务

**Files:**
- Create: `runtime/session_deletion_service.py`
- Test: `tests/test_session_deletion_service.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_session_deletion_service.py
from awp_rp_runtime_v2.runtime.session_runtime_registry import SessionRuntimeStoreRegistry
from awp_rp_runtime_v2.runtime.session_deletion_service import SessionDeletionService
from awp_rp_runtime_v2.tests.factories import make_binding, make_turn_record

def test_delete_session_cascades_all(tmp_path):
    reg = SessionRuntimeStoreRegistry(str(tmp_path / "t.db"))
    reg.card_session_binding_store.save(make_binding(session_id="s1", logical_card_id="c1"))
    reg.turn_record_store.save(make_turn_record(session_id="s1"))
    svc = SessionDeletionService(reg)
    svc.delete_session("s1")
    assert reg.card_session_binding_store.load("s1") is None
    assert reg.turn_record_store.list_by_session("s1") == []
    # opening/worldbook/receipt 也应删
    assert reg.opening_record_store.get_by_session("s1") is None

def test_delete_card_cascades_sessions(tmp_path):
    reg = SessionRuntimeStoreRegistry(str(tmp_path / "t.db"))
    reg.card_session_binding_store.save(make_binding(session_id="s1", logical_card_id="c1"))
    reg.card_session_binding_store.save(make_binding(session_id="s2", logical_card_id="c1"))
    reg.turn_record_store.save(make_turn_record(session_id="s1"))
    svc = SessionDeletionService(reg)
    svc.delete_card("c1")
    assert reg.card_definition_store.get_latest("c1") is None
    assert reg.card_session_binding_store.list_by_card("c1") == []
    assert reg.turn_record_store.list_by_session("s1") == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_session_deletion_service.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现服务**

```python
# runtime/session_deletion_service.py
"""会话/卡级联删除服务。外键未设 ON DELETE CASCADE，需应用层级联。"""
from __future__ import annotations
from .session_runtime_registry import SessionRuntimeStoreRegistry


class SessionDeletionService:
    def __init__(self, registry: SessionRuntimeStoreRegistry) -> None:
        self._reg = registry

    def delete_session(self, session_id: str) -> None:
        r = self._reg
        # 先删依赖 session_id 的表
        r.turn_record_store.delete_by_session(session_id)
        r.opening_record_store.delete_by_session(session_id)
        r.worldbook_binding_store.delete_by_session(session_id)
        r.bootstrap_receipt_store.delete_by_session(session_id)
        # 再删 binding
        r.card_session_binding_store.delete(session_id)

    def delete_card(self, logical_card_id: str) -> None:
        r = self._reg
        # 删该卡所有会话（级联）
        for b in r.card_session_binding_store.list_by_card(logical_card_id):
            self.delete_session(b.session_id)
        # 删卡定义
        r.card_definition_store.delete(logical_card_id)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_session_deletion_service.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add runtime/session_deletion_service.py tests/test_session_deletion_service.py
git commit -m "feat: 会话/卡级联删除服务"
```

---

## Task 4: Reviser 修订重试补进 PersistentTurnEngine

这是最敏感的改动（851 测试依赖）。TDD 小步。

**Files:**
- Modify: `runtime/persistent_turn_engine.py`（import + `_quality_check` 失败分支改重试）
- Test: `tests/test_reviser_in_engine.py`

- [ ] **Step 1: 读关键代码段**

读 `runtime/persistent_turn_engine.py:790-860`（quality 检查与拒绝分支）和 `runtime/reviser_runtime.py` 全文、`contracts/revision_request.py`、`contracts/revision_result.py`，确认 `RevisionRequest` 构造参数和 writer_adapter 如何获取（引擎里 Writer 用的 adapter 变量名）。

- [ ] **Step 2: 写失败测试——质量不通过→修订→通过**

```python
# tests/test_reviser_in_engine.py
"""引擎 Reviser 修订重试：质量不通过时修订一次，修订后通过则接受。"""
import pytest
from awp_rp_runtime_v2.runtime.persistent_turn_engine import PersistentTurnEngine
# 复用现有测试的引擎构造辅助（grep 现有 test 找 build_engine / make_snapshot）

def test_engine_revises_when_quality_fails_then_passes(monkeypatch):
    # 构造引擎 + snapshot，使首次 writer 输出触发 SceneGate/LengthGate 失败，
    # Reviser 修订稿通过。断言最终 outcome=success 且 writer_output 为修订稿。
    ...
```

> 实现前先 grep 现有引擎测试（`grep -rln "PersistentTurnEngine" tests/`）找现成的引擎构造 fixture 和"制造质量失败"的手段（如短文本触发 LengthGate），复用而非新造。

- [ ] **Step 3: 跑测试确认失败**

Run: `python -m pytest tests/test_reviser_in_engine.py -v`
Expected: FAIL（当前不通过直接拒绝，无修订）

- [ ] **Step 4: 加 import**

`runtime/persistent_turn_engine.py` 顶部 import 区加：
```python
from .reviser_runtime import ReviserRuntime
from ..contracts.revision_request import RevisionRequest
```

- [ ] **Step 5: 改质量失败分支为修订重试**

在 `:820` 的 `if not quality_decision.allows_side_effects():` 分支，替换"直接拒绝返回"为：
```python
        if not quality_decision.allows_side_effects():
            # Reviser 修订重试（最大 1 次）
            candidate_text = self._try_revise(
                candidate_text, quality_decision, snapshot, trace_id, bundle, writer_adapter,
            )
            # 修订后再检查一次
            quality_decision = self._quality_check(candidate_text, snapshot, trace_id)
            diag.quality_verdict = quality_decision.verdict.value
            if not quality_decision.allows_side_effects():
                # 仍不通过才拒绝
                diag.steps_failed.append("quality_gate")
                diag.outcome = "quality_rejected"
                diag.failure_message = f"Quality gate rejected after revise: {quality_decision.blocking_reasons}"
                receipt = FirstTurnReceipt(...)  # 保持原拒绝 receipt 结构
                self._persist_trace(trace, diag)
                return (receipt.to_dict(), {}, diag.to_dict(),
                        card_state.to_dict(), {}, snapshot.to_dict())
```

- [ ] **Step 6: 实现 _try_revise 辅助方法**

在引擎类里加：
```python
    def _try_revise(
        self, candidate_text, quality_decision, snapshot, trace_id, bundle, writer_adapter,
    ) -> str:
        """质量不通过时调 Reviser 修订一次，返回修订稿（失败则返回原稿）。"""
        try:
            reviser = ReviserRuntime(writer_adapter, max_revisions=1)
            request = RevisionRequest(
                original_text=candidate_text,
                issues=list(quality_decision.blocking_reasons),
                current_revision=0,
                max_revisions=1,
                writer_draft_id=trace_id,
            )
            result = reviser.revise(request, bundle)
            if result.success or result.revised_text:
                return result.revised_text or candidate_text
        except Exception:
            pass
        return candidate_text
```
> 实现前确认 `RevisionRequest` 真实构造参数（读 `contracts/revision_request.py`）、`bundle` 和 `writer_adapter` 在 execute 主流程里的变量名。

- [ ] **Step 7: 跑新测试确认通过**

Run: `python -m pytest tests/test_reviser_in_engine.py -v`
Expected: PASS

- [ ] **Step 8: 写第二条测试——修订后仍不通过则拒绝**

```python
def test_engine_rejects_when_revise_still_fails(monkeypatch):
    # 首次失败，Reviser 修订稿仍触发失败。断言 outcome=quality_rejected。
    ...
```

- [ ] **Step 9: 跑两条测试**

Run: `python -m pytest tests/test_reviser_in_engine.py -v`
Expected: PASS

- [ ] **Step 10: 跑全量回归（关键）**

Run: `python -m pytest tests/ -x -q`
Expected: 无新增失败。若有，说明 _try_revise 影响了原有质量拒绝路径，需调整。

- [ ] **Step 11: 提交**

```bash
git add runtime/persistent_turn_engine.py tests/test_reviser_in_engine.py
git commit -m "feat: PersistentTurnEngine 补 Reviser 修订重试（最大1次）"
```

---

## Task 5: 整理 workflows/api 目录（移图形格式，放真 API 格式）

**Files:**
- Move: `workflows/api/*.api.json`（5个图形格式）→ `workflows/awp_v2_playable_workflows/`
- Create: `workflows/api/send_turn.api.json`（用户提供，从 `C:\Users\zhao\Downloads\03_send_turn.api.json`）
- Create: `workflows/api/first_turn.api.json`、`workflows/api/continue_world.api.json`（模板推导）

- [ ] **Step 1: 移走现有图形格式文件**

```bash
# 注意文件名冲突：awp_v2_playable_workflows 下已有 01_bootstrap_session.api.json 等
# workflows/api 的文件名（bootstrap_only 等）与 playable 不同名，可直接移
git mv workflows/api/bootstrap_only.api.json workflows/awp_v2_playable_workflows/bootstrap_only.graph.json
git mv workflows/api/continuation_turn_only.api.json workflows/awp_v2_playable_workflows/continuation_turn_only.graph.json
git mv workflows/api/full_architecture_turn.api.json workflows/awp_v2_playable_workflows/full_architecture_turn.graph.json
git mv workflows/api/persistent_play_session.api.json workflows/awp_v2_playable_workflows/persistent_play_session.graph.json
git mv workflows/api/sub_agents_only.api.json workflows/awp_v2_playable_workflows/sub_agents_only.graph.json
```
> 移到图形目录后改 `.graph.json` 后缀，与真 API 格式区分。

- [ ] **Step 2: 放入用户提供的真 API 格式 send_turn**

```bash
cp "C:/Users/zhao/Downloads/03_send_turn.api.json" workflows/api/send_turn.api.json
```

- [ ] **Step 3: 生成 first_turn.api.json（模板推导）**

基于 send_turn.api.json，把节点1的 `class_type` 改为 `AWPV2PersistentFirstTurn`，保留 `session_id`/`player_input`/profile 参数。用 Write 工具创建 `workflows/api/first_turn.api.json`，内容 = send_turn 副本但 class_type 换掉、turn_kind 相关保持。

- [ ] **Step 4: 生成 continue_world.api.json（模板推导）**

基于 send_turn.api.json，节点1 `class_type` 改为 `AWPV2ContinueTurnP1`，去掉 `player_input`（续写无玩家输入）。用 Write 创建。

- [ ] **Step 5: 验证三个文件都是真 API 格式**

```bash
python -c "import json; d=json.load(open('workflows/api/send_turn.api.json',encoding='utf-8')); assert 'class_type' in d['1']; print('send_turn OK')"
python -c "import json; d=json.load(open('workflows/api/first_turn.api.json',encoding='utf-8')); assert 'class_type' in d['1']; print('first_turn OK')"
python -c "import json; d=json.load(open('workflows/api/continue_world.api.json',encoding='utf-8')); assert 'class_type' in d['1']; print('continue_world OK')"
```
Expected: 三个都 OK

- [ ] **Step 6: 验证 APIWorkflowLoader 能加载**

```bash
python -c "from testing.api_workflow_loader import APIWorkflowLoader; l=APIWorkflowLoader(); print(l.list_workflows()); l.load('send_turn'); l.load('first_turn'); l.load('continue_world'); print('all loaded')"
```
Expected: 列表含 send_turn/first_turn/continue_world，全部加载成功

- [ ] **Step 7: 提交**

```bash
git add workflows/api/ workflows/awp_v2_playable_workflows/
git commit -m "chore: workflows/api 专放真API格式，图形格式移至 playable 目录"
```

---

## Task 6: 执行调度层 execution_dispatcher

**Files:**
- Create: `runtime/execution_dispatcher.py`
- Test: `tests/test_execution_dispatcher.py`

- [ ] **Step 1: 写失败测试——python 轨直调**

```python
# tests/test_execution_dispatcher.py
from awp_rp_runtime_v2.runtime.execution_dispatcher import ExecutionDispatcher

def test_python_mode_calls_node_directly(tmp_path, monkeypatch):
    # 造一个已 bootstrap 的会话，dispatcher 以 mode=python 调玩家回合
    # 断言：调用了 AWPV2PersistentContinuationTurn.execute，新回合落库
    ...
```

> 实现前 grep 现有测试找"造会话+首回合"的 fixture 复用。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_execution_dispatcher.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现调度层**

```python
# runtime/execution_dispatcher.py
"""双轨执行调度层。生成类动作：hybrid 走工作流队列，python 直调节点。"""
from __future__ import annotations
import os
from typing import Any
from .runtime_store_factory import RuntimeStoreFactory

DEFAULT_WORKFLOWS = {
    "turn": "send_turn",
    "first_turn": "first_turn",
    "continue": "continue_world",
}


def _global_mode() -> str:
    return os.environ.get("AWP_EXECUTION_MODE", "hybrid").lower()


class ExecutionDispatcher:
    def __init__(self, registry=None) -> None:
        self._registry = registry

    def _reg(self):
        if self._registry is None:
            self._registry = RuntimeStoreFactory.from_env().registry
        return self._registry

    def execute_turn(self, session_id: str, player_input: str,
                     mode: str = "", workflow: str = "") -> dict:
        """玩家回合。mode 优先参数，其次全局。"""
        m = (mode or _global_mode()).lower()
        if m == "python":
            return self._python_turn(session_id, player_input)
        return self._hybrid("turn", session_id, player_input, workflow)

    def execute_first_turn(self, session_id: str, player_input: str,
                           mode: str = "", workflow: str = "") -> dict:
        m = (mode or _global_mode()).lower()
        if m == "python":
            return self._python_first_turn(session_id, player_input)
        return self._hybrid("first_turn", session_id, player_input, workflow)

    def execute_continue(self, session_id: str,
                         mode: str = "", workflow: str = "") -> dict:
        m = (mode or _global_mode()).lower()
        if m == "python":
            return self._python_continue(session_id)
        return self._hybrid("continue", session_id, "", workflow)

    # ── python 轨 ──
    def _python_turn(self, session_id, player_input) -> dict:
        from ..nodes.persistent_continuation_turn_node import AWPV2PersistentContinuationTurn
        result = AWPV2PersistentContinuationTurn().execute(
            session_id=session_id, player_input=player_input,
        )
        return self._extract_turn_result(result)

    def _python_first_turn(self, session_id, player_input) -> dict:
        from ..nodes.persistent_first_turn_node import AWPV2PersistentFirstTurn
        result = AWPV2PersistentFirstTurn().execute(
            session_id=session_id, player_input=player_input,
        )
        return self._extract_turn_result(result)

    def _python_continue(self, session_id) -> dict:
        from ..nodes.continue_turn_execution_node import AWPV2ContinueTurn
        result = AWPV2ContinueTurn().execute(session_id=session_id)
        return self._extract_turn_result(result)

    # ── hybrid 轨 ──
    def _hybrid(self, action: str, session_id: str, player_input: str,
                workflow: str) -> dict:
        wf_name = workflow or DEFAULT_WORKFLOWS[action]
        graph = self._load_workflow(wf_name)
        self._fill_inputs(graph, session_id, player_input)
        return self._submit_and_wait(graph)

    def _load_workflow(self, name: str) -> dict:
        import sys, pathlib
        # testing/api_workflow_loader 在 testing 包下
        root = pathlib.Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(root))
        from testing.api_workflow_loader import APIWorkflowLoader
        return APIWorkflowLoader().load(name)

    def _fill_inputs(self, graph: dict, session_id: str, player_input: str) -> None:
        # 找持有 session_id 输入的节点，填参
        for node_id, node_def in graph.items():
            inputs = node_def.get("inputs", {})
            if "session_id" in inputs:
                inputs["session_id"] = session_id
            if "player_input" in inputs and player_input:
                inputs["player_input"] = player_input

    def _submit_and_wait(self, graph: dict) -> dict:
        import sys, pathlib
        root = pathlib.Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from testing.comfy_api_client import ComfyAPIClient
        client = ComfyAPIClient()
        if not client.is_available():
            raise RuntimeError("ComfyUI server not available for hybrid mode")
        res = client.queue_prompt(graph)
        prompt_id = res["prompt_id"]
        history = client.wait_for_completion(prompt_id, timeout_seconds=180)
        return self._extract_turn_result_from_history(history)

    # ── 结果提取 ──
    def _extract_turn_result(self, result: tuple) -> dict:
        # 节点 execute 返回 (receipt, ctx, diag, card_state, turn_record, snapshot)
        turn_record = result[4] if len(result) > 4 else {}
        diag = result[2] if len(result) > 2 else {}
        return {
            "success": (diag.get("outcome") == "success") if isinstance(diag, dict) else False,
            "turn_id": turn_record.get("turn_id", "") if isinstance(turn_record, dict) else "",
            "turn_index": turn_record.get("turn_index", 0) if isinstance(turn_record, dict) else 0,
            "writer_output": turn_record.get("writer_output", "") if isinstance(turn_record, dict) else "",
            "diagnostics": diag if isinstance(diag, dict) else {},
        }

    def _extract_turn_result_from_history(self, history: dict) -> dict:
        # 从 ComfyUI history outputs 取 AWPV2AcceptedTextOutput 的文本
        # history 结构: {prompt_id: {"outputs": {node_id: {...}}}}
        outputs = {}
        for v in history.values():
            if isinstance(v, dict) and "outputs" in v:
                outputs = v["outputs"]
                break
        text = ""
        for node_out in outputs.values():
            if isinstance(node_out, dict) and "text" in node_out:
                text = node_out["text"]
                break
        return {"success": True, "turn_id": "", "turn_index": 0,
                "writer_output": text, "diagnostics": {}}
```

> 实现前确认：(a) `AWPV2PersistentContinuationTurn` 在 `nodes/persistent_continuation_turn_node.py` 的类名与 import 路径；(b) `ComfyAPIClient.wait_for_completion` 返回结构；(c) `AWPV2AcceptedTextOutput` 节点输出在 history 里的字段名（可能不是 `text`，需查节点定义）。

- [ ] **Step 4: 跑 python 轨测试确认通过**

Run: `python -m pytest tests/test_execution_dispatcher.py::test_python_mode_calls_node_directly -v`
Expected: PASS

- [ ] **Step 5: 写测试——mode 覆盖逻辑**

```python
def test_request_mode_overrides_global(monkeypatch):
    monkeypatch.setenv("AWP_EXECUTION_MODE", "python")
    d = ExecutionDispatcher(registry=...)
    # 传 mode=hybrid 应走 hybrid 分支（mock _hybrid 验证被调）
    ...
```

- [ ] **Step 6: 写测试——工作流选择**

```python
def test_workflow_param_selects_workflow(monkeypatch):
    # 传 workflow="full_architecture_turn"（如有），断言 _load_workflow 收到该名
    ...
```

- [ ] **Step 7: 跑全部调度层测试**

Run: `python -m pytest tests/test_execution_dispatcher.py -v`
Expected: PASS

- [ ] **Step 8: 提交**

```bash
git add runtime/execution_dispatcher.py tests/test_execution_dispatcher.py
git commit -m "feat: 双轨执行调度层（hybrid工作流/python直调 + 开关覆盖）"
```

---

## Task 7: 新增管理 API 端点

**Files:**
- Modify: `runtime/management_api.py`
- Test: `tests/test_management_api_new_endpoints.py`

> 端点测试用 aiohttp test 或直接调路由函数。先 grep 现有 management_api 测试看模式（`grep -rln "management_api" tests/`）。

- [ ] **Step 1: 写失败测试——玩家发消息端点**

```python
# tests/test_management_api_new_endpoints.py
def test_post_turn_creates_new_turn(tmp_path, monkeypatch):
    # 造会话，POST /sessions/{id}/turn {player_input}，
    # 断言返回 success 且 turn_record_store 多一条
    ...
```

- [ ] **Step 2: 跑确认失败**

Run: `python -m pytest tests/test_management_api_new_endpoints.py -v`
Expected: FAIL（端点不存在）

- [ ] **Step 3: 实现玩家回合端点**

在 `runtime/management_api.py` 的 continue_session 路由后加：
```python
    @server.PromptServer.instance.routes.post("/awp/api/v1/sessions/{session_id}/turn")
    async def post_turn(request):
        """玩家发消息——触发玩家回合。"""
        session_id = request.match_info["session_id"]
        body = await request.json()
        player_input = body.get("player_input", "")
        mode = request.query.get("mode", "")
        workflow = request.query.get("workflow", "")
        if not player_input:
            return _json({"error": "player_input required"}, 400)
        from .execution_dispatcher import ExecutionDispatcher
        try:
            dispatcher = ExecutionDispatcher()
            result = dispatcher.execute_turn(session_id, player_input, mode=mode, workflow=workflow)
            return _json(result)
        except Exception as e:
            return _json({"error": f"Turn failed: {str(e)[:200]}"}, 500)
```

- [ ] **Step 4: 实现首回合端点**

```python
    @server.PromptServer.instance.routes.post("/awp/api/v1/sessions/{session_id}/first-turn")
    async def post_first_turn(request):
        session_id = request.match_info["session_id"]
        body = await request.json()
        player_input = body.get("player_input", "")
        mode = request.query.get("mode", "")
        workflow = request.query.get("workflow", "")
        from .execution_dispatcher import ExecutionDispatcher
        try:
            dispatcher = ExecutionDispatcher()
            result = dispatcher.execute_first_turn(session_id, player_input, mode=mode, workflow=workflow)
            return _json(result)
        except Exception as e:
            return _json({"error": f"First turn failed: {str(e)[:200]}"}, 500)
```

- [ ] **Step 5: 改造 continue 端点走调度层**

把现有 `continue_session` 路由体替换为：
```python
    @server.PromptServer.instance.routes.post("/awp/api/v1/sessions/{session_id}/continue")
    async def continue_session(request):
        session_id = request.match_info["session_id"]
        mode = request.query.get("mode", "")
        workflow = request.query.get("workflow", "")
        from .execution_dispatcher import ExecutionDispatcher
        try:
            dispatcher = ExecutionDispatcher()
            result = dispatcher.execute_continue(session_id, mode=mode, workflow=workflow)
            return _json(result)
        except Exception as e:
            return _json({"error": f"Continue failed: {str(e)[:200]}"}, 500)
```

- [ ] **Step 6: 实现导入卡端点**

```python
    @server.PromptServer.instance.routes.post("/awp/api/v1/cards/import")
    async def import_card(request):
        body = await request.json()
        source_path = body.get("source_path", "")
        if not source_path:
            return _json({"error": "source_path required"}, 400)
        from ..nodes.persistent_bootstrap_node import AWPV2PersistentBootstrap
        try:
            node = AWPV2PersistentBootstrap()
            binding, opening, worldbook, receipt, diag = node.execute(
                source_path=source_path,
                session_id=body.get("session_id", f"imp-{_id('sess','')}"),
                greeting_id=body.get("greeting_id", "g0"),
            )
            return _json({"success": diag.get("outcome") == "success",
                          "session_id": binding.get("session_id", ""),
                          "card_id": binding.get("logical_card_id", ""),
                          "diagnostics": diag})
        except Exception as e:
            return _json({"error": f"Import failed: {str(e)[:200]}"}, 500)
```
> 实现前确认 `AWPV2PersistentBootstrap` 的 import 路径和返回 tuple 顺序（Task 调研已确认：binding/opening/worldbook/receipt/diag）。

- [ ] **Step 7: 实现 greetings 列表端点**

```python
    @server.PromptServer.instance.routes.get("/awp/api/v1/cards/{card_id}/greetings")
    async def list_greetings(request):
        card_id = request.match_info["card_id"]
        factory = _factory()
        card = factory.registry.card_definition_store.get_latest(card_id)
        if not card:
            return _json({"error": "Card not found"}, 404)
        greetings = []
        for g in (card.greetings or []):
            greetings.append({
                "greeting_id": g.get("greeting_id", ""),
                "label": g.get("label", ""),
                "is_default": g.get("is_default", False),
                "preview": (g.get("safe_display_content", "") or "")[:120],
            })
        return _json(greetings)
```

- [ ] **Step 8: 实现新建会话端点**

```python
    @server.PromptServer.instance.routes.post("/awp/api/v1/sessions")
    async def create_session(request):
        body = await request.json()
        card_id = body.get("card_id", "")
        greeting_id = body.get("greeting_id", "")
        if not card_id:
            return _json({"error": "card_id required"}, 400)
        factory = _factory()
        card = factory.registry.card_definition_store.get_latest(card_id)
        if not card:
            return _json({"error": "Card not found"}, 404)
        # 用 bootstrap pipeline 从已有卡建会话（不重新导入）
        from ..runtime.card_session_bootstrap_pipeline import CardSessionBootstrapPipeline
        # 构造 request 调 pipeline.bootstrap(...) —— 实现前读 pipeline 签名确认参数
        ...
        return _json({"session_id": binding.session_id, "card_id": card_id, "greeting_id": greeting_id})
```
> 实现前读 `runtime/card_session_bootstrap_pipeline.py` 确认如何从已有 CardDefinition（不重新读文件）建会话。可能需要先构造 `CardSessionBootstrapRequest`。

- [ ] **Step 9: 实现删除卡/删除会话端点**

```python
    @server.PromptServer.instance.routes.delete("/awp/api/v1/cards/{card_id}")
    async def delete_card(request):
        card_id = request.match_info["card_id"]
        from .session_deletion_service import SessionDeletionService
        try:
            factory = _factory()
            SessionDeletionService(factory.registry).delete_card(card_id)
            return _json({"success": True})
        except Exception as e:
            return _json({"error": str(e)[:200]}, 500)

    @server.PromptServer.instance.routes.delete("/awp/api/v1/sessions/{session_id}")
    async def delete_session(request):
        session_id = request.match_info["session_id"]
        from .session_deletion_service import SessionDeletionService
        try:
            factory = _factory()
            SessionDeletionService(factory.registry).delete_session(session_id)
            return _json({"success": True})
        except Exception as e:
            return _json({"error": str(e)[:200]}, 500)
```

- [ ] **Step 10: 跑端点测试**

Run: `python -m pytest tests/test_management_api_new_endpoints.py -v`
Expected: PASS

- [ ] **Step 11: 跑全量回归**

Run: `python -m pytest tests/ -x -q`
Expected: 无新增失败

- [ ] **Step 12: 提交**

```bash
git add runtime/management_api.py tests/test_management_api_new_endpoints.py
git commit -m "feat: 管理API新端点（turn/first-turn/import/delete/greetings/create-session）"
```

---

## Task 8: 工作流清单 + Writer 预设端点

**Files:**
- Modify: `runtime/management_api.py`
- Test: `tests/test_workflow_selector.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_workflow_selector.py
def test_list_workflows_returns_api_format_only():
    # GET /awp/api/v1/workflows 返回 send_turn/first_turn/continue_world
    ...

def test_list_writer_presets():
    # GET /awp/api/v1/presets/writer 返回 presets/writer 下的 .txt 名
    ...

def test_get_writer_preset_content():
    # GET /awp/api/v1/presets/writer/{name} 返回 content + path
    ...
```

- [ ] **Step 2: 跑确认失败**

Run: `python -m pytest tests/test_workflow_selector.py -v`
Expected: FAIL

- [ ] **Step 3: 实现工作流清单端点**

```python
    @server.PromptServer.instance.routes.get("/awp/api/v1/workflows")
    async def list_workflows(request):
        import sys, pathlib
        root = pathlib.Path(__file__).resolve().parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from testing.api_workflow_loader import APIWorkflowLoader
        loader = APIWorkflowLoader()
        names = loader.list_workflows()
        result = []
        for n in names:
            wf = loader.load(n)
            node_count = len(wf)
            class_types = sorted({v.get("class_type", "") for v in wf.values()})
            result.append({"name": n, "node_count": node_count, "class_types": class_types})
        return _json(result)
```

- [ ] **Step 4: 实现 Writer 预设端点**

```python
    @server.PromptServer.instance.routes.get("/awp/api/v1/presets/writer")
    async def list_writer_presets(request):
        from ..presets.writer_preset_loader import WriterPresetLoader
        loader = WriterPresetLoader()
        return _json(loader.list_presets())

    @server.PromptServer.instance.routes.get("/awp/api/v1/presets/writer/{name}")
    async def get_writer_preset(request):
        from ..presets.writer_preset_loader import WriterPresetLoader
        name = request.match_info["name"]
        loader = WriterPresetLoader()
        try:
            content = loader.load(name)
            path = loader.get_preset_path(name)
            return _json({"name": name, "content": content, "path": path})
        except Exception as e:
            return _json({"error": str(e)[:200]}, 404)
```

- [ ] **Step 5: 跑测试**

Run: `python -m pytest tests/test_workflow_selector.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add runtime/management_api.py tests/test_workflow_selector.py
git commit -m "feat: 工作流清单 + Writer预设 端点"
```

---

## Task 9: 历史加载验收（显式验收点）

**Files:**
- Test: `tests/test_history_loading.py`

- [ ] **Step 1: 写验收测试**

```python
# tests/test_history_loading.py
"""显式验收：打开已有会话必须加载全部历史，不得空白。"""
from awp_rp_runtime_v2.runtime.session_runtime_registry import SessionRuntimeStoreRegistry

def test_reopen_session_shows_full_history(tmp_path):
    reg = SessionRuntimeStoreRegistry(str(tmp_path / "t.db"))
    # 造会话 + 开场白 + 3 个回合
    from awp_rp_runtime_v2.tests.factories import make_binding, make_turn_record, make_opening
    reg.card_session_binding_store.save(make_binding(session_id="s1"))
    reg.opening_record_store.save(make_opening(session_id="s1", content="开场白"))
    for i in range(3):
        reg.turn_record_store.save(make_turn_record(session_id="s1", turn_index=i, writer_output=f"回合{i}"))

    # 模拟前端打开会话：调 listTurns 等价查询
    turns = reg.turn_record_store.list_by_session("s1")
    opening = reg.opening_record_store.get_by_session("s1")

    # 断言全部历史可见
    assert opening is not None
    assert opening.safe_display_content == "开场白"
    assert len(turns) == 3
    assert [t.turn_index for t in turns] == [0, 1, 2]
    assert all(t.writer_output for t in turns)
```

- [ ] **Step 2: 跑测试**

Run: `python -m pytest tests/test_history_loading.py -v`
Expected: PASS（现有存储层已支持，此为验收锁）

- [ ] **Step 3: 提交**

```bash
git add tests/test_history_loading.py
git commit -m "test: 历史加载显式验收（打开会话必须见全部历史）"
```

---

## Task 10: 前端 API client 扩展

**Files:**
- Modify: `web/src/api/client.ts`

- [ ] **Step 1: 加新 API 函数**

在 `web/src/api/client.ts` 末尾加：
```typescript
export async function sendTurn(sessionId: string, playerInput: string, opts?: { mode?: string; workflow?: string }): Promise<{ success: boolean; turn_id: string; turn_index: number; writer_output: string }> {
  const params = new URLSearchParams();
  if (opts?.mode) params.set("mode", opts.mode);
  if (opts?.workflow) params.set("workflow", opts.workflow);
  const res = await fetch(`${BASE}/awp/api/v1/sessions/${encodeURIComponent(sessionId)}/turn?${params}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_input: playerInput }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.data?.error || `HTTP ${res.status}`);
  return body.data;
}

export async function firstTurn(sessionId: string, playerInput: string, opts?: { mode?: string; workflow?: string }): Promise<any> {
  const params = new URLSearchParams();
  if (opts?.mode) params.set("mode", opts.mode);
  if (opts?.workflow) params.set("workflow", opts.workflow);
  const res = await fetch(`${BASE}/awp/api/v1/sessions/${encodeURIComponent(sessionId)}/first-turn?${params}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ player_input: playerInput }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.data?.error || `HTTP ${res.status}`);
  return body.data;
}

export async function continueSessionV2(sessionId: string, opts?: { mode?: string; workflow?: string }): Promise<any> {
  const params = new URLSearchParams();
  if (opts?.mode) params.set("mode", opts.mode);
  if (opts?.workflow) params.set("workflow", opts.workflow);
  const res = await fetch(`${BASE}/awp/api/v1/sessions/${encodeURIComponent(sessionId)}/continue?${params}`, { method: "POST" });
  const body = await res.json();
  if (!res.ok) throw new Error(body.data?.error || `HTTP ${res.status}`);
  return body.data;
}

export async function importCard(sourcePath: string, greetingId?: string): Promise<any> {
  const res = await fetch(`${BASE}/awp/api/v1/cards/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_path: sourcePath, greeting_id: greetingId || "g0" }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.data?.error || `HTTP ${res.status}`);
  return body.data;
}

export async function deleteCard(cardId: string): Promise<void> {
  const res = await fetch(`${BASE}/awp/api/v1/cards/${encodeURIComponent(cardId)}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${BASE}/awp/api/v1/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function listGreetings(cardId: string): Promise<Array<{ greeting_id: string; label: string; is_default: boolean; preview: string }>> {
  return get(`/cards/${encodeURIComponent(cardId)}/greetings`);
}

export async function createSession(cardId: string, greetingId: string): Promise<{ session_id: string }> {
  const res = await fetch(`${BASE}/awp/api/v1/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ card_id: cardId, greeting_id: greetingId }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.data?.error || `HTTP ${res.status}`);
  return body.data;
}

export interface WorkflowInfo { name: string; node_count: number; class_types: string[] }
export async function listWorkflows(): Promise<WorkflowInfo[]> {
  return get<WorkflowInfo[]>("/workflows");
}

export interface WriterPresetInfo { name: string; content: string; path: string }
export async function listWriterPresets(): Promise<string[]> {
  return get<string[]>("/presets/writer");
}
export async function getWriterPreset(name: string): Promise<WriterPresetInfo> {
  return get<WriterPresetInfo>(`/presets/writer/${encodeURIComponent(name)}`);
}
```

- [ ] **Step 2: 类型检查**

Run: `cd web && npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 3: 提交**

```bash
git add web/src/api/client.ts
git commit -m "feat: 前端 API client 扩展（turn/import/delete/greetings/workflows/presets）"
```

---

## Task 11: 前端工作流选择器组件

**Files:**
- Create: `web/src/components/WorkflowSelector.tsx`

- [ ] **Step 1: 实现组件**

```tsx
// web/src/components/WorkflowSelector.tsx
import { useEffect, useState } from "react";
import { Collapse, Select, Radio, Space, Typography } from "antd";
import { listWorkflows, WorkflowInfo } from "../api/client";

const { Text } = Typography;

interface Props {
  action: "turn" | "first_turn" | "continue";
  mode: string;
  workflow: string;
  onModeChange: (m: string) => void;
  onWorkflowChange: (w: string) => void;
}

export default function WorkflowSelector({ action, mode, workflow, onModeChange, onWorkflowChange }: Props) {
  const [workflows, setWorkflows] = useState<WorkflowInfo[]>([]);

  useEffect(() => {
    listWorkflows().then(setWorkflows).catch(() => {});
  }, []);

  return (
    <Collapse ghost defaultActiveKey={[]}>
      <Collapse.Panel header="执行模式与工作流（高级）" key="1">
        <Space direction="vertical" style={{ width: "100%" }}>
          <Radio.Group value={mode} onChange={(e) => onModeChange(e.target.value)}>
            <Radio.Button value="hybrid">工作流（hybrid）</Radio.Button>
            <Radio.Button value="python">Python 直调</Radio.Button>
          </Radio.Group>
          <div>
            <Text type="secondary">工作流：</Text>
            <Select
              style={{ width: "100%", marginTop: 4 }}
              value={workflow || undefined}
              placeholder="默认"
              onChange={onWorkflowChange}
              allowClear
              options={workflows.map((w) => ({
                value: w.name,
                label: `${w.name}（${w.node_count} 节点）`,
              }))}
            />
          </div>
        </Space>
      </Collapse.Panel>
    </Collapse>
  );
}
```

- [ ] **Step 2: 类型检查 + 构建**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: 构建成功，产物在 `frontend/dist`

- [ ] **Step 3: 提交**

```bash
git add web/src/components/WorkflowSelector.tsx frontend/dist/
git commit -m "feat: 前端工作流选择器组件"
```

---

## Task 12: SessionChat 页——玩家输入框 + 发送 + 选择器 + 预设

**Files:**
- Modify: `web/src/pages/SessionChat.tsx`
- Create: `web/src/components/PresetViewer.tsx`

- [ ] **Step 1: 实现 PresetViewer 组件**

```tsx
// web/src/components/PresetViewer.tsx
import { useEffect, useState } from "react";
import { Collapse, Select, Typography, Button, Modal } from "antd";
import { FolderOpenOutlined } from "@ant-design/icons";
import { listWriterPresets, getWriterPreset } from "../api/client";

const { Text, Paragraph } = Typography;

export default function PresetViewer() {
  const [presets, setPresets] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [content, setContent] = useState("");
  const [path, setPath] = useState("");

  useEffect(() => {
    listWriterPresets().then(setPresets).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selected) return;
    getWriterPreset(selected).then((p) => { setContent(p.content); setPath(p.path); }).catch(() => {});
  }, [selected]);

  return (
    <Collapse ghost defaultActiveKey={[]}>
      <Collapse.Panel header="Writer 预设" key="1">
        <Select
          style={{ width: "100%" }}
          placeholder="选择预设"
          value={selected || undefined}
          onChange={setSelected}
          options={presets.map((p) => ({ value: p, label: p }))}
        />
        {selected && (
          <div style={{ marginTop: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>路径：{path}</Text>
            <Paragraph style={{ marginTop: 8, whiteSpace: "pre-wrap", maxHeight: 200, overflow: "auto", background: "#fafafa", padding: 8, borderRadius: 4 }}>
              {content}
            </Paragraph>
            <Button size="small" icon={<FolderOpenOutlined />} onClick={() => {
              Modal.info({ title: "编辑预设", content: `请在文件系统中打开目录编辑：${path}` });
            }}>
              跳转编辑
            </Button>
          </div>
        )}
      </Collapse.Panel>
    </Collapse>
  );
}
```

- [ ] **Step 2: 改造 SessionChat——加输入框、发送、选择器、预设**

在 `web/src/pages/SessionChat.tsx`：
- import `Input, SendTurn`、`WorkflowSelector`、`PresetViewer`、`sendTurn`
- 加 state：`mode`/`workflow`/`sending`/`inputText`
- 在 Header 下加 `<WorkflowSelector>` 和 `<PresetViewer>`
- 在 turns 列表底部加输入框 + 发送按钮：

```tsx
import { Input, Button } from "antd";
import { SendOutlined } from "@ant-design/icons";
import { sendTurn } from "../api/client";
import WorkflowSelector from "../components/WorkflowSelector";
import PresetViewer from "../components/PresetViewer";

// state 新增
const [inputText, setInputText] = useState("");
const [sending, setSending] = useState(false);
const [mode, setMode] = useState("hybrid");
const [workflow, setWorkflow] = useState("");

// 发送处理
const handleSend = async () => {
  if (!id || !inputText.trim()) return;
  setSending(true);
  try {
    const result = await sendTurn(id, inputText, { mode, workflow: workflow || undefined });
    if (result.success) {
      setInputText("");
      load();
    } else {
      message.error("发送失败");
    }
  } catch (e: any) {
    message.error(e.message);
  }
  setSending(false);
};

// JSX：在 bottomRef 前加
<div style={{ display: "flex", gap: 8, marginTop: 16 }}>
  <Input.TextArea
    value={inputText}
    onChange={(e) => setInputText(e.target.value)}
    placeholder="输入玩家消息…"
    autoSize={{ minRows: 1, maxRows: 4 }}
    onPressEnter={(e) => { if (!e.shiftKey) { e.preventDefault(); handleSend(); } }}
  />
  <Button type="primary" icon={<SendOutlined />} loading={sending} onClick={handleSend}>
    发送
  </Button>
</div>
```

- [ ] **Step 3: 改造续写按钮用 continueSessionV2**

把 `handleContinue` 里的 `continueSession(id)` 换为 `continueSessionV2(id, { mode, workflow: workflow || undefined })`。

- [ ] **Step 4: 类型检查 + 构建**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: 成功

- [ ] **Step 5: 提交**

```bash
git add web/src/pages/SessionChat.tsx web/src/components/PresetViewer.tsx frontend/dist/
git commit -m "feat: SessionChat 玩家输入框+发送+工作流选择器+Writer预设"
```

---

## Task 13: Cards 页——导入/删除/详情

**Files:**
- Modify: `web/src/pages/Cards.tsx`

- [ ] **Step 1: 改造 Cards 页**

加"导入角色卡"按钮（弹窗输入 source_path）、删除按钮（Popconfirm）、行点击展开看 greetings。

```tsx
import { Button, Modal, Input, Popconfirm, message, Drawer, List } from "antd";
import { ImportOutlined, DeleteOutlined } from "@ant-design/icons";
import { importCard, deleteCard, listGreetings } from "../api/client";

// state
const [importOpen, setImportOpen] = useState(false);
const [sourcePath, setSourcePath] = useState("");
const [importing, setImporting] = useState(false);
const [detailCard, setDetailCard] = useState<string | null>(null);
const [greetings, setGreetings] = useState<any[]>([]);

// 导入
const handleImport = async () => {
  setImporting(true);
  try {
    const r = await importCard(sourcePath);
    message.success(`导入成功：${r.card_id}`);
    setImportOpen(false); setSourcePath("");
    // reload
    listCards().then(setCards);
  } catch (e: any) { message.error(e.message); }
  setImporting(false);
};

// 删除
const handleDelete = async (cardId: string) => {
  await deleteCard(cardId);
  message.success("已删除");
  listCards().then(setCards);
};

// 看详情
const openDetail = async (cardId: string) => {
  setDetailCard(cardId);
  const gs = await listGreetings(cardId);
  setGreetings(gs);
};

// 表格列加操作列
{
  title: "操作", key: "action",
  render: (_, r) => (
    <span>
      <Button size="small" onClick={() => openDetail(r.card_id)}>详情</Button>
      <Popconfirm title="删除该卡及其所有会话？" onConfirm={() => handleDelete(r.card_id)}>
        <Button size="small" danger icon={<DeleteOutlined />} />
      </Popconfirm>
    </span>
  ),
}

// 顶部加导入按钮
<Button icon={<ImportOutlined />} onClick={() => setImportOpen(true)}>导入角色卡</Button>

// Modal + Drawer JSX
```

- [ ] **Step 2: 类型检查 + 构建**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: 成功

- [ ] **Step 3: 提交**

```bash
git add web/src/pages/Cards.tsx frontend/dist/
git commit -m "feat: Cards 页导入/删除/详情"
```

---

## Task 14: Sessions 页——新建/删除

**Files:**
- Modify: `web/src/pages/Sessions.tsx`
- Create: `web/src/components/NewSessionModal.tsx`

- [ ] **Step 1: 实现 NewSessionModal（开场白可选一体化）**

```tsx
// web/src/components/NewSessionModal.tsx
import { useEffect, useState } from "react";
import { Modal, Select, message } from "antd";
import { listCards, listGreetings, createSession, Card } from "../api/client";

interface Props { open: boolean; onClose: () => void; onCreated: () => void; }

export default function NewSessionModal({ open, onClose, onCreated }: Props) {
  const [cards, setCards] = useState<Card[]>([]);
  const [cardId, setCardId] = useState("");
  const [greetings, setGreetings] = useState<any[]>([]);
  const [greetingId, setGreetingId] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => { if (open) listCards().then(setCards); }, [open]);

  useEffect(() => {
    if (!cardId) return;
    setGreetingId("");
    listGreetings(cardId).then(setGreetings).catch(() => setGreetings([]));
  }, [cardId]);

  const handleCreate = async () => {
    if (!cardId || !greetingId) { message.warning("请选卡和开场白"); return; }
    setCreating(true);
    try {
      const r = await createSession(cardId, greetingId);
      message.success("会话已创建");
      onCreated();
      onClose();
    } catch (e: any) { message.error(e.message); }
    setCreating(false);
  };

  return (
    <Modal title="新建会话" open={open} onCancel={onClose} onOk={handleCreate} confirmLoading={creating} okText="创建">
      <p>角色卡</p>
      <Select style={{ width: "100%" }} value={cardId || undefined} onChange={setCardId}
        options={cards.map((c) => ({ value: c.card_id, label: c.name }))} placeholder="选择角色卡" />
      <p style={{ marginTop: 12 }}>开场白</p>
      <Select style={{ width: "100%" }} value={greetingId || undefined} onChange={setGreetingId}
        options={greetings.map((g) => ({ value: g.greeting_id, label: g.label || g.greeting_id }))}
        placeholder={cardId ? "选择开场白" : "先选角色卡"} disabled={!cardId} />
    </Modal>
  );
}
```

- [ ] **Step 2: 改造 Sessions 页**

加"新建会话"按钮 + 删除按钮（Popconfirm）。

```tsx
import { Button, Popconfirm, message } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import { deleteSession } from "../api/client";
import NewSessionModal from "../components/NewSessionModal";

const [modalOpen, setModalOpen] = useState(false);

const handleDelete = async (sid: string) => {
  await deleteSession(sid);
  message.success("已删除");
  listSessions().then(setSessions);
};

// 顶部加按钮
<Button icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>新建会话</Button>

// List.Item extra 加删除
extra={<span><Tag>{s.turn_count} 回合</Tag>
  <Popconfirm title="删除该会话？" onConfirm={() => handleDelete(s.session_id)}>
    <Button size="small" danger icon={<DeleteOutlined />} />
  </Popconfirm></span>}

// 末尾加
<NewSessionModal open={modalOpen} onClose={() => setModalOpen(false)} onCreated={() => listSessions().then(setSessions)} />
```

- [ ] **Step 3: 类型检查 + 构建**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: 成功

- [ ] **Step 4: 提交**

```bash
git add web/src/pages/Sessions.tsx web/src/components/NewSessionModal.tsx frontend/dist/
git commit -m "feat: Sessions 页新建/删除会话（开场白可选）"
```

---

## Task 15: 端到端验收 + README 更新

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 端到端手动验收清单**

启动 ComfyUI，访问 `http://localhost:8188/awp/`，逐项验证：
- [ ] Cards 页：导入角色卡 → 列表出现 → 点详情看 greetings → 删除
- [ ] Sessions 页：新建会话（选卡→选 greeting）→ 列表出现 → 删除
- [ ] SessionChat 页：打开已有会话 → **开场白+全部历史回合可见**（历史加载验收）
- [ ] SessionChat 页：输入玩家消息 → 发送 → 新回合气泡出现（玩家右、Writer左）
- [ ] SessionChat 页：点续写 → AI 自走回合出现
- [ ] 工作流选择器：展开 → 切 hybrid/python → 切工作流 → 发送仍正常
- [ ] Writer 预设：展开 → 选预设 → 看内容 → 跳转编辑提示
- [ ] 切 `AWP_EXECUTION_MODE=python` 重启 → 发送走直调

- [ ] **Step 2: 跑全量测试**

Run: `python -m pytest tests/ -q`
Expected: 全绿

- [ ] **Step 3: 更新 README 管理面板章节**

在 `README.md` 第 12 节管理面板，更新端点列表（加 turn/first-turn/import/delete/greetings/workflows/presets）+ 加双轨开关说明 + 工作流选择器说明。

- [ ] **Step 4: 提交**

```bash
git add README.md
git commit -m "docs: 更新管理面板章节（双轨+新端点+工作流选择器）"
```

---

## 自检

**Spec 覆盖**：
- §3 双轨执行引擎 → Task 6（调度层）+ Task 7（端点带 mode/workflow 参数）✓
- §3.2 工作流选择器 → Task 8（端点）+ Task 11（前端组件）✓
- §4.1 生成类端点 → Task 7 ✓
- §4.2 管理类端点 → Task 7 ✓
- §4.3 开场白可选 → Task 14（NewSessionModal）✓
- §4.4 Writer 预设可见 → Task 8（端点）+ Task 12（PresetViewer）✓
- §5 Reviser 补丁 → Task 4 ✓
- §6 hybrid 异步流程 → Task 6（_submit_and_wait 轮询）✓
- §7 前端 UI → Task 11-14 ✓
- §8 测试（含历史加载验收）→ Task 9 + 各 Task 测试步骤 ✓
- registry 缺 card_definition_store（调研发现的 bug）→ Task 1 ✓
- 工作流格式 gap → Task 5（用真 API 格式）✓

**遗留不确定性**（实现时需读代码确认，已在对应 Step 标注）：
- Task 2: store 表名、`_row_to_binding` 方法名、factories 是否存在
- Task 4: `RevisionRequest` 构造参数、bundle/writer_adapter 变量名、拒绝 receipt 结构
- Task 6: 节点 import 路径、`AWPV2AcceptedTextOutput` 在 history 的输出字段名
- Task 7: `CardSessionBootstrapPipeline` 从已有卡建会话的签名

这些在对应 Task 的 Step 1 都要求"先读代码确认"，非占位符。
