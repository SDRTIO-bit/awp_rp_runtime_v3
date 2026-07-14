---
name: single-chapter
description: 单章小说操作纪律。
---

未规划时只调用 plan_chapter；确认细纲存在后才调用 write_chapter。一次只处理一章。生成失败、正文为空或状态 rejected 时，明确报告并停止。
