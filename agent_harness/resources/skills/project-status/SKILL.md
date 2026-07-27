---
name: project-status
description: 先检查当前小说项目状态再操作。
---

对章节请求先调用 project_status，每次会话开始先调用它获得总览——章节计划数、已生成数、待确认数。再调用 read_authoring_context 了解作者素材和计划状态。已有章节正文用 read_chapter 读取，不要读 output/ 下的文件。只使用当前项目，不能询问或猜测其他项目的数据。
