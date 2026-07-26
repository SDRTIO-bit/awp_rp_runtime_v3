# 纯小说系统收敛审计

日期：2026-07-26

## 结论

产品已决定放弃 RP Mode。仓库需要先收敛为纯小说创作系统，再实施专属写作编辑 Agent。

清理不能只按 `novel_` 文件名前缀执行。小说管线仍然复用了 SQLite、LLM 适配、Active/RAG Memory 和少量历史合约；这些共享基础设施必须保留。反过来，ComfyUI 节点、RP 回合引擎、角色卡导入、动态子 Agent、RP 管理页面和 RP 验收工具没有小说调用方，应移除。

## 当前规模

| 区域 | 跟踪文件数 | 审计结论 |
|---|---:|---|
| `runtime/*.py` | 154 | 29 个小说命名模块；其余按调用图拆分 |
| `contracts/*.py` | 139 | 15 个小说命名合约；保留小说实际依赖的共享记忆/质量合约 |
| `tests/` Python 测试 | 108 | 35 个小说测试；删除纯 RP/ComfyUI 测试 |
| `nodes/` | 117 | 纯 ComfyUI/RP，删除 |
| `workflows/` | 14 | 纯 RP/ComfyUI，删除 |
| `testing/` | 43 | 纯 RP/ComfyUI 验收工具；小说测试不直接依赖，删除 |
| `web/node_modules/` | 19,627 | 误提交的生成依赖，取消跟踪并加入 `.gitignore` |
| RP 历史文档候选 | 33 | 删除活跃仓库中的纯 RP 资料，历史仍可从 Git 获取 |

`web/node_modules/` 当前约占 79.3 MB，是最明确的仓库污染项。

## 保留边界

### 小说核心

- `agent_harness/`
- `runtime/novel_*.py`
- `contracts/novel_*.py`
- `storage/sqlite/novel_stores.py`
- `storage/novel_interfaces.py`
- `scripts/novel_cli.py`
- `scripts/awp_tui.py`
- `novels/`
- 小说提示词、项目文档和 `tests/test_novel*.py`

### 小说仍使用的共享基础设施

- `adapters/llm/base.py`
- `adapters/llm/deepseek_adapter.py`
- `adapters/llm/openai_compatible.py`
- `runtime/prompt_loader.py`
- `runtime/provider_env_guard.py`
- `runtime/session_runtime_registry.py`，但收窄为小说与小说记忆 Store
- `runtime/active_memory_commit_runtime.py`
- `runtime/active_memory_recall_runtime.py`
- `runtime/rag_memory_commit_runtime.py`
- `runtime/rag_recall_runtime.py`
- Active/RAG Memory、Memory Recall、Memory Commit、Quality Decision/Issue 等被小说调用的共享合约
- SQLite Database 和 Active/RAG Memory Store

这些模块暂时保留历史字段名 `card_id` / `session_id`，因为小说记忆已用固定 scope 映射到这些字段。字段重命名不是本次清理的必要条件。

## 删除边界

### Python 产品代码

- RP 回合编排、Director/Writer/Critic V1-V2、动态 D1-D6 Agent、RP Tool Gateway。
- 角色卡导入、启动、CardState 提交、世界书绑定。
- ComfyUI 诊断、工作流和节点运行时。
- RP 独立管理 API、会话删除服务和 Console。
- `nodes/`、`services/`、`policies/`、`testing/`。

### Web

- 会话、角色卡、RP Pipeline Drawer、工作流选择器和 Writer Preset 页面。
- API 客户端中的 RP 类型及路由。
- 跟踪中的 `web/node_modules/`。

保留小说项目列表和详情页，并将默认路由改为 `/novels`。独立服务器改成小说 API 与静态站点，不再导入 RP `management_api.py`。

### 测试和资料

- 删除非小说测试、ComfyUI fixture、RP workflow scenario。
- 删除纯 RP 架构、交接、测试和参考文档。
- 删除根目录下仅用于 RP/临时调试的脚本。

## 必须先改再删的混合点

1. 根 `__init__.py` 当前注册 ComfyUI Nodes、导入 `management_api` 并自动启动 RP Server。改为无副作用的小说包入口。
2. `runtime/session_runtime_registry.py` 当前实例化所有 RP Store。先收窄为小说与小说记忆 Store。
3. `storage/interfaces.py` 混合 RP 与 Memory 接口。先留下小说记忆需要的接口。
4. `runtime/management_api.py` 混合了 Novel API。先把小说端点迁入独立 `runtime/novel_api.py`。
5. `scripts/awp_server.py` 当前只注册 RP 路由。改写为小说专用服务器。
6. `web/src/api/client.ts` 同时包含 RP 与 Novel API。改写为小说专用客户端。
7. `tests/conftest.py` 当前加载 ComfyUI stub 和 RP Fake Store。收窄为小说角色运行时 fixture。

## 删除安全规则

- 仅删除 Git 已跟踪、审计为纯 RP 的文件。
- 不删除 `novels/` 下的作者项目、正文、数据库或未跟踪运行产物。
- 不删除 `.omo/` 当前续跑状态。
- 所有批量删除目标先解析为工作区内绝对路径并检查存在性。
- 清理分独立 Git 提交；每个提交后运行小说 Python 测试或 Node Harness 测试。
- Git 历史保留已删除内容，不在活跃源码树中另建 RP 归档副本。

## 验收

- 包导入不注册 ComfyUI Node，不启动后台服务器。
- 安装包不再包含 `nodes`、`services`、`policies` 或 `testing`。
- Web 默认只显示小说产品。
- `web/node_modules` 不再被 Git 跟踪。
- 默认和 legacy 小说 Agent 仍可导入。
- 小说 Store、CLI、TUI、Pi Host 和 NovelEngine 测试通过。
- 仓库级搜索没有产品代码引用已删除 RP 模块。
