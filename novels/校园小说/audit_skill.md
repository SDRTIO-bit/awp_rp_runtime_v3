# Novel Audit Skill — 校园小说审计层

## 职责

设计层负责故事方向；执行层为 Architect → Director → Writer → Quality → Ledger；本文件只负责在两者之间写轻量章节契约、执行管线、审读成稿和做最小修复。

## 每章流程

1. 读 `project.json`、`story_bible.md`、`world.md`、`outline.md` 与 `guidance/WRITING_STANDARD.md`。
2. 在 `outline.md` 维护本章的开篇钩子、冲突、转折、结尾钩子。
3. 写 `guidance/chapter_NN.md`，控制在 250 汉字以内，只给 Writer 五件事：校园事件、双方想要什么、一次对话转折、关系后果、最多三条事实禁令。
4. 运行完整管线：

```powershell
$env:PYTHONPATH = "."
python -u scripts/novel_cli.py seed "novels\校园小说"
python -u scripts/novel_cli.py plan "novels\校园小说" N
python -u scripts/novel_cli.py write "novels\校园小说" N --stream
```

5. 审读 `output/chapter_NN.md`。只有确实伤害阅读的地方才做小修；不为追求“审稿格式”重写整章。

## Writer 引导边界

不要把审稿清单、禁词长表、行数预算、动作分镜、物件溯源表、示例台词直接塞给 Writer。它们会把正文变成逐项执行的分镜。Writer 的正文风格以 `reference_benchmark.txt` 为准，章节引导以场景与人物选择为主。

## 成稿审读

- 关系链：本章结束后，人物是否多了一项不能当作没发生的任务、知情、误解或选择？
- 角色底线：陈默是否把秘密当笑料；女主是否为了推进而失去体面或主动性；竞争者是否被写成工具人？
- 对话密度：正文是否由要求→抵抗→更高代价→决定推动，而非连续短句动作或训练流程？
- 败犬独特性：本章的失败是否属于这个人物，而不是通用的失恋哭戏？
- 连续性：新物件、录音、名单、节目单和时间是否有明确来源；结尾是否避开最近两章的同类钩子？

## 修复原则

只修可定位的问题：删除旁白解释、合并机械短句、补一条有立场的配角台词、让失败先发生再让合作成功。若问题来自章节目标本身，先改下一章大纲，不在正文里硬塞补丁。
