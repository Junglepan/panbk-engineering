# Superpowers 技术总览（面向 Codex/Claude Code）

## 1. 它本质上是什么
`obra/superpowers` 不是一个“功能型插件”集合，而是一个“流程约束框架”：

- 用一组 `skills/*/SKILL.md` 把开发流程标准化
- 用启动注入（hook 或 skill discovery）让模型优先执行流程，而不是直接写代码
- 重点在“行为塑形”，而不是“提供新 API”

一句话：它把“怎么做工程”编码成可触发、可复用、可测试的技能系统。

## 2. 核心工作流（默认主线）
仓库 README 给出的主流程是：

1. `brainstorming`：先澄清需求与方案  
2. `using-git-worktrees`：隔离工作区  
3. `writing-plans`：写细粒度实现计划  
4. `subagent-driven-development` 或 `executing-plans`：按计划执行  
5. `test-driven-development`：红绿重构（RED-GREEN-REFACTOR）  
6. `requesting-code-review`：中间检查  
7. `finishing-a-development-branch`：收尾与合入决策

这套流程的目标是把“拍脑袋编码”变成“先设计、再计划、再验证”的流水线。

## 3. 技术实现机制
### 3.1 Skill 作为最小执行单元
- 每个能力都在 `skills/<name>/SKILL.md`
- `SKILL.md` 顶部 frontmatter 的 `name` 与 `description` 决定触发语义
- 描述通常是“何时必须触发”的条件，而不是功能介绍

### 3.2 启动时行为注入
- 在 Claude 插件侧，`hooks/hooks.json` 注册 `SessionStart` 事件
- `hooks/session-start` 会把 `using-superpowers` 的全文注入上下文
- `using-superpowers` 规则非常强：要求“只要有 1% 可能匹配 skill，就先调用 skill”

### 3.3 Codex 的接入方式（你现在用的是这个）
- 通过软链接把技能目录挂到 `~/.agents/skills/superpowers`
- Codex 启动后原生发现 skills 并按任务匹配触发
- 关键路径是：
  `~/.agents/skills/superpowers -> ~/.codex/superpowers/skills`

## 4. 关键技能分层
从仓库当前技能看，可分四层：

- 流程入口：`using-superpowers`, `brainstorming`
- 实施编排：`writing-plans`, `executing-plans`, `subagent-driven-development`, `dispatching-parallel-agents`
- 质量保障：`test-driven-development`, `systematic-debugging`, `verification-before-completion`, `requesting-code-review`, `receiving-code-review`
- 交付收尾：`finishing-a-development-branch`, `using-git-worktrees`

这意味着它覆盖了“需求->实现->验证->合并”的完整闭环。

## 5. 与普通提示词配置的差异
相较仅使用 `CLAUDE.md` / `AGENTS.md`，superpowers 的差异在于：

- 粒度更细：每个 skill 管一个动作场景
- 触发更自动：依赖 description 条件匹配，而不是每次手写提示
- 约束更硬：大量 `MUST`、`HARD-GATE`、前置检查
- 可测试：仓库自带 `tests/` 脚本验证技能行为

## 6. 工程价值
### 优点
- 降低“直接开写导致返工”的概率
- 明显强化 TDD、根因定位、完成前验证
- 对多人协作、长任务、并行子代理场景更稳定

### 成本
- 前期交互变长（先问、先设计、先计划）
- 简单任务可能显得“流程过重”
- 若与你团队节奏不一致，需要做本地裁剪

## 7. 在你当前项目的落地建议
你项目现在已经有项目级配置（`CLAUDE.md` + `.claude/rules`）。建议采用“轻量吸收 superpowers”而不是全量照搬：

1. 保留主干流程：Design -> Plan -> Implement -> Verify
2. 对复杂任务启用 TDD 与阶段评审；小任务允许直改
3. 将“必须验证后再宣称完成”设为硬规则
4. 继续把规则拆在 `.claude/rules/`，避免单文件过长

## 8. 你已完成的安装状态（本机）
已按官方 Codex 安装文档完成：

- 克隆：`~/.codex/superpowers`
- 链接：`~/.agents/skills/superpowers`

重启 Codex 后即可让技能发现生效。

## 9. 我对它的技术判断
superpowers 的本质不是“增强模型能力”，而是“增强工程流程纪律”。  
对个人/团队最有价值的部分通常是：

- `brainstorming`（防止错做）
- `writing-plans`（任务可执行）
- `test-driven-development` + `verification-before-completion`（质量闭环）

如果你把这四块真正用起来，收益通常已覆盖 80%。

