# Claude Code 执行机制全景分析

> 本文档基于 Claude Code CLI/桌面端/IDE 插件的可观测行为与系统机制，系统梳理会话、Session、记忆、Skill、工具调用等核心底层逻辑。

---

## 目录

1. [会话（Conversation）基础架构](#1-会话基础架构)
2. [上下文窗口与压缩机制](#2-上下文窗口与压缩机制)
3. [系统提示（System Prompt）层级](#3-系统提示层级)
4. [工具系统（Tools）深度解析](#4-工具系统深度解析)
5. [权限模型（Permission Model）](#5-权限模型)
6. [Hooks 执行机制](#6-hooks-执行机制)
7. [记忆系统（Memory System）](#7-记忆系统)
8. [Skill 系统](#8-skill-系统)
9. [子代理系统（Sub-agent / Agent Tool）](#9-子代理系统)
10. [CLAUDE.md 配置层级](#10-claudemd-配置层级)
11. [Prompt 缓存（Prompt Cache）](#11-prompt-缓存)
12. [调度与定时任务（Cron / Schedule）](#12-调度与定时任务)
13. [任务跟踪系统（Task System）](#13-任务跟踪系统)
14. [模型选择与 Fast Mode](#14-模型选择与-fast-mode)
15. [会话标识符与持久化](#15-会话标识符与持久化)
16. [完整执行流程时序图](#16-完整执行流程时序图)

---

## 1. 会话基础架构

### 1.1 消息结构

每轮对话由以下角色的消息交替组成：

```
system  →  user  →  assistant  →  user  →  assistant  →  ...
```

- **system**：初始化时注入，包含 CLAUDE.md 内容、记忆索引（MEMORY.md）、可用 Skill 列表、可用 Deferred Tools 列表、环境信息（OS、Shell、工作目录、模型 ID 等）。
- **user**：用户明文输入，也可包含 `<system-reminder>` 标签（运行时动态注入的系统级信息）。
- **assistant**：模型输出，包含文本和工具调用（tool_use）块，二者可混合出现。

### 1.2 `<system-reminder>` 标签机制

`<system-reminder>` 是平台在 **user 角色消息** 中动态注入的系统信息，常见内容：

| 类型 | 注入时机 | 典型内容 |
|------|---------|---------|
| Deferred Tools 列表 | 每轮对话开头 | 尚未加载 schema 的工具名单 |
| Skills 列表 | 每轮对话开头 | 可调用的 Skill 名称与触发条件 |
| CLAUDE.md 内容 | 每轮对话开头 | 用户/项目级指令 |
| MEMORY.md 内容 | 每轮对话开头 | 记忆索引文件 |
| Hook 反馈 | 工具调用后 | hooks 的 stdout 输出 |

**关键特性**：`<system-reminder>` 中的内容对模型具有类 system 指令的权威性，但在技术上仍走 user 角色通道注入，避免 system prompt 过长。

### 1.3 工具调用消息结构

```
assistant message:
  content[0]: text block   → "我来查一下这个文件..."
  content[1]: tool_use block {
    id: "toolu_01Abc..."
    name: "Read"
    input: { file_path: "/foo/bar.py" }
  }

user message (tool result):
  content[0]: tool_result block {
    tool_use_id: "toolu_01Abc..."
    content: "...文件内容..."
  }
```

一轮 assistant 输出可包含多个 tool_use 块（并行工具调用），随后的 user 消息包含对应数量的 tool_result。

---

## 2. 上下文窗口与压缩机制

### 2.1 上下文窗口限制

当前 Claude Sonnet 4.6 / Opus 4.7 的上下文窗口为 **200K tokens**。随着对话进行，历史消息累积会逼近上限。

### 2.2 自动压缩（Auto-compaction）

当上下文接近限制时，系统自动触发消息压缩：

1. **触发条件**：上下文使用量接近阈值（通常 ~80-90%）
2. **压缩策略**：将较早的消息历史摘要化，保留：
   - 当前目标（goal）
   - 已修改的文件列表
   - 关键决策和结论
   - 尚未完成的风险/问题
3. **`/compact` 命令**：用户主动触发，可附加保留要点提示

**压缩后的影响**：
- 早期工具调用结果消失，但摘要保留关键信息
- Prompt cache 失效（因消息结构变化）
- 模型对早期代码细节的记忆依赖压缩质量

### 2.3 `--continue` 与 `--resume` 参数

```bash
claude --continue          # 继续最近一次会话
claude --resume <session-id>  # 恢复指定 session
```

这些参数将历史消息重新载入上下文，使模型能"接续"之前的工作。

---

## 3. 系统提示层级

Claude Code 的系统提示由多层叠加构成，从高到低优先级：

```
┌─────────────────────────────────────────────┐
│  Anthropic 内置 System Prompt（最高，不可见）   │
├─────────────────────────────────────────────┤
│  ~/.claude/CLAUDE.md  (Global User Config)   │
├─────────────────────────────────────────────┤
│  <project>/.claude/CLAUDE.md  (Project)      │
├─────────────────────────────────────────────┤
│  <project>/CLAUDE.md  (Local Project Root)   │
├─────────────────────────────────────────────┤
│  子目录 CLAUDE.md（按工作目录深度动态加载）     │
├─────────────────────────────────────────────┤
│  动态注入：MEMORY.md、Skills、工具列表、环境   │
└─────────────────────────────────────────────┘
```

**覆盖规则**：下层可覆盖上层，但 "OVERRIDE" 关键词（如 CLAUDE.md 中的 "IMPORTANT: These instructions OVERRIDE"）显式提升优先级。

---

## 4. 工具系统（Tools）深度解析

### 4.1 工具分类

#### 4.1.1 Always-Available Tools（始终可用）

无需预加载，可直接调用：

| 工具 | 功能 |
|------|------|
| `Read` | 读取文件（支持 PDF、图片、Jupyter Notebook） |
| `Edit` | 精确字符串替换编辑文件 |
| `Write` | 写入/覆盖文件 |
| `Glob` | 文件路径模式匹配 |
| `Grep` | 基于 ripgrep 的代码内容搜索 |
| `Bash` | 执行 shell 命令 |
| `Agent` | 启动子代理 |
| `Skill` | 调用技能 |
| `ToolSearch` | 加载 Deferred Tools 的 schema |

#### 4.1.2 Deferred Tools（延迟加载工具）

这类工具在 `<system-reminder>` 中只列出名字，**不包含参数 schema**。直接调用会触发 `InputValidationError`。必须先用 `ToolSearch` 加载 schema：

```
ToolSearch("select:WebFetch,WebSearch")
→ 返回完整 JSON Schema
→ 之后可正常调用 WebFetch/WebSearch
```

常见 Deferred Tools：

| 工具 | 功能 |
|------|------|
| `WebFetch` | 抓取网页内容 |
| `WebSearch` | 网络搜索 |
| `TaskCreate/TaskGet/TaskList/TaskUpdate/TaskStop/TaskOutput` | 任务管理 |
| `CronCreate/CronDelete/CronList` | 定时任务 |
| `Monitor` | 监听后台进程输出流 |
| `AskUserQuestion` | 主动向用户提问 |
| `PushNotification` | 推送通知 |
| `RemoteTrigger` | 触发远程操作 |
| `EnterPlanMode/ExitPlanMode` | 进入/退出计划模式 |
| `EnterWorktree/ExitWorktree` | Git worktree 隔离 |
| `NotebookEdit` | 编辑 Jupyter Notebook |
| `ScheduleWakeup` | 动态循环中的定时唤醒 |
| `MCP 工具` | 挂载的 MCP Server 工具 |

**为什么延迟加载？** 每个工具的 JSON Schema 占用 token，将不常用工具延迟加载可节省每轮的 token 开销并减少 prompt 长度。

### 4.2 工具调用并行性

```
// 并行（无依赖关系时，单条 assistant 消息中多个 tool_use 块）:
assistant: [Read("a.py"), Read("b.py"), Glob("**/*.ts")]  ← 一次输出

// 串行（有依赖时，必须等前一个结果）:
assistant: [Read("config.json")]
user:      [tool_result: {...}]
assistant: [Edit("config.json", ...)]  ← 依赖上一步结果
```

### 4.3 Bash 工具特殊行为

- 工作目录在命令间**不持久**（每次 Bash 调用独立 shell）
- 后台执行：`run_in_background: true`，完成后通知
- 超时：默认 120s，最大 600s
- 不建议 `-i` 交互式标志（无 TTY）

### 4.4 工具结果处理

工具结果以 `tool_result` 消息返回，模型基于结果继续推理。若工具调用被用户**拒绝**，Claude 不会重试相同调用，而是调整策略。

---

## 5. 权限模型（Permission Model）

### 5.1 权限层级

```
~/.claude/settings.json          ← 全局用户级
<project>/.claude/settings.json  ← 项目级
<project>/.claude/settings.local.json  ← 本地项目级（不入 git）
```

### 5.2 权限模式

用户在启动时选择以下之一：

| 模式 | 行为 |
|------|------|
| Default | 敏感操作需逐个确认 |
| Auto-approve (Shift+Tab) | 自动批准所有工具调用 |
| Custom allowlist | 按工具类型/命令预批准 |

### 5.3 settings.json 结构示例

```json
{
  "permissions": {
    "allow": [
      "Bash(git *)",
      "Bash(npm run *)",
      "Read(*)",
      "Edit(*)"
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Bash(git push --force)"
    ]
  },
  "env": {
    "DEBUG": "true"
  }
}
```

**匹配规则**：`deny` 优先于 `allow`；glob 模式匹配工具名及参数。

### 5.4 权限提示流程

```
Claude 调用工具
  → 权限系统检查 allow/deny 列表
    → 命中 allow → 自动执行
    → 命中 deny  → 拒绝，返回错误
    → 无匹配     → 弹出用户确认对话框
      → 用户批准 → 执行，可选"记住此决定"
      → 用户拒绝 → Claude 收到拒绝信号，调整策略
```

---

## 6. Hooks 执行机制

Hooks 是在特定事件发生时**自动执行的 shell 命令**，由 Claude Code 运行时（harness）触发，而非 Claude 模型本身。

### 6.1 Hook 类型

| Hook 名称 | 触发时机 |
|-----------|---------|
| `PreToolUse` | 工具调用之前 |
| `PostToolUse` | 工具调用之后 |
| `UserPromptSubmit` | 用户提交消息时 |
| `Stop` | Claude 停止响应后 |
| `SubagentStop` | 子代理停止后 |

### 6.2 配置示例

```json
// settings.json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Edit|Write",
      "hooks": [{
        "type": "command",
        "command": "npm run lint"
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "notify-send 'Claude finished'"
      }]
    }]
  }
}
```

### 6.3 Hook 的输出反馈

Hook 的 stdout 输出会作为 `<system-reminder>` 注入到下一轮消息中，Claude 可读取并响应（如 lint 错误）。Hook 被阻塞时，Claude 不会重试被阻塞的操作，而是询问用户如何调整。

---

## 7. 记忆系统（Memory System）

### 7.1 文件结构

```
~/.claude/projects/
  -Users-panbk/         ← 按工作目录路径哈希命名
    memory/
      MEMORY.md         ← 索引文件（每轮自动载入）
      user_role.md      ← 具体记忆文件
      feedback_*.md
      project_*.md
      reference_*.md
```

### 7.2 记忆类型

| 类型 | 存储内容 | 何时保存 |
|------|---------|---------|
| `user` | 用户角色、偏好、技能背景 | 了解到用户特征时 |
| `feedback` | 用户对 Claude 行为的纠正或确认 | 用户给出工作方式反馈时 |
| `project` | 项目背景、决策、截止日期 | 了解项目上下文时 |
| `reference` | 外部资源指针（Linear、Grafana等）| 了解外部系统地址时 |

### 7.3 记忆文件格式

```markdown
---
name: 用户技术背景
description: 用户是 Go 专家，刚开始接触 React 前端
type: user
---

用户有 10 年 Go 经验，是第一次接触本项目的 React 部分。

**Why:** 用户在对话中自我介绍
**How to apply:** 解释前端概念时用 Go 后端类比
```

### 7.4 MEMORY.md 索引机制

```markdown
# Memory Index

- [用户角色](user_role.md) — Go 专家，React 新手
- [反馈_简洁风格](feedback_terse.md) — 不要在回复末尾重复已做的事
```

MEMORY.md 的前 **200 行**会被自动载入每轮上下文（超出部分截断）。因此索引条目需保持简洁（≤150 字符/条）。

### 7.5 记忆读写流程

```
对话开始
  → system-reminder 注入 MEMORY.md 内容
  → Claude 判断记忆相关性
    → 相关 → 参考记忆调整行为
    → 记忆可能过时 → 先验证（Read/Grep）再使用

对话中
  → 发现值得记忆的信息
    → Write 写入具体记忆文件（含 frontmatter）
    → Edit 更新 MEMORY.md 索引（新增一行）
  
  → 用户要求遗忘某事
    → 找到对应文件，删除内容或文件
    → 更新 MEMORY.md 索引
```

### 7.6 记忆 vs 其他持久化方式对比

| 机制 | 作用域 | 生命周期 | 适用场景 |
|------|--------|---------|---------|
| Memory 文件 | 跨会话 | 永久 | 用户偏好、项目背景 |
| Plan（计划模式）| 当前会话 | 会话结束 | 实现路径对齐 |
| Task 系统 | 当前会话 | 会话结束 | 步骤跟踪进度 |
| CLAUDE.md | 跨会话 | 永久 | 行为规则、约定 |
| Bash 变量 | 当前 Bash 调用 | 瞬时 | 命令间传递数据 |

---

## 8. Skill 系统

### 8.1 什么是 Skill

Skill 是预定义的专业化工作流，通过 `Skill` 工具触发。本质上是一段特殊的 system-level 指令注入，使 Claude 获得某领域的额外上下文和行为规则。

### 8.2 Skill 调用流程

```
用户输入 "/review" 或 Skill 触发条件满足
  → Claude 调用 Skill("review") 工具
  → 运行时加载对应 Skill 的指令（类似动态注入一段 CLAUDE.md）
  → Claude 按 Skill 指令执行专业化工作流
```

### 8.3 可用 Skill 列表（当前环境）

| Skill | 触发场景 |
|-------|---------|
| `update-config` | 配置 settings.json、hooks、权限 |
| `keybindings-help` | 自定义键盘快捷键 |
| `simplify` | 代码质量审查与简化 |
| `fewer-permission-prompts` | 分析权限请求并添加白名单 |
| `loop` | 设置循环执行任务 |
| `schedule` | 创建定时远程代理 |
| `claude-api` | Claude API / Anthropic SDK 开发 |
| `claude-code-init` | 初始化 Claude Code、CLAUDE.md |
| `codex:setup/rescue` | Codex CLI 集成 |
| `init` | 生成 CLAUDE.md 文档 |
| `review` | PR 代码审查 |
| `security-review` | 安全审查 |

### 8.4 Skill 与普通指令的区别

| 维度 | 普通对话指令 | Skill |
|------|------------|-------|
| 持久性 | 仅当前消息有效 | 注入后在本轮会话有效 |
| 专业深度 | 依赖基础能力 | 包含领域专用流程 |
| 工具访问 | 标准工具集 | 可解锁特定工具组合 |
| 触发方式 | 自然语言 | `/skill-name` 或条件触发 |

---

## 9. 子代理系统（Sub-agent / Agent Tool）

### 9.1 Agent 工具基础

```javascript
Agent({
  description: "简短描述（3-5词）",
  subagent_type: "Explore",     // 可选，指定专业类型
  prompt: "详细指令...",
  model: "sonnet",              // 可选，覆盖模型
  run_in_background: false,     // 可选，后台运行
  isolation: "worktree"         // 可选，git worktree 隔离
})
```

### 9.2 子代理类型

| 类型 | 工具权限 | 最佳用途 |
|------|---------|---------|
| `Explore` | 只读（无 Edit/Write/Agent） | 代码库探索、文件搜索 |
| `claude-code-guide` | Read/Grep/Glob/WebFetch/WebSearch | Claude API/SDK 问题 |
| `claude-config-optimizer` | 全部工具 | Agent 配置设计优化 |
| `code-reviewer` | 全部工具 | 代码审查 |
| `debugger` | 全部工具 | 错误调试 |
| `test-writer` | 全部工具 | 编写测试 |
| `refactor-advisor` | 全部工具 | 代码重构 |
| `Plan` | 只读（无 Edit/Write） | 实现方案设计 |
| `general-purpose` | 全部工具 | 通用复杂任务 |
| `codex:codex-rescue` | Bash | Codex 任务救援 |

### 9.3 子代理的上下文隔离

**关键特性**：子代理启动时完全冷启动，**不携带父会话的任何历史记录**。

```
父会话（主 Claude）
  ├── 知道：用户名叫 John，项目是 X
  └── 调用 Agent(prompt="...")
        ↓
      子代理（独立实例）
        ├── 不知道：用户是谁、之前做了什么
        ├── 需要 prompt 自包含所有必要上下文
        └── 返回单条结果消息给父会话
```

**提示写法要求**：Prompt 必须包含所有背景信息，不能依赖"你知道我们之前讨论的..."。

### 9.4 SendMessage 继续子代理

```javascript
// 继续已有子代理（不新建）
SendMessage({
  to: "agent-name-or-id",
  message: "继续刚才的工作..."
})
```

用于已存在的子代理有完整上下文时，避免冷启动的开销。

### 9.5 并行子代理

```javascript
// 单条消息中多个 Agent 调用 = 并行执行
[
  Agent({ description: "搜索 API 文档", ... }),
  Agent({ description: "检查测试覆盖", ... }),
  Agent({ description: "分析依赖关系", ... })
]
```

### 9.6 Worktree 隔离

```javascript
Agent({
  isolation: "worktree",  // 创建临时 git worktree
  prompt: "..."
})
```

- 子代理在隔离的 worktree 工作，不影响主工作目录
- 若代理无修改，worktree 自动清理
- 若有修改，返回 worktree 路径和分支名

---

## 10. CLAUDE.md 配置层级

### 10.1 文件查找顺序

```
启动时工作目录：/Users/panbk/projects/myapp/src/components/

加载顺序（从根到叶）：
1. ~/.claude/CLAUDE.md
2. /Users/panbk/projects/myapp/.claude/CLAUDE.md
3. /Users/panbk/projects/myapp/CLAUDE.md
4. /Users/panbk/projects/myapp/src/CLAUDE.md
5. /Users/panbk/projects/myapp/src/components/CLAUDE.md
```

### 10.2 动态加载

子目录中的 CLAUDE.md 在模型读取该目录文件时动态载入，无需预先扫描全部路径。

### 10.3 `@import` 机制

```markdown
<!-- CLAUDE.md -->
@.claude/backend-guidelines.md
@.claude/security-rules.md
```

支持从 CLAUDE.md 引入其他文档，模块化管理大型项目规则。

---

## 11. Prompt 缓存（Prompt Cache）

### 11.1 缓存机制

Anthropic API 对**前缀相同的 token 序列**进行缓存。缓存 TTL 为 **5 分钟**。

```
带缓存的请求 token 结构：
[system prompt（稳定）] [历史消息（稳定）] [新消息（变化）]
        ↑ 缓存命中             ↑ 缓存命中       ↑ 不缓存
```

### 11.2 对 Claude Code 的影响

| 场景 | 缓存状态 |
|------|---------|
| 连续对话，5分钟内 | 历史消息缓存命中，成本↓速度↑ |
| 5分钟后继续 | 缓存失效，全量处理 |
| `/compact` 压缩后 | 缓存失效（消息结构变化） |
| 子代理调用 | 独立缓存上下文 |

### 11.3 ScheduleWakeup 与缓存的关系

在 `/loop` 动态循环中，`ScheduleWakeup` 的 `delaySeconds` 选择与缓存直接相关：

- **< 300s（5分钟）**：缓存保持热态，响应更快更便宜
- **300s**：最差选择（缓存刚失效，又不够长来分摊开销）
- **> 300s**：缓存冷启动，适合无需频繁检查的长等待

---

## 12. 调度与定时任务（Cron / Schedule）

### 12.1 CronCreate

```javascript
// 需要先用 ToolSearch("select:CronCreate") 加载 schema
CronCreate({
  schedule: "0 9 * * 1-5",  // 标准 cron 表达式
  prompt: "检查 CI 状态并报告",
  name: "daily-ci-check"
})
```

创建**远程定时代理**，在指定时间触发独立的 Claude Code 会话。

### 12.2 /loop 动态循环

```
/loop [interval] [command]
```

- 无 interval 时：模型自主决定下次唤醒时间（调用 `ScheduleWakeup`）
- 每次唤醒：重新执行相同 prompt，保持循环
- 结束循环：不调用 `ScheduleWakeup` 即退出

### 12.3 /schedule Skill

通过 `schedule` Skill 管理远程触发器（RemoteTrigger），与 CronCreate 的区别在于：
- CronCreate：基于时间触发
- RemoteTrigger：基于事件触发（webhook等）

---

## 13. 任务跟踪系统（Task System）

### 13.1 Task 生命周期

```
TaskCreate → TaskGet → TaskUpdate(status: "in_progress")
  → 实际工作 →  TaskUpdate(status: "completed")
```

### 13.2 Task 状态

```
pending → in_progress → completed
                      → failed
                      → cancelled
```

### 13.3 后台 Task

```javascript
Bash({ command: "npm run build", run_in_background: true })
// → 立即返回，Claude 继续其他工作
// → 构建完成时通知 Claude
// → 用 TaskOutput 读取输出
```

### 13.4 使用原则

- Task 用于**当前会话**的进度跟踪
- 每完成一步立即更新状态（不批量处理）
- 不用于跨会话持久化（用 Memory 代替）

---

## 14. 模型选择与 Fast Mode

### 14.1 当前可用模型

| 模型 ID | 别名 | 特点 |
|---------|------|------|
| `claude-opus-4-7` | opus | 最强推理能力 |
| `claude-sonnet-4-6` | sonnet | 平衡性能（默认） |
| `claude-haiku-4-5-20251001` | haiku | 速度优先 |

### 14.2 Fast Mode

- 命令：`/fast` 切换
- 仅在 Opus 4.6 上可用（加速输出，**不**降级到更小模型）
- 适用于需要 Opus 能力但希望更快响应的场景

### 14.3 子代理模型选择

```javascript
Agent({
  model: "haiku",  // 探索任务用便宜快速模型
  prompt: "列出所有 TypeScript 文件..."
})

Agent({
  model: "opus",   // 复杂推理用强模型
  prompt: "分析这段算法的时间复杂度..."
})
```

---

## 15. 会话标识符与持久化

### 15.1 Session ID

每次 Claude Code 启动分配唯一 session ID，用于：
- `--resume <session-id>` 恢复历史会话
- 日志关联
- 子代理会话隔离

### 15.2 会话文件存储

```
~/.claude/
  projects/
    -Users-panbk-myproject/  ← 项目路径的规范化
      memory/               ← 记忆文件
  sessions/
    <session-id>.jsonl      ← 消息历史（JSONL 格式）
  settings.json             ← 全局配置
  keybindings.json          ← 快捷键配置
```

### 15.3 MCP Server 状态

MCP (Model Context Protocol) Server 在 Claude Code 进程中持久运行，跨工具调用保持连接。MCP 工具以 `mcp__<server-name>__<tool-name>` 格式出现在 Deferred Tools 列表中。

---

## 16. 完整执行流程时序图

```
用户启动 Claude Code
         │
         ▼
┌─────────────────────────────────────────────────────┐
│                    初始化阶段                         │
│  1. 加载 settings.json（全局+项目）                   │
│  2. 扫描并加载 CLAUDE.md 层级                        │
│  3. 加载 MEMORY.md（注入 system-reminder）           │
│  4. 枚举可用工具（立即可用 + Deferred 列表）          │
│  5. 枚举可用 Skills                                  │
│  6. 启动 MCP Servers                                 │
│  7. 构建初始 System Prompt                           │
└─────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────┐
│                    每轮对话循环                       │
│                                                     │
│  用户输入消息                                        │
│    ↓                                                │
│  Hooks: UserPromptSubmit                            │
│    ↓                                                │
│  构建请求：                                          │
│    - system prompt（CLAUDE.md + MEMORY.md + Skills）│
│    - 历史消息（或压缩摘要）                           │
│    - 新 user 消息                                    │
│    ↓                                                │
│  API 调用（附 Prompt Cache）                        │
│    ↓                                                │
│  模型推理                                            │
│    ↓                                                │
│  输出解析                                            │
│    ├── 纯文本 → 显示给用户                           │
│    └── tool_use 块                                  │
│          ↓                                          │
│        权限检查                                      │
│          ├── 允许 → 执行工具                         │
│          │     ↓                                    │
│          │   Hooks: PreToolUse / PostToolUse         │
│          │     ↓                                    │
│          │   工具执行                               │
│          │     ↓                                    │
│          │   返回 tool_result                       │
│          │     ↓                                    │
│          │   追加到消息历史，继续推理                 │
│          │                                          │
│          └── 拒绝 → Claude 收到拒绝信号，调整策略    │
│                                                     │
│  响应完成                                            │
│    ↓                                                │
│  Hooks: Stop                                        │
│    ↓                                                │
│  检查上下文使用量                                    │
│    ├── 正常 → 等待下一轮输入                         │
│    └── 接近限制 → 触发 Auto-compaction               │
└─────────────────────────────────────────────────────┘
```

---

## 附录：关键设计决策解析

### A. 为什么 Deferred Tools 而非始终加载所有工具？

每个工具 JSON Schema 约 200-500 tokens。20+ 个工具 = ~10K tokens/轮。延迟加载将按需付费降至仅加载实际使用的工具。

### B. 为什么子代理冷启动而非共享父上下文？

1. **隔离性**：子代理的工具调用（尤其文件修改）不污染父会话的决策树
2. **并行性**：共享上下文无法并行执行（需串行保证一致性）
3. **成本控制**：传递 200K token 的父上下文给每个子代理成本极高

### C. `<system-reminder>` 为何走 user 通道而非 system？

1. System prompt 在 API 层面只有一个，而 system-reminder 需要动态、多次注入
2. 避免每轮重新构建完整 system prompt（缓存失效成本高）
3. user 消息中的标签让模型知道这是系统信息，具有相应权威性

### D. Memory 系统为何用文件而非数据库？

1. 对 Claude 的工具集（Read/Write/Edit）天然友好
2. 无需额外依赖（无 SQLite/Redis）
3. 用户可直接用文本编辑器查看和修改记忆内容
4. Git 可版本管理记忆变更历史

---

*文档生成时间：2026-04-18 | 适用版本：Claude Code CLI + claude-sonnet-4-6*
