# 贡献指南

## 最小贡献流程

### 1. 创建分支

```bash
git checkout -b feat/your-feature main
```

### 2. 运行测试

```bash
python -m pytest tests/ -q
```

所有测试必须通过才能提交。

### 3. 保持合同 schema 版本兼容

- 所有数据结构必须携带 `schema_id` 和 `schema_version`
- 修改现有合同时，必须递增 schema_version
- 新增合同必须使用唯一的 schema_id

### 4. 新增 Agent 时必须声明权限

- 在 `AgentRoleSpec` 中声明工具权限
- 在 `ToolProfile` 中定义可用工具集
- 明确是否可以委派、是否可以写状态/记忆

### 5. 新增副作用时必须通过 Commit Runtime

- CardState 写入：通过 `CardStateCommitRuntime`
- TurnRecord 写入：通过 `TurnRecordCommitRuntime`
- ActiveMemory 写入：通过 `ActiveMemoryCommitRuntime`
- RagMemory 写入：通过 `RagMemoryCommitRuntime`
- 任何新的副作用必须有对应的 CommitRuntime

### 6. 新增 workflow 时必须补 JSON 校验

- workflow JSON 必须包含所有节点定义
- 必须验证节点连接正确
- 必须在测试中验证 JSON 结构

### 7. 提交前检查清单

- [ ] 不包含 API Key、Token、Cookie
- [ ] 不包含真实用户角色卡
- [ ] 不包含私密世界书
- [ ] 不包含 SQLite 数据库文件
- [ ] 不包含 Trace 日志
- [ ] 不包含 `.env` 文件
- [ ] 所有测试通过
