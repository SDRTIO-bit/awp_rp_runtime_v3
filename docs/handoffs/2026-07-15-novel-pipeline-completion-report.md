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
