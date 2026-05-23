---
title: Claude Code 核心设计工程剖析
date: 2026-05-21
tags: [claude-code, agent, 架构]
status: complete
---

# Claude Code 2.1.88 核心设计工程剖析

> 研究对象：`/Users/panbk/claude-code-source/claude-code-sourcemap`  
> 版本来源：公开 npm 包 `@anthropic-ai/claude-code@2.1.88` 的 source map 还原源码。  
> 注意：该仓库是非官方还原结构，不等同于原始内部仓库；本文只基于本地还原源码做工程分析。

## 1. 一句话结论

Claude Code 的核心不是“一个会调用工具的聊天程序”，而是一个以模型为规划器、以工具契约为执行边界、以权限系统为安全仲裁、以会话日志和上下文压缩为长期状态层的终端软件工程代理。它把 TUI、SDK/headless、MCP、插件、技能、子代理、后台任务和远程控制都统一到同一条执行管线里：用户输入被归一成消息，模型产生 `tool_use`，工具执行层验证、授权、运行并产出 `tool_result`，再把结果回灌给模型，直到自然停止、被 hook 截断、触发压缩或达到回合限制。

## 2. 源码地图

关键目录如下：

- `restored-src/src/main.tsx`：完整 CLI 主入口，负责初始化配置、鉴权、策略、模型、MCP、插件、技能、权限模式、会话恢复和 TUI 启动。
- `restored-src/src/entrypoints/cli.tsx`：轻量 bootstrap 入口，先处理 `--version`、Chrome/MCP/native host、daemon、background、remote-control 等快路径，再懒加载主 CLI。
- `restored-src/src/screens/REPL.tsx`：交互式终端应用主体。基于 React/Ink 组织消息列表、输入框、权限弹窗、MCP elicitation、后台任务、队列、通知、IDE/remote/bridge 等 UI。
- `restored-src/src/QueryEngine.ts`：SDK/headless 场景的会话引擎，持有消息、文件缓存、权限拒绝、usage、转录记录，并调用 `query()`。
- `restored-src/src/query.ts`：模型主循环。处理 API 流、工具调用、自动压缩、stop hooks、错误恢复、max output tokens 恢复、streaming fallback、工具结果预算。
- `restored-src/src/Tool.ts` 与 `restored-src/src/tools.ts`：工具抽象和工具池组装中心。
- `restored-src/src/services/tools/*`：工具执行编排层，包括并发调度、权限和 hook 包装、结果持久化、遥测、错误映射。
- `restored-src/src/utils/permissions/*`：权限规则、权限模式、auto 模式分类器、dangerous rule 清理、权限持久化。
- `restored-src/src/utils/sandbox/sandbox-adapter.ts`：OS 沙箱运行时适配，把 Claude Code 的 settings/permissions 转成 sandbox-runtime 配置。
- `restored-src/src/services/mcp/*`：MCP 客户端、连接管理、OAuth、资源、工具桥接。
- `restored-src/src/tools/AgentTool/*` 与 `restored-src/src/tasks/*`：子代理、后台任务、远程任务、队友/多代理机制。
- `restored-src/src/services/compact/*`：自动压缩、手动压缩、会话记忆压缩、压缩后恢复附件。
- `restored-src/src/skills/*`、`restored-src/src/plugins/*`、`restored-src/src/utils/plugins/*`：技能和插件加载、缓存、marketplace、命令/agent/hook/MCP 扩展。
- `restored-src/src/utils/sessionStorage.ts`：JSONL 会话日志、子代理 transcript、resume、metadata、内容替换记录。

## 3. 参考目录后的补充阅读框架

你给出的目录更像一份“源码架构导览”。对照后，可以把本文的阅读框架整理成三层：

1. **全景层**：项目概览、技术栈、目录结构、启动流程。
2. **内核层**：Agent Loop、工具调用系统、流式执行引擎、Thinking、Task、Compact。
3. **扩展层**：Skill、Hooks、Feature Flag、MCP/插件、关键文件速查。

现有内容已经覆盖大部分内核，但原来更偏工程剖析叙事；补充后更适合作为后续源码学习和知识库索引使用。

### 3.1 目录映射表

| 参考目录项 | 本文对应章节 | 是否需要补充 |
|---|---|---|
| 项目概览 | 一句话结论、源码地图 | 已覆盖 |
| 技术栈全景 | 新增“技术栈全景” | 补充 |
| 目录结构详解 | 新增“目录结构详解” | 补充 |
| 启动流程 | 启动设计 | 已覆盖，保留 |
| 核心：Agent Loop | 模型循环 | 已覆盖 |
| 工具调用系统 | 工具抽象、工具池、工具执行层 | 已覆盖 |
| 流式执行引擎 | 并发执行 | 已覆盖 |
| Thinking 推理模式 | 新增“Thinking 推理模式” | 补充 |
| Task 系统 | 子代理与后台任务 | 已覆盖，补充速览 |
| Compact 对话压缩 | 上下文压缩 | 已覆盖 |
| Skill 系统 | 插件与技能 | 已覆盖 |
| Hooks 生命周期扩展 | Hook 系统 | 已覆盖，补充生命周期表 |
| 高级特性与 Feature Flag | 新增“Feature Flag” | 补充 |
| 关键文件速查表 | 推荐阅读路径 | 已覆盖，补充速查表 |
| 架构亮点与设计哲学 | 设计亮点、最终评价 | 已覆盖 |

## 4. 技术栈全景

从还原源码看，Claude Code 是一个 Node/Bun 打包的 TypeScript 终端应用，前端是 React/Ink，后端执行层混合了 Node 进程、shell、MCP transport、原生模块和远程服务。

| 层级 | 技术/机制 | 作用 |
|---|---|---|
| 运行时 | Node.js 18+、Bun bundle feature gate | CLI 分发、动态 import、构建期裁剪、启动快路径 |
| 语言 | TypeScript、Zod | 类型约束、工具输入 schema、配置校验、frontmatter 校验 |
| 终端 UI | React、Ink、自研 layout/termio | REPL、消息列表、权限弹窗、任务面板、通知、快捷键 |
| 模型 API | Anthropic SDK beta messages、streaming | 主模型采样、thinking、tool_use/tool_result、prompt cache、fallback |
| 工具执行 | Shell 子进程、文件系统 API、MCP SDK、LSP | Bash、文件读写、搜索、外部服务、编辑器/语言服务集成 |
| 扩展 | MCP、plugins、skills、slash commands、hooks | 外部能力接入、用户/团队自定义工作流 |
| 状态 | AppState store、JSONL transcript、settings、memory dir | UI 状态、会话恢复、配置、长期偏好 |
| 安全 | permission rules、auto classifier、sandbox-runtime | 权限仲裁、自动模式安全判断、OS 级文件/网络隔离 |
| 可观测性 | analytics、OTel、debug logs、cost tracker | 工具调用、权限决策、API 成本、cache break、错误诊断 |

这个技术栈的关键不是“用了哪些库”，而是这些库被组织成了一个 Agent runtime：React/Ink 负责交互，query loop 负责模型协议，Tool ABI 负责行动边界，权限/沙箱负责风险控制，JSONL 和 compact 负责长会话生存能力。

## 5. 目录结构详解

源码目录可以按职责重新分组理解：

| 目录 | 职责 | 学习重点 |
|---|---|---|
| `entrypoints/`、`main.tsx` | CLI 入口与启动分流 | 快路径、动态 import、初始化顺序 |
| `screens/`、`components/`、`ink/` | 终端 UI | REPL、权限弹窗、消息渲染、任务面板 |
| `query.ts`、`QueryEngine.ts`、`query/` | Agent Loop | 多轮循环、工具结果回灌、错误恢复 |
| `tools/`、`Tool.ts`、`tools.ts` | 工具定义与工具池 | Tool ABI、内置工具、MCP 工具合并 |
| `services/tools/` | 工具执行运行时 | schema 校验、hooks、权限、并发、遥测 |
| `utils/permissions/`、`hooks/toolPermission/` | 权限系统 | allow/deny/ask、auto mode、交互权限 |
| `utils/sandbox/` | 沙箱适配 | 文件/网络隔离、settings 防护、git escape 防护 |
| `services/api/` | 模型 API 层 | betas、streaming、fallback、prompt cache |
| `services/compact/` | 上下文压缩 | auto compact、manual compact、session memory、post-compact restore |
| `services/mcp/` | MCP 客户端 | transport、OAuth、tools/resources/prompts 桥接 |
| `skills/`、`plugins/`、`utils/plugins/` | 扩展系统 | 技能、插件、marketplace、frontmatter、hooks |
| `tasks/`、`tools/AgentTool/` | 子代理与后台任务 | agent lifecycle、task progress、worktree/remote isolation |
| `state/`、`utils/sessionStorage.ts` | 运行状态与持久化 | AppState、JSONL、resume、子代理 transcript |

一个实用读法是：先读 `entrypoints -> REPL/QueryEngine -> query -> Tool -> toolExecution` 这条主链，再回头读权限、compact、MCP、AgentTool 等横切系统。


## 6. 启动设计：快路径优先，重依赖懒加载

`entrypoints/cli.tsx` 是启动性能优化的第一层。它在加载完整 CLI 前先处理低成本路径：

- `--version` 直接输出版本，几乎零依赖加载。
- Chrome native host、Claude-in-Chrome MCP、computer-use MCP 等特殊进程走独立入口。
- daemon、background session、remote-control、templates、runner 这类子命令按需动态 import。
- 对远程环境设置 `NODE_OPTIONS=--max-old-space-size=8192`，说明它把子进程和工具执行也纳入资源治理。

`main.tsx` 是第二层。文件开头就能看到启动 profiler、MDM 设置读取、macOS keychain prefetch 等顶层副作用，其目的很明确：把必需但慢的 IO 和后续模块加载并行化。主入口之后继续做配置、策略限制、GrowthBook gate、模型字符串、MCP 配置、插件、技能、LSP、权限模式、会话恢复等初始化。

这个设计的核心取舍是：CLI 用户对冷启动很敏感，因此把“常用但不必立即加载”的能力尽量拆到 feature gate 和动态 import 后面。代价是入口文件非常复杂，且存在大量懒加载与循环依赖规避代码。

## 7. 主执行链路

交互式路径大致如下：

1. `screens/REPL.tsx` 接收输入、粘贴内容、IDE selection、命令队列、远程消息或后台任务通知。
2. `processUserInput()` 解析 slash command、图片/附件、prompt hooks、技能/命令展开等，决定是否需要发起模型查询。
3. REPL 或 `QueryEngine.submitMessage()` 构造 `ToolUseContext`，其中包含工具池、命令、MCP clients、权限上下文、文件缓存、AppState、abort controller、hook 回调等。
4. `fetchSystemPromptParts()` 组装 system prompt、user context、system context；`QueryEngine` 还会注入 memory、coordinator context、custom/append prompt。
5. `query()` 进入模型循环：调用 API，流式接收 assistant 消息和 `tool_use`，执行工具，把 `tool_result` 作为 user message 追加，再继续下一轮。
6. 循环结束后写 transcript、更新 usage/cost、触发 stop hooks 或 session end hooks。

headless/SDK 路径的关键是 `QueryEngine.ts`。它把 REPL 中分散的会话状态抽成类：一个 `QueryEngine` 对应一个 conversation，多次 `submitMessage()` 共享消息、文件缓存、usage 和权限拒绝列表。这解释了为什么 Claude Code 能同时支持终端 TUI、`-p`/SDK、side question、background agent 等不同入口。

## 8. 模型循环：`query.ts` 是系统的心脏

`query()` 是一个 async generator，输出请求开始事件、assistant/user/system/progress 消息、工具摘要、tombstone 等。它的设计重点不是简单调用模型，而是把异常和长任务情况都纳入状态机：

- 保存 loop state：`messages`、`toolUseContext`、`autoCompactTracking`、`maxOutputTokensRecoveryCount`、`pendingToolUseSummary`、`stopHookActive`、`turnCount`、`transition`。
- 在每轮前后计算 token 状态，必要时自动 compact。
- 支持 streaming tool execution：模型流出工具块时就可以启动工具，减少等待。
- 保证 tool_use/tool_result 配对。流式 fallback、用户中断、工具并发错误都会生成 synthetic tool_result，避免 API 层看到悬空 tool_use。
- 对 prompt too long、media size、max_output_tokens、streaming broken 等情况走不同恢复路径。
- stop hooks 可以阻止继续，或者插入阻断消息后让模型继续解释。
- 工具结果会走预算控制，过大结果可落盘，只给模型预览和路径。

这是一种典型的“agent loop as protocol repair layer”设计：模型和工具之间的协议必须始终合法，即使底层 API、流式响应、用户中断或工具报错。

## 9. API 请求层：缓存、beta、fallback 和工具 schema

`services/api/claude.ts` 是模型 API 的封装层。它做的事情包括：

- 把内部 `Tool` 转为 API tool schema。
- 处理 prompt cache：`splitSysPromptPrefix()`、cache scope、1h cache header、cache break 诊断。
- 注入 betas：thinking、effort、structured outputs、tool search、context management、task budgets 等。
- 根据工具搜索策略把部分工具标记为 `defer_loading`，降低初始 schema 体积。
- 维护 usage/cost、quota、request id、diagnostic logs。
- 通过 `withRetry()` 做重试和模型 fallback。
- streaming 出问题时可以退到 non-streaming fallback，并且做独立 telemetry。

这里体现了一个重要设计：系统 prompt 和工具 schema 被当作缓存资产来管理。`tools.ts` 里 `assembleToolPool()` 甚至会先排序内置工具，再拼接排序后的 MCP 工具，避免 MCP 工具插入内置工具区间导致 prompt cache key 抖动。

## 10. Thinking 推理模式

Thinking 不是一个独立工具，而是模型 API 请求和消息规范的一部分。相关逻辑分布在 `services/api/claude.ts`、`utils/thinking.ts`、`query.ts` 和系统提示构造中。

关键点：

- 模型是否支持 thinking 由模型能力、beta header、用户配置和默认策略共同决定。
- `query.ts` 明确维护 thinking block 的合法性：带 thinking 或 redacted_thinking 的消息必须处在允许 thinking 的请求轨迹中，且要跟随对应 assistant trajectory 保存。
- streaming、fallback、compact 和 tool_result 配对都要避免破坏 thinking block 的上下文约束。
- thinking 与 max output tokens、effort、adaptive thinking、structured outputs 等能力会互相影响。

工程意义：Thinking 是“模型内部推理预算和轨迹”的协议层能力，不应该被当成普通文本处理。任何上下文裁剪、压缩、重放、fallback 都必须尊重它的消息结构约束，否则会产生 API 层错误或缓存失效。


## 11. 工具抽象：一个强契约对象

`Tool.ts` 中的 `Tool` 接口非常大，但这不是偶然。工具既是模型可见能力，也是安全对象、UI 对象、协议对象和 telemetry 对象。一个工具要提供：

- `inputSchema` / `inputJSONSchema`：模型输入校验。
- `call()`：实际执行。
- `validateInput()`：语义校验。
- `checkPermissions()`：工具自身权限判断。
- `isConcurrencySafe()`、`isReadOnly()`、`isDestructive()`：执行调度和风险判断。
- `interruptBehavior()`：用户新输入时取消还是阻塞。
- `mapToolResultToToolResultBlockParam()`：把内部结果映射成 API `tool_result`。
- `renderToolUseMessage()`、`renderToolResultMessage()`、progress/group render：TUI 展示。
- `toAutoClassifierInput()`：auto mode 安全分类器看到的紧凑动作表达。
- `maxResultSizeChars`：结果过大时的落盘策略。
- `mcpInfo`、`shouldDefer`、`alwaysLoad`：MCP 和 ToolSearch 集成。

`buildTool()` 给大多数安全相关默认值采用保守策略：默认不并发安全、默认非只读、默认不是 destructive、默认跳过 classifier 输入。也就是说，真正需要放宽的工具必须显式声明。

## 12. 工具池组装：内置工具、MCP 工具、权限过滤

`tools.ts` 是工具池的单一入口。它先定义内置工具，如 Agent、Bash、FileRead/Edit/Write、Glob/Grep、WebFetch/WebSearch、Todo、Skill、Plan、Task、MCP Resource 等，再根据环境变量、feature gate、用户类型、REPL 模式、LSP、PowerShell、worktree、tool search 等动态增减。

关键机制：

- `getTools(permissionContext)`：只返回当前权限上下文下可见的内置工具。
- `filterToolsByDenyRules()`：被 blanket deny 的工具在模型看到前就移除，而不是等调用时再拒绝。
- `assembleToolPool(permissionContext, mcpTools)`：合并内置和 MCP 工具，内置优先，按名称排序保证缓存稳定。
- simple mode 只暴露 Bash/Read/Edit，REPL 模式会隐藏底层 primitive tools，让 REPL wrapper 统一代理。

这说明 Claude Code 把“模型可见的动作空间”当成安全边界的一部分。不给模型看，比让模型看了再拒绝更省 token，也更少诱发无效行动。

## 13. 工具执行层：验证、hook、权限、执行、结果、遥测

`services/tools/toolExecution.ts` 是每次工具调用的完整管线：

1. 通过 zod 校验模型输入。
2. 调用工具级 `validateInput()`。
3. Bash 会提前启动 speculative classifier，让分类器和 hooks/权限 UI 并行。
4. 运行 `PreToolUse` hooks，可产生消息、修改输入、给出权限结果、阻止继续。
5. 通过 `resolveHookPermissionDecision()` 和 `canUseTool()` 得到最终权限决定。
6. 若拒绝，生成 `tool_result is_error`，必要时触发 PermissionDenied hooks。
7. 若允许，调用 `tool.call()`，并转发 progress。
8. 把结果映射成 API tool_result，过大结果经 `toolResultStorage` 持久化。
9. 运行 `PostToolUse` hooks，MCP 工具允许 hook 修改 MCP 输出。
10. 记录 OTel、Statsig/analytics、duration、tool_result_size、错误类型、MCP scope 等。

这个层次的价值是把所有工具的横切关注点集中化：任何新工具只要实现 `Tool` 契约，就自动获得权限、hooks、UI progress、结果预算、遥测和错误恢复。

## 14. 并发执行：只读/安全工具批量跑，写操作串行

工具编排有两套：

- `toolOrchestration.ts`：传统批处理。它把连续的 concurrency-safe 工具合成批次并发执行，非并发安全工具单独串行执行。
- `StreamingToolExecutor.ts`：流式工具执行。工具块一流出就入队，concurrency-safe 工具可以并发，非安全工具需要独占；结果按工具出现顺序缓冲输出。

`StreamingToolExecutor` 还处理三个难点：

- 兄弟 Bash 工具失败时中止同批工具，生成 synthetic error。
- 用户中断时按工具的 `interruptBehavior()` 决定取消还是阻塞。
- streaming fallback 时丢弃旧工具结果，避免旧 tool_use id 对应的新结果污染新一轮请求。

这是工程上很关键的优化：代理任务的实际耗时经常在 grep/read/list/test 上，安全并发能显著降低等待；但写文件、shell 修改、MCP side effect 必须保守串行。

## 15. 权限系统：模式、规则、hooks、分类器和提示

权限核心在 `utils/permissions/permissions.ts`、`permissionSetup.ts` 和 `hooks/useCanUseTool.tsx`。

权限来源包括：

- settings：user/project/local/policy 等来源的 allow/deny/ask。
- CLI 参数和 session 临时授权。
- 工具自身 `checkPermissions()`。
- PreToolUse / PermissionRequest hooks。
- 权限模式：default、acceptEdits、bypassPermissions、dontAsk、plan、auto 等。
- sandbox 条件下的 Bash 自动允许。
- auto mode 分类器。
- 交互式用户弹窗、bridge/channel permission callbacks、swarm/coordinator permission forwarding。

权限判断的典型顺序是：先处理硬 deny 和工具级安全检查，再看 allow/ask 规则、模式、sandbox、hooks，最后才进入交互或 auto 分类器。`useCanUseTool()` 把 headless 和交互 UI 分流：allow 直接返回，deny 直接生成拒绝，ask 则可能经过 coordinator/swarm 自动处理、Bash speculative classifier、再进入交互权限弹窗。

值得注意的安全设计：

- `permissionSetup.ts` 会识别 auto mode 下危险的 Bash/PowerShell/Agent allow 规则，如 `Bash(*)`、`python:*`、`node*`、`PowerShell(iex*)`、Agent 宽授权等。
- auto mode 对安全检查有“不可被分类器绕过”的分支，某些 safetyCheck 必须人工批准。
- PowerShell 默认不进入 auto classifier，除非专门 feature 打开。
- headless 或后台代理如果不能弹权限框，会先跑 PermissionRequest hooks，仍无法决策则自动拒绝。

## 16. 沙箱：权限规则的 OS 级补强

`utils/sandbox/sandbox-adapter.ts` 把 Claude Code settings 转为 `@anthropic-ai/sandbox-runtime` 配置。它覆盖网络、读写文件系统、ripgrep、Unix socket、本地绑定等。

关键设计点：

- `permissions.allow` 中的 `WebFetch(domain:...)` 会转成网络 allow domains。
- `FileEdit(path)`、`FileRead(path)` 规则会转成 allowWrite/denyWrite/denyRead。
- 当前目录和 Claude temp dir 默认可写，额外 `--add-dir` 目录也进入 allowWrite。
- settings 文件、managed settings drop-in、`.claude/skills` 被加入 denyWrite，防止模型通过修改自身配置或技能来提权。
- 针对 bare git repo escape 做了专门防护：命令后 scrub 可能被种下的 `HEAD`、`objects`、`refs`、`hooks`、`config`。
- sandbox 显式启用但不可用时会返回可展示原因，避免用户以为网络/文件限制已生效。

权限系统回答“这个工具调用是否应该被允许”，沙箱回答“即使允许，进程在 OS 层还能碰什么”。两者叠加才构成可执行代理的安全边界。

## 17. System Prompt 与上下文构造

`constants/prompts.ts` 是系统行为的主要来源。它分静态和动态部分，并定义 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY`，用于 prompt cache：边界前可跨用户/组织全局缓存，边界后包含用户/会话信息，不应全局缓存。

系统 prompt 内容覆盖：

- 软件工程任务行为规范。
- 工具使用和权限拒绝后的行为。
- hook 反馈的语义。
- 自动压缩和无限上下文说明。
- 输出风格、语言偏好、MCP instructions、memory、worktree、agent/team/coordinator 等动态部分。

`utils/queryContext.ts` 把 system prompt、user context、system context 的构造集中化，避免循环依赖，并保证 main loop 和 side question 尽量使用同样的 cache-safe prefix。

## 18. 用户输入处理：命令、附件、hooks 和技能入口

`utils/processUserInput/processUserInput.ts` 在模型查询前处理输入：

- prompt 输入立即显示，减少 UI 延迟。
- 解析 slash command 和 bridge-safe command。
- 处理图片、粘贴内容、IDE selection、引用。
- 执行 `UserPromptSubmit` hooks；hook 可以阻断、阻止继续、追加上下文或输出消息。
- slash command 可以返回 prompt、allowed tools、model、effort、next input。

这意味着 Claude Code 的“用户消息”不只是文本，它是一组可能包含本地命令结果、hook 附加上下文、图片、IDE 选区、技能展开、队列消息的结构化消息。

## 19. 记忆系统：文件化长期偏好，不替代项目事实

`memdir/memdir.ts` 构建 memory prompt。它的设计不是把所有历史写进一个大文件，而是：

- `MEMORY.md` 是索引，不是内容主体。
- 每条 memory 建议写到单独文件，有 frontmatter。
- memory 类型有封闭分类，强调不要保存可从当前代码/项目状态推导出来的事实。
- `MEMORY.md` 限制 200 行和 25KB，过长会截断并提示。
- memory 目录会在 prompt 构建时确保存在，避免模型浪费回合 mkdir/ls。

这体现出一个边界：memory 保存跨会话协作偏好和背景，不应该成为项目索引或临时计划。计划、任务、当前会话状态分别用 plan/task/transcript 机制承担。

## 20. 上下文压缩：多层降级而不是单一总结

`services/compact/*` 说明上下文管理是多层系统：

- `autoCompact.ts` 根据模型 context window、输出保留 token、阈值和 buffer 判断是否自动压缩。
- `compact.ts` 负责实际总结，去掉图片/文档大块，移除会被重新注入的附件，处理 prompt-too-long retry。
- `sessionMemoryCompact.ts` 可优先尝试把历史压成 session memory。
- `postCompactCleanup.ts` 清理压缩后状态。
- 压缩后会恢复关键文件、技能、计划、MCP/agent/tool delta 等附件，避免总结丢掉可执行上下文。

几个工程细节值得注意：

- 自动压缩有 consecutive failure circuit breaker，避免不可恢复超限时反复烧 API。
- compact 自身如果 prompt too long，会按 API round 丢弃旧组，并插入 synthetic marker。
- context collapse、reactive compact、history snip、session memory compact 之间有互斥和优先级，避免多套上下文机制互相打架。

## 21. MCP：外部能力统一成工具、命令和资源

`services/mcp/client.ts` 支持 stdio、SSE、HTTP stream、WebSocket、SDK control、Claude.ai proxy 等 transport。它把 MCP server 的 tools 转为 Claude Code `Tool`，resources 转为 List/Read MCP Resource 工具，prompts/commands 也能进入命令体系。

核心设计点：

- OAuth token 刷新、401/needs-auth 状态、auth cache。
- MCP tool timeout 默认很长，适合长任务服务器。
- MCP tool description 和 server instructions 有长度 cap，避免 OpenAPI 服务器把几十 KB 描述塞进 prompt。
- MCP 输出可以截断、二进制落盘、大输出提示。
- MCP error 的 `_meta` 会传给 SDK 消费者。
- agent definition 可以声明额外 MCP servers；内联定义的 agent-specific MCP 会在 agent 结束时清理，共享 server 不清理。

MCP 工具并没有绕过工具系统，而是完整进入同一个权限、hooks、结果预算、遥测、ToolSearch、UI 展示链路。

## 22. 插件与技能：扩展面被产品化

插件加载在 `utils/plugins/pluginLoader.ts`。插件目录可包含：

- `plugin.json` manifest。
- `commands/` 自定义 slash commands。
- `agents/` 自定义 agents。
- `hooks/` hook 配置。
- MCP server 或其他组件。

插件支持 marketplace、git/npm 缓存、版本化 cache、seed cache、zip cache、策略 blocklist/allowlist、managed plugin、inline session plugin。加载器会校验 manifest、路径、重复名、hooks schema，并收集错误。

技能加载在 `skills/loadSkillsDir.ts`。技能本质上也被建模为 command/tool 相关能力：frontmatter 可声明 description、when_to_use、allowed-tools、model、effort、hooks、fork context、agent、paths、shell 等。技能内容按需加载，系统 prompt 只估算/暴露 frontmatter，降低常驻 token。

这说明 Claude Code 把扩展能力分成两层：

- 插件是安装、版本、分发和管理单元。
- 技能/命令/agent/MCP/hook 是运行时能力单元。

## 23. 子代理与后台任务：独立上下文，统一任务框架

`AgentTool` 是代理能力的核心工具。它可以：

- 启动同步子代理。
- 启动后台本地 agent task。
- 通过 `isolation: worktree` 创建隔离 git worktree。
- 在特定构建中启动 remote agent。
- 在 agent swarms / teammate 模式下生成可寻址队友。
- 支持 fork subagent，共享父级 prompt cache。

`runAgent.ts` 会为子代理构造自己的 system prompt、tools、commands、MCP clients、permission context、transcript path 和 file cache。权限上有几个明确边界：

- agent 可用工具通过 agent definition、allowed tools 和权限规则解析。
- async agent 通常不能弹权限提示，因此 `shouldAvoidPermissionPrompts` 会让 ask 变 deny，除非 hook 能自动决策。
- agent-specific MCP server 可以附加到父上下文，但 plugin-only 策略会阻止用户控制 agent 私自加 MCP。

后台任务统一在 `tasks/*`。`LocalAgentTask` 记录 agentId、prompt、agentType、model、abortController、progress、messages、pendingMessages、retain/diskLoaded/evictAfter 等。`TaskOutputTool`、`SendMessageTool`、task notifications 等机制让主代理能查看和沟通后台任务。

## 24. 会话持久化：JSONL 是事实源

`utils/sessionStorage.ts` 把会话写到 `~/.claude/projects/<project>/<session>.jsonl`。它不仅保存用户和助手消息，也保存 attachment、system compact boundary、metadata、file history snapshot、content replacement、worktree state、agent transcript 等。

关键点：

- `isTranscriptMessage()` 明确定义哪些消息能进入 transcript；progress 是 UI-only，不应参与 parentUuid chain。
- 老版本 progress entry 会在加载时桥接，说明它兼容历史日志格式。
- transcript 读取有 50MB 上限，避免超大 JSONL OOM。
- 子代理 transcript 放在主 session 目录下的 `subagents/agent-<id>.jsonl`。
- session title、cost、metadata、worktree、plan slug 等围绕 transcript 做恢复。

这是一种事件日志式设计：运行时 AppState 可变，但长期可恢复状态以 JSONL transcript 和附属 metadata 为准。

## 25. UI 状态：React/Ink 不是薄壳

`screens/REPL.tsx` 很大，因为它是交互式产品本体，而不是简单 stdout 打印器。它协调：

- prompt input、vim mode、history、paste/reference 展开。
- virtual message list、transcript mode、搜索、滚动、message actions。
- permission dialog、sandbox permission、MCP elicitation、hook prompt dialog。
- background task panel、teammate view、coordinator task index。
- MCP connection manager、plugin notifications、LSP/IDE/Chrome/Desktop 提示。
- speculation/prompt suggestion、auto background session、remote/bridge/SSH/direct connect。
- cost/rate limit/deprecation/auto mode unavailable 等通知。

`state/AppStateStore.ts` 定义了大量产品状态，`state/store.ts` 则是一个很小的订阅式 store。复杂性不在 store 框架，而在状态域本身：模型循环、工具执行、权限 UI、后台任务和远程控制都要在同一终端界面内协调。

## 26. Hook 系统：用户/组织把执行链路插入点外置

Hook 出现在多个阶段：

- `UserPromptSubmit`
- `PreToolUse`
- `PermissionRequest`
- `PostToolUse`
- `PostToolUseFailure`
- `Stop`
- `PreCompact` / `PostCompact`
- `SessionStart` / `SessionEnd`

hook 的工程作用是把企业策略、自动格式化、审计、额外上下文、权限代理、阻断规则等从核心代码外置。风险是 hook 会变成另一个不可靠执行面，所以代码里有大量超时、输出截断、阻断消息、进度展示和错误降级。

## 27. Task 系统速览

Task 系统是把“长时间运行的副作用”从主对话里抽出来管理的框架。它不只服务 Agent，也服务 shell、remote、workflow、monitor 等后台能力。

| Task 类型 | 代表文件 | 作用 |
|---|---|---|
| `LocalAgentTask` | `tasks/LocalAgentTask/LocalAgentTask.tsx` | 本地后台子代理，记录进度、消息、结果、通知和停止控制 |
| `LocalShellTask` | `tasks/LocalShellTask/*` | 后台 shell 命令与 shell 生命周期管理 |
| `RemoteAgentTask` | `tasks/RemoteAgentTask/*` | 远程环境中的 Agent 任务，保留 session URL 和输出路径 |
| `DreamTask` | `tasks/DreamTask/*` | 特定实验/模式下的后台任务类型 |
| feature-gated tasks | `LocalWorkflowTask`、`MonitorMcpTask` | 工作流脚本、监控 MCP 等高级能力 |

Task 的关键设计是：主 Agent 不必一直阻塞等待长任务完成，而是通过任务状态、输出文件、通知消息、`TaskOutputTool`、`SendMessageTool` 等机制继续协作。这使得 Agent 可以同时处理前台推理和后台执行。

## 28. Hooks 生命周期扩展

Hooks 是把用户、团队、企业策略插入 Agent Loop 的生命周期机制。它们不是 UI 插件，而是执行链路上的控制点。

| Hook 阶段 | 触发时机 | 能做什么 |
|---|---|---|
| `UserPromptSubmit` | 用户输入进入模型前 | 阻断 prompt、追加上下文、写入 hook 附件 |
| `PreToolUse` | 工具权限判断和执行前 | 修改工具输入、阻断执行、提供权限结果、输出进度 |
| `PermissionRequest` | 工具需要 ask 时 | 自动允许/拒绝、持久化权限更新、headless 代理权限 |
| `PostToolUse` | 工具成功后 | 改写 MCP 输出、追加附件、审计结果 |
| `PostToolUseFailure` | 工具失败后 | 记录失败、追加诊断、触发恢复逻辑 |
| `Stop` | 模型自然停止或准备继续前 | 阻止继续、插入 stop summary、释放锁 |
| `PreCompact` / `PostCompact` | 对话压缩前后 | 保存上下文、恢复必要状态、做清理 |
| `SessionStart` / `SessionEnd` | 会话开始/结束 | 初始化环境、收尾审计、上传或通知 |

Hooks 的设计价值在于把“组织策略”和“项目习惯”从核心程序里外置；风险是 hook 本身也可能慢、失败或输出过大，因此执行层必须做超时、截断、进度显示和失败降级。

## 29. 高级特性与 Feature Flag

源码中大量使用 `feature('...')`、环境变量和 GrowthBook gate。它们不是简单开关，而是支撑多版本、多用户类型、多实验能力的架构机制。

常见用途：

- **构建期裁剪**：外部构建剔除 ant-only、daemon、assistant、coordinator、context collapse 等能力。
- **运行期实验**：GrowthBook 控制 auto background agents、auto mode 行为、tool search、compact 策略。
- **能力隔离**：不同用户类型、不同平台、不同模型能力下暴露不同工具和命令。
- **风险控制**：高级权限、auto mode、PowerShell、remote-control、agent swarms 等能力按 gate 开放。
- **性能优化**：懒加载 feature-gated 模块，减少常规 CLI 启动成本。

代价也很明显：代码路径数量显著增加，阅读时必须同时看 feature gate、环境变量、用户类型、settings 和模型能力，否则容易误判某个模块是否真实可用。

## 30. 关键文件速查表

| 问题 | 优先看这些文件 |
|---|---|
| CLI 怎么启动？ | `entrypoints/cli.tsx`、`main.tsx` |
| 交互式界面怎么组织？ | `screens/REPL.tsx`、`state/AppStateStore.ts` |
| SDK/headless 怎么跑？ | `QueryEngine.ts`、`cli/print.ts` |
| Agent Loop 在哪里？ | `query.ts`、`query/config.ts`、`query/transitions.ts` |
| API 请求怎么构造？ | `services/api/claude.ts`、`utils/api.ts`、`constants/prompts.ts` |
| 工具接口是什么？ | `Tool.ts`、`tools.ts` |
| 工具怎么执行？ | `services/tools/toolExecution.ts`、`toolOrchestration.ts`、`StreamingToolExecutor.ts` |
| 权限怎么判断？ | `utils/permissions/permissions.ts`、`permissionSetup.ts`、`hooks/useCanUseTool.tsx` |
| 沙箱怎么配置？ | `utils/sandbox/sandbox-adapter.ts`、`tools/BashTool/shouldUseSandbox.ts` |
| MCP 怎么接入？ | `services/mcp/client.ts`、`services/mcp/config.ts`、`tools/MCPTool/MCPTool.ts` |
| Compact 怎么做？ | `services/compact/autoCompact.ts`、`compact.ts`、`prompt.ts` |
| Skill 怎么加载？ | `skills/loadSkillsDir.ts`、`tools/SkillTool/SkillTool.ts` |
| Hooks 怎么跑？ | `utils/hooks.ts`、`services/tools/toolHooks.ts`、`schemas/hooks.ts` |
| 子代理怎么启动？ | `tools/AgentTool/AgentTool.tsx`、`runAgent.ts`、`tasks/LocalAgentTask/LocalAgentTask.tsx` |
| 会话怎么保存/恢复？ | `utils/sessionStorage.ts`、`utils/sessionRestore.ts`、`utils/conversationRecovery.ts` |


## 31. 设计亮点

1. 工具契约足够强：schema、权限、并发、展示、结果、分类器输入都在一个接口里，横切逻辑集中。
2. 动态工具池可控：deny rule 在模型可见前过滤，MCP 工具合并排序保证 cache 稳定。
3. 协议修复意识强：任何异常路径都努力生成合法 tool_result，维护 Anthropic Messages API 的消息配对约束。
4. 权限多层防御：规则、模式、hooks、分类器、交互、沙箱、dangerous rule stripping 叠加。
5. 长上下文是系统工程：auto compact、reactive compact、session memory、snip、post-compact restoration 共同处理。
6. 扩展面统一：MCP、插件、技能、agent 都最终落到 command/tool/hook/resource 这些运行时抽象。
7. 会话可恢复：JSONL transcript、子代理 transcript、metadata、content replacement、file history 使长任务和 resume 可行。
8. 性能工程深入：启动快路径、动态 import、keychain/MDM prefetch、streaming tool execution、speculative classifier、prompt cache 稳定性都被显式优化。

## 32. 主要复杂性与风险

1. 入口和 REPL 过大：`main.tsx` 与 `screens/REPL.tsx` 聚合太多产品逻辑，维护成本高。
2. feature gate 与 dead-code elimination 让代码路径难以穷尽测试，尤其存在大量 `feature(...) ? require(...) : null`。
3. 权限系统状态多源：settings、policy、session、CLI、hooks、UI、classifier、sandbox 叠加，容易出现边界理解偏差。
4. 模型协议依赖强：tool_use/tool_result、thinking block、cache boundary、defer_loading 等协议细节贯穿多层，一旦 API 语义变化会牵动面大。
5. hook 和插件扩展面提升灵活性的同时，也扩大了调试空间和安全边界。
6. auto mode 使用模型分类器做安全决策，虽然有 fail-closed、denial tracking 和不可绕过 safetyCheck，但仍是高敏感路径。
7. transcript 和压缩机制复杂，老格式兼容、progress bridge、content replacement、post-compact restore 都需要长期维护。

## 33. 可复用的工程经验

- 把模型可见工具空间当成安全和性能边界，不只是运行时权限边界。
- 让工具接口承担完整生命周期，而不是只定义 `execute(args)`。
- 对 agent loop 做协议修复：中断、fallback、并发错误都要产出合法消息序列。
- 大模型产品的“上下文管理”应是分层系统：估算、预警、总结、恢复、失败熔断都需要。
- 插件/技能/MCP 不应绕过核心执行链路；扩展能力越强，越要统一权限、hook 和遥测。
- 对长任务代理，日志必须是可恢复事实源，UI progress 应与 transcript 明确分离。
- 启动性能需要架构级处理：快路径、懒加载、并行预取、cache 稳定性比微优化更重要。

## 34. 推荐阅读路径

如果继续深入，建议按这个顺序读源码：

1. `restored-src/src/entrypoints/cli.tsx`
2. `restored-src/src/main.tsx`
3. `restored-src/src/screens/REPL.tsx`
4. `restored-src/src/QueryEngine.ts`
5. `restored-src/src/query.ts`
6. `restored-src/src/Tool.ts`
7. `restored-src/src/tools.ts`
8. `restored-src/src/services/tools/toolExecution.ts`
9. `restored-src/src/services/tools/StreamingToolExecutor.ts`
10. `restored-src/src/utils/permissions/permissions.ts`
11. `restored-src/src/utils/sandbox/sandbox-adapter.ts`
12. `restored-src/src/services/api/claude.ts`
13. `restored-src/src/services/compact/autoCompact.ts`
14. `restored-src/src/services/compact/compact.ts`
15. `restored-src/src/services/mcp/client.ts`
16. `restored-src/src/tools/AgentTool/AgentTool.tsx`
17. `restored-src/src/tools/AgentTool/runAgent.ts`
18. `restored-src/src/utils/sessionStorage.ts`
19. `restored-src/src/skills/loadSkillsDir.ts`
20. `restored-src/src/utils/plugins/pluginLoader.ts`

## 35. 总体架构图

```text
User / SDK / Remote / Background
        |
        v
processUserInput / Slash Commands / Hooks / Attachments
        |
        v
System Prompt + User Context + System Context + Tool Pool
        |
        v
query() model loop  <-------------------------------+
        |                                            |
        | assistant text / tool_use                  |
        v                                            |
Tool orchestration / StreamingToolExecutor           |
        |                                            |
        v                                            |
toolExecution: schema -> validate -> hooks -> permission
        |                                            |
        v                                            |
Tool.call / MCP call / Bash / File / Agent / Skill   |
        |                                            |
        v                                            |
tool_result + attachments + progress + telemetry ----+
        |
        v
Transcript JSONL / AppState / Compact / Memory / Tasks
```

## 36. 最终评价

从工程角度看，这个 AI 编程助手的核心竞争力不只是模型能力，而是围绕模型建立的一整套执行操作系统：它有启动器、运行时、工具 ABI、权限内核、沙箱适配、扩展包管理、任务调度、会话日志、上下文 GC、UI 事件循环和遥测系统。它把“让模型写代码”变成了“让模型在受控、可恢复、可扩展、可观察的工程环境中行动”。

这也解释了源码复杂度的来源：只要允许模型真实读写文件、运行命令、调用外部服务、长期工作并跨会话恢复，就必须处理权限、并发、失败、恢复、上下文、用户体验和企业策略。Claude Code 的设计选择是把这些复杂性显式工程化，而不是藏在提示词里。
