# migrate-to-codex 官方思路总结

日期：2026-05-15  
来源：`/Users/panbk/.codex/skills/migrate-to-codex`

## 一句话

`migrate-to-codex` 的核心不是“把 Claude 文件直接复制成 Codex 文件”，而是“先扫描，再转换，再标注风险，再验证目标，最后处理人工复核项”的迁移闭环。

## 核心原则

1. 先盘点再写入，不靠猜。
2. 能自动映射的就自动映射，不能等价的就明确标注。
3. 生成物和人工复核项要分开。
4. 迁移后必须验证目标是否真的可用。
5. 不要假装 1:1 等价，尤其是 hooks、权限、subagent、slash command、插件。

## 执行闭环

官方思路基本是：

1. `--scan-only` 先看源目录里有什么。
2. `--plan` / `--doctor` 先看迁移计划和风险。
3. `--dry-run` 先模拟写入。
4. 真实写入 Codex 目标文件。
5. 读取迁移报告，修复 `manual_fix_required` 项。
6. `--validate-target` 检查目标格式和基本可用性。
7. 必要时再跑一轮。

这意味着迁移不是单次动作，而是一个“生成 -> 复核 -> 校验 -> 再生成”的循环。

## 迁移顺序

官方转换顺序大致是：

1. Instructions
2. Plugins 报告
3. Hooks
4. Skills / Slash commands
5. Config / MCP
6. Subagents

这个顺序有一个隐含前提：先处理最基础的行为说明，再处理能力面和运行时配置，最后处理角色定义。

## 最重要的差异边界

以下内容不是简单 copy 的对象，必须人工复核：

- slash command 的 runtime 参数展开
- hooks 的生命周期和 matcher 语义
- permissionMode 到 sandbox 的映射
- subagent 的 model / effort / tools / skills 语义
- plugin tree 和 marketplace
- MCP header / env / transport 的细节

只要这些地方出现“看起来能写进去”，都不等于“语义已经等价”。

## 可以直接复用到同步规范里的做法

1. 每次同步先生成计划，不直接写。
2. 每个迁移项都要有状态，至少区分 `added`、`check`、`not_added`。
3. 任何语义有损的地方都写入报告或目标文件里的 manual note。
4. 同步完成后必须做一次验证，而不是只看 UI 成功提示。
5. 用户看到的“可同步”不应等于“已经完全安全”。

## 对当前项目的启示

如果 `ClaudeCodex-Together` 要继续靠近官方 `migrate-to-codex`，优先级应该是：

1. 统一目标路径和文件格式。
2. 把 warning 从 UI 结果升级成可保存的 report。
3. 把 MCP / hooks / subagent 这些差异大的 surface 分层做出来。
4. 给同步结果增加验证层。

## 最简结论

官方 `migrate-to-codex` 的价值在于把“迁移”拆成了可检查、可验证、可回滚思考的步骤，而不是把转换做成一个黑盒。

