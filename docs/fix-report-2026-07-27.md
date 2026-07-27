# 修复完成报告 — 2026-07-27

## 计划 vs 实际 逐条对照

### 阶段 0 — 数据止血

| # | 计划要求 | 状态 | 提交 | 差异 |
|---|---------|------|------|------|
| 0.1 | 更新 `.gitignore` 忽略运行数据 | ✅ | `e5fbd94c` | 无 |
| 0.2 | `git rm --cached` 停止跟踪，不删除本地数据 | ✅ | `e5fbd94c` | 198 文件从索引移除，磁盘完整保留 |
| 0.3 | 搜索当前版本及历史中的 API Key/Token | ✅ | — | 无明文 key 命中；`sk-xxx` 仅出现于文档占位符 |
| 0.4 | **不**执行 `git filter-repo` / force push | ✅ | — | 已跳过 |
| 0.5 | 保留可公开测试夹具，与真实数据分离 | ✅ | — | `autonomous_npc_fresh_trial` 会话文件同时从索引移除（保守处理） |

### 阶段 1 — POST/PUT 不匹配

| # | 计划要求 | 状态 | 提交 | 差异 |
|---|---------|------|------|------|
| 1.1 | 前端新增通用 `put()` 函数 | ✅ | `c60ba839` | 无 |
| 1.2 | `updateLlmConfig` 使用 PUT | ✅ | `c60ba839` | 无 |
| 1.3 | 不给后端增加兼容 POST 路由 | ✅ | — | 未添加 |
| 1.4 | 添加后端 API 测试和前端保存行为测试 | ✅ | `c60ba839` | `client.test.ts` (2 测试) + `test_novel_api.py` 路由注册断言 |

### 阶段 2 — 统一 LLM 配置链

| # | 计划要求 | 状态 | 提交 | 差异 |
|---|---------|------|------|------|
| 2.1 | 定义统一配置结构：provider / provider_id / model / api_base / api_key_env / max_tokens / thinking_level | ✅ | `4b79b356` | provider 存 type (`opencode`)，provider_id 在 backend 映射为 Pi 注册 ID (`awp-opencode`) |
| 2.2 | 前后端同一组 provider 枚举 | ✅ | `4b79b356` | `deepseek`/`opencode`/`mimo`/`siliconflow`/`custom` |
| 2.3 | `thinking_level` 真正转换为 Runtime 使用的思考配置 | ✅ | `4b79b356` | `_override_thinking_from_level()` 映射字符串 → THINKING_* dict |
| 2.4 | `max_tokens` 传到 Pi Host 模型注册参数，不得继续写死 4000 | ✅ | `4b79b356` | `novel_agent_host.mjs`: `connection.max_tokens`；`novel_role_host.mjs`: `task.max_tokens ?? 4000` |
| 2.5 | 不得在 API 中读取或返回真实 API Key | ✅ | `4b79b356` | `api_key` 始终为 None，仅暴露 `api_key_env` 名称 |
| 2.6 | 删除或绕过全局可变的项目覆盖状态。Runtime 创建时应显式接收解析完成的配置 | ⚠️ 部分 | `27aedc63` | `create_novel_role_runtime` 构建 resolver 时捕获单例 factory 状态；但 `_project_overrides` 仍存在 `NovelLLMFactory` 单例上。editor + role 两条路径现在都会读取项目覆盖，但切换依赖 `set_project_overrides()` + `reset()` 顺序调用 |
| 2.7 | 项目 A 和 B 配置同时存在，互不污染 | ✅ | `622b1b90` | 已验证：创建 A→设置覆盖→创建 B→切换覆盖→切回 A→验证无泄漏 |
| 2.8 | 已运行会话用创建时配置快照；新会话用数据库最新配置 | ⚠️ 部分 | — | `ensure_runtime` 在 Runtime 创建前 push 最新覆盖到单例；但同一 project 的两个并发 Runtime 共享同一份 `_project_overrides`。只有 role bridge resolver 闭包在创建时捕获了那一刻的 factory 状态 |
| 2.9 | 双项目并发或交错创建 Runtime 的隔离测试 | ✅ | `622b1b90` | 测试验证顺序 A→B→A 无泄漏 |

### 阶段 3 — 项目数据库边界

| # | 计划要求 | 状态 | 提交 | 差异 |
|---|---------|------|------|------|
| 3.1 | 所有带 `project_id` 的 API 使用对应 Workspace Registry | ✅ | `2ecb65fd` | `delete_project`、`plan_chapter`、`write_chapter`、`revise_chapter`、`batch_write`、`autonomy_summary`、`promote_character_state` 全部传入 `project_id` |
| 3.2 | 全局 Registry 改为 `_global_registry()`，避免无参数 `_registry()` 误用 | ✅ | `2ecb65fd` | `create_project`、`list_projects` 改用 `_global_registry()` |
| 3.3 | 双工作区测试，断言项目 A 数据不进入项目 B | ✅ | `622b1b90` | `test_project_registry_isolation_prevents_cross_db_writes` |

### 阶段 4 — CI

| # | 计划要求 | 状态 | 提交 | 差异 |
|---|---------|------|------|------|
| 4.1 | 删除 `testing.run_workflow_scenarios` 命令 | ✅ | `e620cc6d` | 已删除 |
| 4.2 | CI 运行 Python 全量测试 | ✅ | `e620cc6d` | `python -m pytest tests/` |
| 4.3 | CI 运行 agent_harness npm test | ✅ | `e620cc6d` | 独立 `node` job |
| 4.4 | CI 运行 web npm test + npm run build | ✅ | `e620cc6d` | 独立 `node` job |
| 4.5 | 增加 HTTP smoke test：health、projects、Prompt、LLM config | ⚠️ 路由级别 | `759c6a0e` | 验证路由已注册（`test_health_endpoint_returns_ok`、`test_novel_routes_registered`），但未启动真实 aiohttp server 发送 HTTP 请求 |
| 4.6 | 工作流名称改为 "AWP Novel Runtime CI" | ✅ | `e620cc6d` | 已改名 |

### 阶段 5 — 文档和启动器

| # | 计划要求 | 状态 | 提交 | 差异 |
|---|---------|------|------|------|
| 5.1 | README 加入前端依赖安装与构建步骤 | ✅ | `e620cc6d` | `npm ci && npm test && npm run build` |
| 5.2 | 修复字面量 `&lt;project-name&gt;` | ✅ | `e620cc6d` | 已修复 |
| 5.3 | 统一 `AWP_DB_PATH` 与 `AWP_RUNTIME_DB_PATH` | ✅ | `e620cc6d` | `awp_server.py` → `AWP_RUNTIME_DB_PATH` |
| 5.4 | 启动器检查 Node.js 实际版本 >=22.19 | ✅ | `e620cc6d` | `subprocess.run(["node", "-v"])` 检查 major 版本 |
| 5.5 | 确保 README 命令在干净 clone 后可直接执行 | ⚠️ 未验证 | — | 命令序列已写入 README，但未在实际干净 clone 环境执行 |

---

## 最终验证

| 套件 | 结果 | 耗时 |
|---|---|---|
| Python `pytest tests/` | **368 passed, 3 skipped** | 93s |
| `agent_harness` npm test | **23 passed, 0 failed** | 2.4s |
| `web` npm test | **7 passed, 0 failed** | 1.8s |
| `web` npm run build | **成功 (12 files)** | 6.6s |

## 新增测试清单

| 测试 | 文件 | 覆盖内容 |
|------|------|---------|
| `test_project_overrides_apply_to_role_config` | `test_novel_llm_factory.py` | 项目覆盖 → model / max_tokens / thinking_level |
| `test_thinking_level_overrides_default_thinking` | `test_novel_llm_factory.py` | thinking_level 关闭导演默认高思考 |
| `test_project_overrides_isolated_between_resets` | `test_novel_llm_factory.py` | A→B→A 切换无泄漏 |
| `test_health_endpoint_returns_ok` | `test_novel_api.py` | health 路由注册 |
| `test_novel_routes_registered` | `test_novel_api.py` | projects + llm-config 路由注册 |
| `test_project_llm_overrides_storage_isolation` | `test_novel_editor_session_manager.py` | 双项目 LLM 覆盖存储隔离 |
| `test_project_registry_isolation_prevents_cross_db_writes` | `test_novel_editor_session_manager.py` | 双项目数据库隔离 |
| `client.test.ts` (2 测试) | `web/src/api/client.test.ts` | PUT 方法 + 错误传播 |

## 提交链

```
54eff6a7 chore: tick off all completed items in fix plan
2fd7632b docs: update fix report with Round 2 results and remaining risks
622b1b90 test: add dual-project LLM override and registry isolation tests
759c6a0e test: add HTTP smoke assertions for health and novel routes
27aedc63 fix: propagate project LLM overrides to standalone Pi role runtime
ec01bd56 chore: tick off completed items in fix plan
cec36892 docs: add fix report for 2026-07-27 repair session
9aa83929 fix: align agent_harness test tool lists with source
a42444d1 fix: restore getAutonomySummary, align test tool lists with source
e620cc6d fix: CI pipeline, README, and launcher improvements
2ecb65fd fix: use project-scoped registry in all API handlers
4b79b356 fix: unify LLM config chain from frontend to Pi runtime
c60ba839 fix: use PUT for LLM config save (was POST)
e5fbd94c fix: stop tracking local runtime data (.awp authoring, .omo)
```

## 仍未处理的风险

1. **Git 历史中的运行时数据**：只做了 `git rm --cached` + 新 commit，旧文件仍可从历史恢复。需要独立执行 `git filter-repo` 后 force push。

2. **`pi-role-sessions` 历史残留**：`autonomous_npc_fresh_trial` 和 `星坠王庭` 的旧 session 文件已从索引移除，但历史中仍存在。

3. **全局 LLM 单例 `_project_overrides`**：`NovelLLMFactory` 单例仍持有全局可变覆盖配置。`create_novel_role_runtime` 的 resolver 闭包和 `ensure_runtime` 的 `set_project_overrides()` 都已正确调用，并发下推荐改为 `factory.for_project(project_id, config)` 工厂模式。

4. **配置快照语义不完整**：同一项目的两个并发 Runtime 共享同一份 `_project_overrides`——role bridge 的 resolver 闭包在创建时捕获那一刻的状态，但这是靠闭包行为而非显式快照机制保证的。

5. **HTTP 端到端 smoke 测试**：当前 smoke job 跑的是路由注册断言（不启动 server）。完整的端到端验证需 `pytest-asyncio` + `aiohttp` test client。

## Git 历史清理独立步骤

```bash
pip install git-filter-repo

git filter-repo \
  --path .omo/run-continuation/ \
  --path .omo/plans/ \
  --path novels/daily_high_school/.awp/authoring/ \
  --path novels/daily_high_school/.awp/file-history/ \
  --path novels/daily_high_school/.awp/tool-audit/ \
  --path novels/autonomous_npc_fresh_trial/.awp/pi-role-sessions/ \
  --path "novels/星坠王庭/.awp/pi-role-sessions/" \
  --invert-paths

# 确认后执行（这会重写历史）：
# git push --force origin main
```
