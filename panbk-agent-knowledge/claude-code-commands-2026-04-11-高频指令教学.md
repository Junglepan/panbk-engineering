# Claude Code 高频指令教学（官方文档整理，2026-04-11）

官方参考：
- https://code.claude.com/docs/en/commands
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/slash-commands

## 一、先记住这 10 个高频命令

1. `/agents`
- 用来干嘛：管理子代理（创建/编辑/删除/查看运行状态），把探索和执行拆开。
- 工作价值：减少主对话上下文污染，适合并行处理复杂任务。
- 示例：先用只读 agent 做代码检索，再回主会话落地修改。

2. `/plan [description]`
- 用来干嘛：进入计划模式，先出步骤再执行。
- 工作价值：减少返工，适合中大型改动。
- 示例：`/plan refactor auth module and keep API compatible`

3. `/permissions`
- 用来干嘛：管理工具权限（allow/ask/deny）。
- 工作价值：让自动化更安全，避免误操作。
- 示例：把高风险工具设为 ask，常用只读工具设为 allow。

4. `/compact [instructions]`
- 用来干嘛：压缩历史上下文，保留重点继续工作。
- 工作价值：长会话稳定性更好，降低跑偏概率。
- 示例：`/compact keep decisions, changed files, and pending risks`

5. `/clear`
- 用来干嘛：清空当前对话上下文（别名 `/reset`、`/new`）。
- 工作价值：当会话已经偏题或噪声太大时快速重启。

6. `/diff`
- 用来干嘛：查看未提交改动与每轮改动差异。
- 工作价值：提交前复核非常高效，避免漏改和误改。

7. `/model [model]` + `/effort [low|medium|high|max|auto]`
- 用来干嘛：切换模型与推理强度。
- 工作价值：在质量、速度、成本之间动态平衡。
- 示例：探索阶段 `low/medium`，复杂设计或疑难排错升到 `high`。

8. `/context`
- 用来干嘛：可视化上下文占用。
- 工作价值：帮助判断何时需要 compact、拆任务、改用 agent。

9. `/tasks`
- 用来干嘛：查看和管理后台任务。
- 工作价值：多任务并行时不丢进度。

10. `/help`
- 用来干嘛：查看当前环境可用命令。
- 工作价值：不同平台/套餐命令差异时最快定位能力边界。

## 二、工作中的典型用法（可直接照搬）

### 场景 A：接手陌生仓库
1. `/help` 看能力
2. `/permissions` 先设安全边界
3. `/agents` 配置只读探索 agent
4. `/plan` 产出分步计划
5. `/diff` 复核改动

### 场景 B：长链路需求开发
1. 先 `/plan`
2. 中途定期 `/compact`
3. 并行任务放到 `/agents` 或后台 `/tasks`
4. 提交前 `/diff` + 运行测试

### 场景 C：成本和速度压测期
1. 默认中等模型与 effort
2. 常规任务保持 `medium`
3. 卡点才升 `high`
4. 通过 `/context` 判断是否拆会话而不是盲目升 effort

## 三、关于 `/agents` 的重点说明（你提到的命令）

根据官方文档，`/agents` 是子代理管理入口，核心价值是“分治 + 隔离上下文”：
- 让探索任务在独立上下文中完成，只把结论回传主会话
- 可以限制子代理工具权限（例如只读）
- 支持按项目或个人范围复用 agent 配置

适合：
- 大仓库检索
- 多模块并行排查
- 需要严格权限隔离的协作流程

## 四、你可以直接执行的一套日常流程

1. 每次新任务：`/plan`
2. 任务中后期：`/compact`（保留决策、改动文件、风险）
3. 大任务拆分：`/agents`
4. 提交前检查：`/diff`
5. 资源管理：`/model`、`/effort`、`/context`

一句话：把 Claude Code 当工程系统来用，而不是只当聊天窗口。命令组合优先级通常是：
`/plan -> /agents -> /compact -> /diff`。
