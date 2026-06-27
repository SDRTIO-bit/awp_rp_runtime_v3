# 安全政策

## 不要提交以下内容

- API Key、Token、Cookie
- 真实用户角色卡
- 私密世界书
- SQLite 数据库文件（`.db`、`.sqlite`、`.sqlite3`）
- Trace 日志（`*.log`、`traces/`）
- `.env` 文件（除 `.env.example` 外）
- 任何包含真实密钥的配置文件

## 真实模型调用

真实模型调用属于未来接入能力。当前测试应默认使用 Fake Adapter。

```bash
# 真实模型调用需要设置环境变量（未来功能）
# export AWP_LLM_API_KEY="your-api-key"
# export AWP_LLM_BASE_URL="https://api.openai.com/v1"
```

API Key 永不写入代码、Trace、数据库、工作流 JSON。
`ProviderConfig.to_safe_dict()` 排除所有敏感值。

## 测试默认使用 Fake Adapter

所有测试使用 `FakeLlmAdapter`、`FakeToolRunner`、`FakeDirectorV2Adapter`、`FakeWriterV2Adapter` 等。

测试不需要 API Key，不需要网络连接，不需要外部服务。

## 发现敏感信息时

如果在仓库中发现真实密钥或隐私数据：

1. **不要**在公开 issue、commit message、README、handoff 中回显真实密钥
2. **不要**把真实密钥写入 `.env.example`
3. 立即报告受影响文件的相对路径
4. 该密钥需要立即在提供商侧轮换
5. 先从当前工作树移除，再由项目所有者决定是否需要重写 Git 历史

## 公开 Issue

- 不要在公开 issue 中粘贴密钥
- 不要在公开 issue 中粘贴完整隐私数据
- 报告安全问题时，请使用私密渠道
