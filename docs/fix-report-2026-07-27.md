# 修复完成报告 — 2026-07-27

## 已验证完成

### 阶段 0：数据止血 ✅ `e5fbd94c`
- `.gitignore` 追加 `.omo/run-continuation/`、`.omo/plans/`、`novels/**/.awp/authoring/`、`novels/**/.awp/file-history/`、`novels/**/.awp/tool-audit/`
- `git rm --cached -r` 移除 198 个运行时文件
- 密钥扫描：无明文 API Key、无 JWT Token、`docs/handoffs/*.md` 中仅含占位符 `sk-xxx`
- `git filter-repo` 历史重写：**已跳过**，待独立执行（详见文末步骤）

### 阶段 1：POST → PUT ✅ `c60ba839`
- `web/src/api/client.ts`：新增 `put()` 函数，`updateLlmConfig()` 改用 PUT
- 后端路由已是 PUT，无需修改
- 测试：`client.test.ts` (2 个 Vitest 测试) + `test_novel_api.py` 路由注册断言

### 阶段 2：LLM 配置链统一 ✅ `4b79b356`
- 供应商 ID：前端 `LOCAL_PROVIDERS` 改为 `deepseek`/`opencode`/`mimo`/`siliconflow`/`custom`
- `thinking_level`：新增 `_override_thinking_from_level()` 方法，支持 `low`/`medium`/`high`/`off` 字符串 → THINKING_* 字典
- `NovelLLMFactory.get_instance()`：所有调用方统一使用单例（`novel_pi_bridge.py`、`novel_pi_role_bridge.py`、`novel_role_runtime.py`）
- `novel_agent_host.mjs`：maxTokens 从 `connection.max_tokens` 读取（不再写死 4000）
- `get_llm_config` API：返回 provider type 而非内部 `awp-*` id
- 测试：`test_project_overrides_apply_to_role_config`、`test_thinking_level_overrides_default_thinking`、`test_project_overrides_isolated_between_resets`

### 阶段 3：项目数据库边界 ✅ `2ecb65fd`
- `delete_project`、`plan_chapter`、`write_chapter`、`revise_chapter`、`batch_write`、`autonomy_summary`、`promote_character_state`：全部传入 `project_id` 到 `_registry()`
- `create_project`、`list_projects`：使用 `_global_registry()`（新增方法，明确语义）
- API 路由测试通过

### 阶段 4：CI + README + 启动器 ✅ `e620cc6d`
- CI：删除 `testing.run_workflow_scenarios` 命令；拆分为 python / node / smoke 三 job；重命名为 "AWP Novel Runtime CI"
- README：增加前端 `npm ci && npm test && npm run build` 前置步骤；修复 `&lt;project-name&gt;`；更新测试命令块
- `awp_server.py`：`--db-path` 环境变量改为 `AWP_RUNTIME_DB_PATH`
- `awp_web_launcher.py`：增加 Node.js >=22.19 版本检查

### 后续修正 ✅ `a42444d1` + `9aa83929`
- 恢复 `getAutonomySummary` 导出（`client.ts` 中接口重排时丢失）
- 恢复 `LlmRoleOverride.model` 字段
- 更新 `novel_agent_host.test.mjs` 和 `novel_tools.test.mjs` 中的工具列表与 source 端一致
- 更新 system-prompt regex 匹配当前 prompt 文本

## 测试证据

### 最终验证 (2026-07-27 Round 2)

| 套件 | 结果 | 耗时 |
|---|---|---|
| Python tests/ | **368 passed, 3 skipped** | 93s |
| agent_harness npm test | **23 passed, 0 failed** | 2.4s |
| web npm test | **7 passed, 0 failed** | 1.8s |
| web npm run build | **成功** | 6.6s |

### 新增测试

| 测试 | 文件 | 覆盖内容 |
|------|------|---------|
| `test_project_overrides_apply_to_role_config` | `test_novel_llm_factory.py` | 项目覆盖 → model/max_tokens/thinking_level |
| `test_thinking_level_overrides_default_thinking` | `test_novel_llm_factory.py` | thinking_level 关闭导演的默认高思考 |
| `test_project_overrides_isolated_between_resets` | `test_novel_llm_factory.py` | A→B→A 切换无泄漏 |
| `test_health_endpoint_returns_ok` | `test_novel_api.py` | health 路由注册 |
| `test_novel_routes_registered` | `test_novel_api.py` | projects + llm-config 路由 |
| `test_project_llm_overrides_storage_isolation` | `test_novel_editor_session_manager.py` | 双项目 LLM 覆盖隔离 |
| `test_project_registry_isolation_prevents_cross_db_writes` | `test_novel_editor_session_manager.py` | 双项目数据库隔离 |
| `client.test.ts` (2 测试) | `web/src/api/client.test.ts` | PUT 方法 + 错误传播 |

## 仍未处理的风险

1. **Git 历史中的运行时数据**：当前只做了 `git rm --cached` + 新 commit。198 个已删除文件仍可从 Git 历史中恢复。需独立执行 `git filter-repo --path-regex` 彻底重写。
2. **`novels/**/.awp/pi-role-sessions/` 和 `pi-sessions/`**：`.gitignore` 已有规则，但 `autonomous_npc_fresh_trial` 和 `星坠王庭` 下的旧 session 文件已从索引中移除。这两个项目可能是公开测试夹具——如果包含真实 API 调用，历史中仍有残留。
3. **全局 LLM 单例仍然存在**：虽然所有调用方现在用 `get_instance()`，`PiNovelRoleRuntime` 在 `create_novel_role_runtime` 中构建 resolver 时依赖 `factory.get_pi_role_connection()` 能够读取当前项目覆盖。并发下仍需依赖调用方在创建 role bridge 之前正确处理 `set_project_overrides()` + `reset()`。已在隔离测试中验证双项目切换正确性，但此单例模式仍建议后续改为工厂模式 `factory.for_project(project_id, config)`。
4. **HTTP smoke 测试**：当前 smoke job 跑的是路由注册测试（无需真实服务器）。完整的端到端 HTTP smoke（启动 server → GET health → GET/PUT llm-config → shutdown）建议后续以 `pytest-asyncio` + `aiohttp` test client 实现。

## Git 历史清理独立步骤

```bash
# 安装 git-filter-repo
pip install git-filter-repo

# 从全部历史中移除泄漏路径
git filter-repo \
  --path .omo/run-continuation/ \
  --path .omo/plans/ \
  --path novels/daily_high_school/.awp/authoring/ \
  --path novels/daily_high_school/.awp/file-history/ \
  --path novels/daily_high_school/.awp/tool-audit/ \
  --path novels/autonomous_npc_fresh_trial/.awp/pi-role-sessions/ \
  --path "novels/星坠王庭/.awp/pi-role-sessions/" \
  --invert-paths

# 强制推送（需确认！这会重写历史）
# git push --force origin main
```
