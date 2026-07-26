# Novel-only 清理交接（2026-07-26）

仓库已经从双模式 RP/Novel 产品收敛为纯小说系统。

## 已完成

- 根包导入不再注册 ComfyUI Node 或启动服务器。
- 移除 RP/ComfyUI 的 nodes、workflows、services、policies、testing、会话 API、前端页面、测试和历史资料。
- 移除 Git 中误跟踪的 `web/node_modules`。
- Store Registry 仅保留 9 个 Novel Store 和 Active/RAG Memory。
- Web 与独立 HTTP Server 只暴露小说项目路由。
- 小说仍用的 MemoryPolicy 已迁入 `runtime/novel_memory_policy.py`。
- `novels/` 与 `.omo/` 的本地作者数据未进入删除清单。

清理提交 `1d67807f` 删除 587 个文件，约 101,691 行。当前跟踪文件约 932 个；Python 产品面保留约 42 个 runtime 模块、26 个 contracts 模块和 42 个测试文件。

## 兼容债

Python import 名仍是 `awp_rp_runtime_v3`，用于现有项目脚本兼容。SQLite 迁移中保留旧 RP 表和 memory 的 `card_id` / `session_id` 字段，以便旧数据库继续升级；活跃产品代码不再使用 RP 引擎。

## 验证

- Novel 包/API/Store 定向测试：35 项通过。
- retained Python 测试收集：205 项成功收集（新增 authoring 测试后更多）。
- Node Harness：17 项通过。
- Web production build：成功。
- 一个既有 nested-host 测试仍期待已停用的 continuity checker 调用顺序，与本次删除无关。
