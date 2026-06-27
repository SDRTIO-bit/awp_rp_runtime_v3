# 参考文档

## 原始架构记录

本目录包含项目的原始架构记录文档：

- [RP ComfyUI 双主Agent、记忆与动态子Agent 架构记录 v0.1](RP_ComfyUI_双主Agent_记忆与动态子Agent_架构记录_v0.1.md)

  **版本：** v0.1（讨论归档 / 后续开发指引）
  **日期：** 2026-06-27
  **定位：** 记录当前已经形成的系统级共识，避免"让世界活起来"的关键想法在后续开发中丢失。

## 架构文档体系

当前公开仓库的可审计架构依据：

| 文档 | 位置 | 内容 |
|------|------|------|
| 系统总览 | [docs/architecture/overview-v1.md](../architecture/overview-v1.md) | 项目目标、双主 Agent、确定性状态、三层记忆 |
| 回合生命周期 | [docs/architecture/turn-lifecycle-v1.md](../architecture/turn-lifecycle-v1.md) | 完整主链、Wave A/B、D6 位置、retry/idempotency |
| Agent 权限边界 | [docs/architecture/agent-boundaries-v1.md](../architecture/agent-boundaries-v1.md) | D1～D6 职责、输入、输出、工具、降级 |
| 记忆治理 | [docs/architecture/memory-governance-v1.md](../architecture/memory-governance-v1.md) | 三层记忆、accepted-only、D6 触发、幂等 |
| 冲突治理 | [docs/architecture/conflict-governance-v1.md](../architecture/conflict-governance-v1.md) | 证据优先级、玩家代理权、事实泄漏防护 |
| Alpha 状态 | [docs/alpha-status-v0.1.md](../alpha-status-v0.1.md) | 已完成能力、已知限制、下一阶段 |

## Handoff 文档

每个开发阶段的验收报告：

| 阶段 | 文档 |
|------|------|
| D1 History/Recall | [docs/handoffs/D1-history-recall-agent-v1.md](../handoffs/D1-history-recall-agent-v1.md) |
| D2 Opportunity | [docs/handoffs/D2-opportunity-agent-v1.md](../handoffs/D2-opportunity-agent-v1.md) |
| D3 World-Life | [docs/handoffs/D3-world-life-agent-v1.md](../handoffs/D3-world-life-agent-v1.md) |
| D4 Emotion/Relationship | [docs/handoffs/D4-emotion-relationship-agent-v1.md](../handoffs/D4-emotion-relationship-agent-v1.md) |
| D5 Continuity | [docs/handoffs/D5-continuity-agent-v1.md](../handoffs/D5-continuity-agent-v1.md) |
| D6 Memory Curator | [docs/handoffs/D6-memory-curator-agent-v1.md](../handoffs/D6-memory-curator-agent-v1.md) |
| D-Integration | [docs/handoffs/D-integration-dynamic-agent-conflict-governance-v1.md](../handoffs/D-integration-dynamic-agent-conflict-governance-v1.md) |
| Public Alpha | [docs/handoffs/public-alpha-release-hygiene-v1.md](../handoffs/public-alpha-release-hygiene-v1.md) |
