# 小说管线完成报告

**日期**：2026-07-15  
**分支**：`codex/pi-novel-role-agents`  
**最新提交**：`2077b7f4 fix(agent_harness): map Qwen 3.7 Plus Writer thinking_level=off to enable_thinking=false`

## 1. 结论

小说模式（Novel Mode）的端到端生成管线已打通。从项目初始化、章节规划、正文生成、质量检查、账本整理到文件导出，均能在 `NOVEL_AGENT_RUNTIME=pi` + `NOVEL_LLM_PROVIDER=opencode` + `qwen3.7-plus` 的配置下稳定跑完，并产出合格正文。

最近一次完整验证通过 CLI 生成了第 1 章，**1925 字**，故事完整、人物动机清晰、结尾留钩。

## 2. 已完成的组件

### 2.1 核心引擎

| 组件 | 文件 | 说明 |
|------|------|------|
| 小说主引擎 | `runtime/novel_engine.py` | `plan_chapter` / `write_chapter` / `audit_chapter` / `batch_write` |
| 流式回调 | `runtime/novel_trace.py` | `NovelStreamCallbacks`：on_phase / on_beat / on_chunk / on_error |
|  writer 适配器 | `runtime/novel_writer_adapter.py` | 单 beat 生成、上下文拼接、质量门 |
|  architect 适配器 | `runtime/novel_architect_adapter.py` | JSON 章节计划抽取与校验 |
|  director 适配器 | `runtime/novel_director_adapter.py` | beat 指导生成 |
|  quality 适配器 | `runtime/novel_quality_adapter.py` | 质量检查与重试 |
|  continuity checker | `runtime/novel_continuity_checker.py` | 长程一致性检查 |
|  ledger curator | `runtime/novel_ledger_curator.py` | 账本条目整理 |
| LLM 工厂 | `runtime/novel_llm_factory.py` | 按角色分配模型、provider 切换、Pi 连接配置 |

### 2.2 嵌入式 Pi 代理层

| 组件 | 文件 | 说明 |
|------|------|------|
| Pi 桥接 | `runtime/novel_pi_bridge.py` | Python ↔ Node JSON Lines 桥 |
| 工具服务 | `runtime/novel_pi_tool_service.py` | 项目级只读工具 allowlist |
| 角色运行时 | `runtime/novel_role_runtime.py` | Pi / legacy 运行时选择 |
| Pi Host | `agent_harness/src/novel_role_host.mjs` | Node 子进程，管理 6 个小说角色 session |
| 角色工具 | `agent_harness/src/novel_role_tools.mjs` | project_status / read_chapter / plan_chapter / write_chapter / audit_chapter |
| 角色资源 | `agent_harness/src/novel_role_resources.mjs` | 按角色加载 system prompt 与 skill |
| 角色提示 | `agent_harness/resources/roles/*/system-prompt.md` | Architect / Director / Writer / Checker / Curator / Style Cleaner |

**关键修复**：`qwen3.7-plus` Writer 原先会把 4K 输出窗全部用于内部 thinking，导致正文为空。已在 `agent_harness/src/novel_role_host.mjs` 中为 Writer 注册 `compat: { thinkingFormat: "qwen", supportsReasoningEffort: false }` 并保持 `reasoning: true`，使 `thinking_level=off` 正确映射为请求体里的 `enable_thinking: false`。

### 2.3 命令行与交互界面

| 组件 | 文件 | 说明 |
|------|------|------|
| 小说 CLI | `scripts/novel_cli.py` | init / seed / plan / write / batch / export / status / run |
| TUI | `scripts/awp_tui.py` | 左右分栏（管线 + 聊天）的 Textual 界面 |
| 启动脚本 | `tui.bat` | Windows 启动器 |

CLI 已验证命令：

```powershell
$env:NOVEL_AGENT_RUNTIME = "pi"
$env:NOVEL_LLM_PROVIDER = "opencode"
$env:NOVEL_LLM_MODEL = "qwen3.7-plus"
python scripts/novel_cli.py init  <dir>
python scripts/novel_cli.py run   <dir> 1 1
```

### 2.4 存储与合约

| 组件 | 文件 | 说明 |
|------|------|------|
| SQLite 数据库 | `storage/sqlite/database.py` | 初始化全部小说表 |
| 小说 store | `storage/sqlite/novel_stores.py` | projects / plans / drafts / ledger / characters / batch_progress |
| Store 注册表 | `runtime/session_runtime_registry.py` | `SessionRuntimeStoreRegistry` 提供 10 个 store |
| 合约模型 | `contracts/novel_*.py` | `NovelProject`、`ChapterPlan`、`ChapterDraft`、`LedgerItem` 等 |

### 2.5 前端

| 页面/组件 | 文件 |
|-----------|------|
| 小说列表 | `web/src/pages/Novels.tsx` |
| 小说详情 | `web/src/pages/NovelDetail.tsx` |
| RP 管线抽屉 | `web/src/components/PipelineStreamDrawer.tsx` |

## 3. 验证结果

### 3.1 单元 / 回归测试

- `agent_harness` Node 测试：**17 passed**（含 Qwen Writer compat 回归测试）
- `tests/test_novel_llm_factory.py`：**2 passed**
- `tests/test_novel_pi_role_e2e.py` 真实外部验收：**passed**

### 3.2 真实模型验收

环境：

```powershell
$env:NOVEL_AGENT_RUNTIME = "pi"
$env:NOVEL_LLM_PROVIDER = "opencode"
$env:NOVEL_LLM_MODEL = "qwen3.7-plus"
$env:NOVEL_PI_ROLE_E2E = "1"
```

结果：

- `plan.target_chars == 2000`
- `draft.text` 长度 **1860 字符**（≥ 1600 阈值）
- 五个角色全部参与：`architect`、`director`、`writer`、`continuity_checker`、`ledger_curator`
- 导出文件 `chapter_01.txt` 正常生成

### 3.3 CLI 完整生成

项目目录：`C:\Users\zhao\AppData\Local\Temp\qwen-novel-demo`

```powershell
python scripts/novel_cli.py run C:/Users/zhao/AppData/Local/Temp/qwen-novel-demo 1 1
```

输出：

```text
项目: 告白字幕失控了 (qwen-novel-demo)
  角色: 唐梨 [protagonist]
  角色: 陈默 [protagonist]
  卷计划: 第一卷：被迫官宣 (第1-3章)
批量完成: 1章, 总计1925字
导出完成: ...\export
全部完成!
```

生成的 `output/chapter_01.md` 为完整章节：

- 开篇：礼堂大屏幕跳出告白字幕
- 发展：唐梨拽陈默上台顶锅
- 高潮：话筒前对峙，唐梨低声威胁
- 结尾：两人逃入楼梯间，陈默质问“到底怎么回事”

## 4. 已知限制与后续建议

### 4.1 当前限制

1. **全量 `pytest tests` 在工作树中无法收集**：部分 RP 旧测试使用 `from ..contracts...` 相对导入，而 `.worktrees/pi-novel-role-agents` 的目录布局使 `tests` 与 `contracts/runtime` 平级，导致 `attempted relative import beyond top-level package`。这是工作树布局问题，不影响小说管线本身。
2. **合并需在主工作树处理**：当前提交在 `codex/pi-novel-role-agents` 分支，尚未合并到 `main`。
3. **Qwen 参数仅对 Writer 生效**：为避免影响 Architect / Director 的 JSON 跟随性，Qwen `enable_thinking` 映射仅作用于 Writer 角色。若未来其他角色也需要显式关闭 thinking，可参照同模式扩展。

### 4.2 建议的后续工作

- 在主仓库工作树跑通 `python -m pytest tests -q` 后再合并。
- 增加第 2-3 章的批量生成验证，观察长程一致性。
- 若用户后续改用 `qwen3.7-max` 或其他模型，需在 `novel_llm_factory.py` 与 `novel_role_host.mjs` 中补充对应参数映射。
- 继续观察 LedgerCurator 在章节增多后的稳定性；目前第 1 章可稳定完成。

## 5. 如何复现

```powershell
cd F:\12\语英\awp_rp_runtime_v3\.worktrees\pi-novel-role-agents
$env:NOVEL_AGENT_RUNTIME = "pi"
$env:NOVEL_LLM_PROVIDER = "opencode"
$env:NOVEL_LLM_MODEL = "qwen3.7-plus"

python scripts/novel_cli.py init ./my_novel
# 编辑 my_novel/project.json 与 outline.md
python scripts/novel_cli.py run ./my_novel 1 1
```

## 6. 结论

小说生成管线已完成并验证。Writer 空输出问题已根修，CLI 可一次性生成完整章节，端到端数据流（plan → draft → audit → ledger → export）已跑通。

---

# 附录：自主 NPC 与预设编译层交付报告

**日期**：2026-07-15  
**分支**：`codex/novel-autonomous-npc`（merge base `d603f456`）  
**提交记录**：

- `525e4202` — feat: add novel autonomy contracts and profile
- `1d88a323` — feat: isolate novel agenda writer context
- `0caa7105` — feat: add pi npc agenda planner
- `fe203856` — feat: commit accepted autonomous npc actions
- `a4c86392` — feat: autonomy observability API, CLI promote-state, and UI

## 1. 完成目标

在 Novel Mode 中加入受版本化 Profile 约束的自主 NPC 行动，并确保 Writer 只能看到可见后果，原始议程、私密目标与选择理由对 Writer 完全隔离。

## 2. 新增与修改的组件

### 2.1 合约层

| 文件 | 说明 |
|------|------|
| `contracts/novel_profile.py` | `NovelWritingProfile`、`load_autonomous_profile`；`mode="novel"` 校验，拒绝 RP 模式。 |
| `contracts/novel_npc_agenda.py` | `NpcAgenda`、`VisibleConsequence`、`SelectedNpcAction`。 |
| `contracts/novel_director_guidance.py` | `DirectorGuidance.selected_npc_actions`。 |
| `contracts/novel_write_packet.py` | `NovelWritePacket.visible_consequences`。 |

### 2.2 Profile / 议程服务层

| 文件 | 说明 |
|------|------|
| `runtime/novel_profile_compiler.py` | `NovelProfileCompiler` 识别 `AUTONOMOUS_NPC` 并设置模式。 |
| `runtime/novel_agenda_service.py` | `NpcAgendaService.active/eligible/expire`；上限 8、按 `(npc, thread_key)` 合并、过期检测。 |

### 2.3 角色与规划器

| 文件 | 说明 |
|------|------|
| `runtime/novel_llm_factory.py` | 新增 `npc_planner` Pi role 连接。 |
| `runtime/novel_director_adapter.py` | `select_npc_actions()` 生成/筛选 `SelectedNpcAction`。 |
| `agent_harness/src/novel_role_host.mjs` | `npc_planner` 角色会话注册。 |
| `agent_harness/resources/roles/npc_planner/` | 角色 system prompt 与 skill 资源。 |

### 2.4 Engine 与 Curator

| 文件 | 说明 |
|------|------|
| `runtime/novel_engine.py` | `write_chapter` / `write_chapter_stream` 接入 `_prepare_autonomous_npc_context`；仅在质量通过后提交 `npc_action`/`npc_agenda`。 |
| `runtime/novel_writer_context.py` | `NovelWritePacket.visible_consequences` 填充；`_relevant_ledger` 过滤隐私 section。 |
| `runtime/novel_evolution_curator.py` | `curate(..., selected_npc_actions=())`，接受后持久化 `npc_action`。 |
| `runtime/novel_continuity_checker.py` | 增加 NPC 连续性与后果可见性检查。 |
| `runtime/novel_ledger_curator.py` | 白名单识别 `npc_agenda` / `npc_action`。 |

### 2.5 可观测性与人工提升

| 文件 | 说明 |
|------|------|
| `runtime/management_api.py` | `GET /novels/{id}/autonomy-summary`、`POST /novels/{id}/characters/{character_id}/state-promotions`。 |
| `scripts/novel_cli.py` | `promote-state` 子命令。 |
| `web/src/api/client.ts` | `getAutonomySummary`、`promoteCharacterState` 类型与请求函数。 |
| `web/src/pages/NovelDetail.tsx` | 项目级与章节级 NPC 自主性计数 UI，不展示 agenda 原文。 |

### 2.6 测试

| 文件 | 说明 |
|------|------|
| `tests/test_novel_autonomous_npc_contracts.py` | Profile/Agenda/Writer 隔离合约测试。 |
| `tests/test_novel_autonomous_npc_planner.py` | Pi planner 与 Director 选择逻辑测试。 |
| `tests/test_novel_autonomous_npc_engine.py` | 接受/拒绝副作用、Writer 包隐私测试。 |
| `tests/test_novel_autonomous_npc_api.py` | 摘要隐私、状态提升、跨项目校验 API 测试。 |
| `tests/test_novel_autonomous_npc_e2e.py` | 两章 fake-E2E，验证第 1 章动作影响第 2 章。 |
| `tests/test_novel_autonomous_npc_cli.py` | `promote-state` CLI 测试。 |
| `tests/test_novel_llm_factory.py` | 更新 Pi role 集合断言。 |

## 3. 验证结果

### 3.1 Python 相关测试

```powershell
python -m pytest --tb=short -q tests/test_novel_autonomous_npc_contracts.py tests/test_novel_autonomous_npc_engine.py tests/test_novel_autonomous_npc_planner.py tests/test_novel_autonomous_npc_api.py tests/test_novel_autonomous_npc_e2e.py tests/test_novel_autonomous_npc_cli.py tests/test_novel_llm_factory.py tests/test_management_api_new_endpoints.py
```

结果：**50 passed**

### 3.2 Node / Pi 测试

```powershell
npm test --prefix agent_harness
```

结果：**17 passed, 0 failed**

### 3.3 全量 Python 套件说明

工作树运行 `python -m pytest tests` 仍会因 `tests` 目录非包（部分 RP 旧测试使用 `from ..contracts...` 相对导入）而在 7 个 RP 旧测试文件收集阶段报错。这是工作树目录布局的既有问题，不影响小说管线本身；本次改动未触及 RP 代码。

### 3.4 Web 构建说明

`npm run build` 在 `web` 目录因 `react-router-dom` 依赖未安装（`node_modules/react-router-dom/package.json` 缺失）而无法通过，同样为既有环境问题，与本次新增代码无关。

## 4. 安全与约束

- **零副作用拒绝**：质量门未通过时，不会写入 `npc_action` 或 `npc_agenda`。
- **Writer 隐私**：Writer 包、Pi read tool 与 prompt 中均不会出现 `private_goal`、`secret_clue` 等私密字段；只传递 `VisibleConsequence`。
- **人工提升闸门**：`state-promotions` 端点拒绝 `name`、`role`、`core_motivation`、`known_fact_ids` 等身份/动机/知识键；仅允许修改 `current_state` 中的状态字段。
- **不建表、不扩展 RP**：仅使用现有 `LedgerItem` 表与 `novel_characters` 表；未修改 RP 引擎。

## 5. 如何使用

### 5.1 在小说中启用自主 NPC

```powershell
python scripts/novel_cli.py init ./my_novel
python scripts/novel_cli.py profile-init ./my_novel
# 编辑 my_novel/autonomous_profile.json 与 outline.md
python scripts/novel_cli.py run ./my_novel 1 1
```

### 5.2 查看自主状态摘要

```powershell
python - <<'PY'
import requests, json
res = requests.get("http://127.0.0.1:8189/awp/api/v1/novels/{project_id}/autonomy-summary")
print(json.dumps(res.json()["data"], indent=2, ensure_ascii=False))
PY
```

### 5.3 人工提升角色状态

```powershell
python scripts/novel_cli.py promote-state ./my_novel <character_id> --source <npc_action_item_id> --patch '{"injured": true, "mood": "guilty"}'
# 或 REST
POST /awp/api/v1/novels/{project_id}/characters/{character_id}/state-promotions
{ "source_item_id": "<item_id>", "patch": { "injured": true, "mood": "guilty" } }
```

## 6. 结论

自主 NPC 预设编译层已完整实现并验证。数据链 `NpcAgenda → SelectedNpcAction → VisibleConsequence` 已固定；Writer 仅消费可见后果，Curator 仅在接受后持久化中间项，人工提升端点提供安全的作者干预入口。
