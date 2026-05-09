# Claude Code 底层实现全景手册

> 更新时间：2026-05-09
> 目标：从安装、配置、文件、会话、Hook、工具、MCP、IDE、SDK 等所有底层维度理解 Claude Code 的运行方式。
> 说明：本文聚焦 Claude Code CLI（`claude` 命令）的实现机制，所有路径以 Linux/macOS 默认布局为准（Windows 在 `%USERPROFILE%\.claude\` 下结构相同）。

---

## 1. 运行时与安装

### 1.1 运行时
- Claude Code 是基于 **Node.js**（>= 18）的 CLI，发布产物为 npm 包 `@anthropic-ai/claude-code`，可执行入口为 `claude`。
- 内部使用 React + Ink 渲染终端 UI（终端的“TUI”），通过 streaming 的 SSE 与 Anthropic API 通信。
- 在受控环境（headless / CI）下退化为非交互式纯文本输入输出。

### 1.2 安装方式
| 方式 | 命令 | 备注 |
|------|------|------|
| 全局 npm | `npm install -g @anthropic-ai/claude-code` | 最常用 |
| 一键脚本 | `curl -fsSL https://claude.ai/install.sh \| bash` | 安装到 `~/.claude/local/` 并把 `claude` 软链到 PATH |
| Homebrew | `brew install anthropic/tap/claude-code` | macOS |
| 原生二进制 | 自动更新机制将更新到 `~/.claude/local/` | 不需要 Node 全局安装 |

### 1.3 启动流程（高层）
1. `claude` 入口加载用户配置（见 §2）。
2. 解析 `CLAUDE.md` 系列记忆文件（见 §3.7）。
3. 注册内置工具与 MCP 工具（见 §9）。
4. 进入 REPL 或非交互模式，开启与 Anthropic API 的对话循环（Agent Harness）。
5. 每条助手响应可能包含 tool_use，由本地 harness 执行并把结果回灌（tool_result）。
6. 命中上下文阈值时触发自动压缩（见 §14）。

### 1.4 鉴权
- 默认使用 Anthropic Console / Claude.ai 登录获得的 OAuth token，缓存于 `~/.claude/.credentials.json`（0600 权限）。
- 也可使用纯 API Key，通过 `ANTHROPIC_API_KEY` 环境变量、或 `apiKeyHelper`（settings.json 字段，指向一个能输出 key 的脚本）。
- 企业可走 Amazon Bedrock 或 Google Vertex（设置 `CLAUDE_CODE_USE_BEDROCK=1` / `CLAUDE_CODE_USE_VERTEX=1`）。

---

## 2. 配置体系（settings.json）

### 2.1 四层叠加（优先级从高到低）
1. **企业管理策略 (Managed Policy)**
   - macOS: `/Library/Application Support/ClaudeCode/managed-settings.json`
   - Linux: `/etc/claude-code/managed-settings.json`
   - Windows: `C:\ProgramData\ClaudeCode\managed-settings.json`
   - 由系统管理员下发，**不可被下层覆盖**（permissions 取交集）。
2. **CLI 参数** (`--permission-mode`, `--model` 等)
3. **本地项目设置**：`<repo>/.claude/settings.local.json`（默认进入 `.gitignore`，存个人偏好）
4. **共享项目设置**：`<repo>/.claude/settings.json`（提交到仓库，团队共享）
5. **用户级设置**：`~/.claude/settings.json`

> 合并语义：对象按 key 合并，**数组（如 `allow`/`deny`）合并取并**，但 `deny` 始终是“一票否决”，企业层 `deny` 不可被下层删除。

### 2.2 完整字段一览

```jsonc
{
  "model": "claude-sonnet-4-6",        // 默认模型，可被 /model 覆盖
  "apiKeyHelper": "/usr/local/bin/get-key.sh",
  "includeCoAuthoredBy": true,         // git commit 是否附带 Co-Authored-By: Claude
  "cleanupPeriodDays": 30,             // ~/.claude/projects/ 下旧 transcript 清理周期
  "autoUpdates": true,                 // 自动升级 CLI
  "env": {                             // 注入到所有子进程的环境变量
    "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
    "DISABLE_TELEMETRY": "1"
  },
  "permissions": {
    "defaultMode": "default",          // default | acceptEdits | plan | bypassPermissions
    "additionalDirectories": ["/srv/data"], // 默认只允许在 cwd 工作；这里追加可访问目录
    "allow":  ["Bash(git status)", "Read(~/Documents/**)"],
    "ask":    ["WebFetch", "Bash(git push *)"],
    "deny":   ["Read(.env)", "Bash(rm -rf *)"]
  },
  "hooks": { /* 见 §5 */ },
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh"
  },
  "outputStyle": "default",            // 见 §12
  "enableAllProjectMcpServers": false,
  "enabledMcpjsonServers":  ["github"],
  "disabledMcpjsonServers": [],
  "forceLoginMethod": "console"        // console | claudeai
}
```

### 2.3 权限规则字符串语法
- 形式：`<Tool>(<pattern>)`，`<Tool>` 为工具名（Bash / Read / Edit / WebFetch / mcp__server__tool 等）。
- 例：
  - `Bash(git diff *)` —— 只允许 `git diff` 开头的命令。
  - `Read(/Users/me/Projects/**)` —— glob 路径白名单。
  - `mcp__github__*` —— 通配某个 MCP server 的所有工具。
- 同一工具同时出现在 `allow` 与 `ask` 时，`ask` 优先；`deny` 永远最高优先级。

### 2.4 关键环境变量

| 变量 | 作用 |
|------|------|
| `ANTHROPIC_API_KEY` | API 鉴权 |
| `ANTHROPIC_AUTH_TOKEN` | 自定义 Bearer token（替代 API key） |
| `ANTHROPIC_BASE_URL` | 反代 / 自托管网关入口 |
| `ANTHROPIC_MODEL` | 默认模型 ID |
| `ANTHROPIC_SMALL_FAST_MODEL` | 用于 Haiku 类轻量调用（如压缩、auto-completion） |
| `CLAUDE_CODE_USE_BEDROCK` / `CLAUDE_CODE_USE_VERTEX` | 切换到 Bedrock/Vertex |
| `AWS_REGION`, `GOOGLE_CLOUD_PROJECT`, `CLOUD_ML_REGION` | 云后端参数 |
| `DISABLE_TELEMETRY=1` / `DISABLE_ERROR_REPORTING=1` | 关遥测 |
| `DISABLE_NON_ESSENTIAL_MODEL_CALLS=1` | 关闭非核心模型调用（标题生成等） |
| `DISABLE_AUTOUPDATER=1` | 禁用自动升级 |
| `BASH_DEFAULT_TIMEOUT_MS` / `BASH_MAX_TIMEOUT_MS` | Bash 工具超时 |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | 单次响应最大 token |
| `MCP_TIMEOUT` / `MCP_TOOL_TIMEOUT` | MCP server 启动 / 调用超时 |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` | 公司网关安全选项 |
| `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` | 标准代理 |

---

## 3. 目录与文件结构（`~/.claude/`）

```
~/.claude/
├── settings.json                   # 用户级设置
├── .credentials.json               # OAuth/API 凭据（0600）
├── CLAUDE.md                       # 用户级全局记忆（所有会话注入）
├── projects/                       # 每个工作目录一个子目录
│   └── -home-user-myrepo/          # 路径转义：/ → -
│       └── <session-uuid>.jsonl    # 会话 transcript
├── todos/                          # TodoWrite 工具持久化（按 session）
│   └── <session-uuid>-agent-<id>.json
├── shell-snapshots/                # Bash 工具会话首次启动捕获的 shell 状态
│   └── snapshot-<bash|zsh>-<ts>-<rand>.sh
├── statsig/                        # 实验/特性开关本地缓存
├── ide/                            # IDE 集成 lock 文件
│   └── <port>.lock                 # JSON：{ pid, workspaceFolders, ideName, transport, authToken, ... }
├── plugins/
│   ├── config.json                 # 已启用插件
│   └── repos/<owner>/<repo>/...    # 已安装的插件源
├── commands/                       # 用户级 slash command
│   └── *.md
├── agents/                         # 用户级 subagent
│   └── *.md
├── skills/                         # 用户级 skill
│   └── <skill>/SKILL.md
├── output-styles/                  # 用户级 output style
│   └── *.md
├── local/                          # 本地安装的 CLI（自动更新到这里）
└── logs/                           # 调试日志（CLAUDE_CODE_DEBUG=1）
```

### 3.1 `projects/<escaped-path>/<uuid>.jsonl`
- 工作目录路径中的 `/` 被替换成 `-`，例如 `/home/user/I-m-Programmer` → `-home-user-I-m-Programmer/`。
- 每条会话一个 JSONL 文件，**每行一条事件**。常见字段：

```jsonc
// 示例（一行一条 JSON，下方为可读化）
{"type":"summary","summary":"Refactor settings loader","leafUuid":"..."}
{"type":"user","uuid":"...","timestamp":"2026-05-09T03:14:00Z",
 "sessionId":"...","cwd":"/home/user/repo","gitBranch":"main",
 "message":{"role":"user","content":[{"type":"text","text":"..."}]}}
{"type":"assistant","uuid":"...","parentUuid":"...","model":"claude-opus-4-7",
 "message":{"role":"assistant","content":[
   {"type":"text","text":"I'll read the file."},
   {"type":"tool_use","id":"toolu_01","name":"Read","input":{"file_path":"/x"}}]},
 "usage":{"input_tokens":1200,"output_tokens":80,"cache_read_input_tokens":40000}}
{"type":"user","message":{"role":"user","content":[
   {"type":"tool_result","tool_use_id":"toolu_01","content":"...file..."}]}}
```

- `parentUuid` 形成消息 DAG，方便 `/resume` 时按链路回放。
- `cleanupPeriodDays` 控制旧 transcript 清理。

### 3.2 `todos/`
- TodoWrite 工具的状态持久化：每个 session 在每个 agent（含主 agent 与 subagent）下保存一份 JSON。
- 字段：`[{ "content": "...", "status": "pending|in_progress|completed", "activeForm": "..." }]`。

### 3.3 `shell-snapshots/`
- Bash 工具首次执行前，会用 `set` / `alias` / `export` 等命令把当前 shell 状态序列化到一个临时脚本，后续 Bash 调用都先 `source` 该 snapshot，从而保证别名、环境变量在多次调用间一致。

### 3.4 `ide/<port>.lock`
- IDE 扩展（VSCode/JetBrains）启动时监听一个本地端口并写入此 lock 文件：
  ```jsonc
  {
    "pid": 12345,
    "workspaceFolders": ["/home/user/repo"],
    "ideName": "VSCode",
    "transport": "ws",
    "authToken": "..."        // CLI 用 token 通过 WebSocket/JSON-RPC 与 IDE 通讯
  }
  ```
- CLI 通过 `/ide` 命令或自动扫描发现该文件，建立 JSON-RPC over WebSocket，双向同步：选区、打开文件、Diff Viewer、诊断信息等。

### 3.5 `plugins/`
- `config.json` 列出启用的插件 / marketplace。
- 单个插件目录结构：
  ```
  <plugin>/
  ├── plugin.json           # 名称、版本、入口
  ├── commands/             # 提供 slash command
  ├── agents/               # 提供 subagent
  ├── skills/               # 提供 skill
  ├── hooks/hooks.json      # 提供 hook
  └── .mcp.json             # 提供 MCP server
  ```

### 3.6 `.credentials.json`
- 仅本机使用、`chmod 600`。
- 字段示意：
  ```json
  {"claudeAiOauth":{"accessToken":"...","refreshToken":"...","expiresAt":172...}}
  ```

### 3.7 CLAUDE.md 记忆体系
- 三层加载（启动时按顺序拼入 system prompt）：
  1. 用户级：`~/.claude/CLAUDE.md`
  2. 项目共享：`<repo>/CLAUDE.md`
  3. 项目本地：`<repo>/CLAUDE.local.json`（已弃用，改为 `.claude/settings.local.json`）+ `<repo>/.claude/CLAUDE.md`
- **递归向上扫描**：从当前 cwd 一直向上找父目录的 `CLAUDE.md`，全部拼接（适合 monorepo）。
- **`@path` 引用**：CLAUDE.md 中可写 `@./docs/style.md`，会被自动内联扩展（最大深度 5）。
- `/memory` 命令打开编辑器，`/init` 命令为新仓库生成初始 CLAUDE.md。

---

## 4. 会话（Session）机制

### 4.1 Session ID 与 transcript
- 每次 `claude` 启动生成一个 UUIDv4 作为 sessionId，所有事件写入对应 `.jsonl`。
- 子代理调用（Task/Agent）以一个独立的 agentId 嵌套在父会话内，但它们的 transcript 走另一份文件（命名 `<sessionId>-agent-<agentId>.jsonl` 或合并到主文件，取决于版本）。

### 4.2 Resume / Continue
- `claude --continue` （或 `-c`）：恢复 cwd 下**最近一次**会话。
- `claude --resume`（或 `-r`）：弹出选择器，列出 `~/.claude/projects/<cwd>/` 下所有 transcript，按更新时间排序。
- 恢复机制：把 JSONL 重新读入并按 `parentUuid` 链回放为消息数组，再发给 API；若上次结束在 tool_use 未配对，会回滚到最后一组配对边界。

### 4.3 自动压缩（Auto-compact）
- 当上下文使用率 ≥ ~92% 时，CLI 自动调用一次模型对历史进行摘要，将旧消息替换为一段 `<summary>...`，保留最近若干条原始消息。
- `/compact [指令]` 可手动触发，并可附加“关注点”指令（如 “保留所有正在跟踪的 bug”）。
- `PreCompact` hook 可在压缩前介入（保存 transcript、阻止压缩等）。

### 4.4 与会话相关的 hook
- `SessionStart`：CLI 启动或 `/resume` 时触发，可注入额外上下文。
- `SessionEnd`：退出时触发。
- `Stop`：模型停止本轮回复时触发。
- `SubagentStop`：Task 子代理停止时触发。

---

## 5. Hook 系统

### 5.1 8 个 Hook 事件
| 事件 | 触发时机 | 可否阻断 |
|------|----------|----------|
| `SessionStart` | 启动 / resume | 可注入 context |
| `SessionEnd` | 退出 | 不能阻止 |
| `UserPromptSubmit` | 用户提交输入后、模型响应前 | 可阻断（拒绝 prompt） |
| `PreToolUse` | 工具调用前 | 可允许/拒绝/询问 |
| `PostToolUse` | 工具结果产生后 | 可向模型注入反馈 |
| `Notification` | CLI 触发桌面通知时 | 不能阻断 |
| `Stop` | 助手回合结束 | 可强制继续 |
| `SubagentStop` | 子代理回合结束 | 可强制继续 |
| `PreCompact` | 自动 / 手动压缩前 | 可阻止压缩 |

### 5.2 settings.json 结构

```jsonc
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",                       // 工具名/正则；可写 "Edit|Write"
        "hooks": [
          { "type": "command",
            "command": "~/.claude/hooks/audit-bash.sh",
            "timeout": 10000 }                   // 毫秒，默认 60s
        ]
      }
    ],
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "~/.claude/hooks/redact-secrets.py" }] }
    ]
  }
}
```

### 5.3 输入：通过 stdin 传给 hook 的 JSON
```jsonc
{
  "session_id": "...",
  "transcript_path": "/home/user/.claude/projects/.../<uuid>.jsonl",
  "cwd": "/home/user/repo",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": { "command": "rm -rf /" }
}
```

### 5.4 输出协议
- **退出码**：
  - `0`：放行（PostToolUse 时其 stdout 进入对话作为补充上下文）
  - `2`：阻断；stderr 文本作为反馈给模型
  - 其它非零：错误，仅写入 CLI 日志，不阻断
- **结构化 JSON 输出**（推荐，写到 stdout）：
  ```json
  {
    "decision": "block",
    "reason": "command writes to /etc",
    "permissionDecision": "deny",          // PreToolUse: allow|ask|deny
    "permissionDecisionReason": "...",
    "hookSpecificOutput": {
      "additionalContext": "注入到下一次模型上下文",
      "suppressOutput": true
    },
    "continue": false                       // false → 立刻结束当前回合
  }
  ```

### 5.5 典型用途
- 全局禁止改 `production.yml`：PreToolUse 匹配 Edit/Write，命中路径返回 deny。
- 自动 lint：PostToolUse 匹配 Edit，调用 `eslint --fix` 并把错误回灌。
- 注入 secret 到上下文：SessionStart 输出 `additionalContext`。

---

## 6. Slash Commands

### 6.1 文件位置
- 项目级：`<repo>/.claude/commands/<name>.md` → `/name`
- 用户级：`~/.claude/commands/<name>.md`
- 子目录构成命名空间：`commands/git/release.md` → `/release` 显示分组 `(project:git)`。

### 6.2 文件格式（Markdown + frontmatter）

```markdown
---
description: Create a release PR
allowed-tools: Bash(git *), Read, Edit
argument-hint: <version>
model: claude-sonnet-4-6
---

# Release $1

Run !`git log $(git describe --tags --abbrev=0)..HEAD --oneline` and summarize.

Read @CHANGELOG.md and propose updates.

Full args: $ARGUMENTS
```

### 6.3 替换规则
- `$ARGUMENTS`：调用时全部参数字符串。
- `$1`, `$2`, …：位置参数。
- 形如 `` !`shell command` ``：CLI 在送入模型前**先在本地执行**，结果替换到 prompt（受 `allowed-tools` 约束）。
- `@<path>`：把文件内容内联进 prompt。

### 6.4 内置 slash 命令（部分）
`/help /clear /compact /resume /continue /model /config /memory /init /agents /hooks /mcp /ide /permissions /status /cost /login /logout /export /vim /review /security-review /todos`。

---

## 7. Subagents（子代理）

### 7.1 文件
路径：`.claude/agents/<name>.md` 或 `~/.claude/agents/<name>.md`。

```markdown
---
name: code-reviewer
description: Use proactively for code review on diffs.
tools: Read, Grep, Bash(git *)        # 留空 = 继承父代理工具集
model: claude-sonnet-4-6              # 可指定，否则继承
---

You are a senior reviewer. Focus on correctness, security, and tests.
Output a punch list grouped by severity.
```

### 7.2 调用机制
- 主 agent 通过 `Agent`（在 SDK / 内部叫 `Task`）工具调用子代理。
- 子代理拥有**独立上下文窗口**（默认不可见父对话），仅得到主 agent 在调用时给出的 prompt。
- 子代理可被声明 `description: "use proactively..."` 以便主代理自动选用。
- `SubagentStop` hook 在子代理结束时触发。

---

## 8. Skills

### 8.1 概念
Skill 是一段“按需加载的能力包”，由模型自己决定是否调用（model-invoked），也可由用户 `/<skill>` 触发。

### 8.2 文件
位置：`.claude/skills/<skill>/SKILL.md` 或 `~/.claude/skills/<skill>/SKILL.md` 或插件提供。

```markdown
---
name: pdf-fill
description: Fill PDF forms using pdftk. Use when user asks to fill, edit, or annotate a PDF.
---

# Steps
1. Inspect form fields with `pdftk <file> dump_data_fields`.
2. Build FDF.
3. Apply with `pdftk <file> fill_form <fdf> output <out>`.
```

- **Progressive disclosure**：仅 frontmatter 始终在系统提示中，正文只有在 skill 被触发时才注入。
- 支持附属脚本：把 `scripts/`、`reference.md` 放在同目录，由 SKILL.md 主动 Read。

---

## 9. MCP（Model Context Protocol）

### 9.1 作用
让 Claude Code 通过统一协议接入外部工具/数据源（GitHub、Slack、Jira、自研网关）。

### 9.2 注册位置
- 用户级：`claude mcp add <name> ...` → 写入 `~/.claude/.mcp.json`
- 项目级：`<repo>/.mcp.json`（提交到仓库共享）
- 配置示例：

```jsonc
{
  "mcpServers": {
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_TOKEN": "$GITHUB_TOKEN" }
    },
    "internal-api": {
      "type": "http",
      "url": "https://mcp.corp.com/v1",
      "headers": { "Authorization": "Bearer ${env:CORP_TOKEN}" }
    },
    "events": {
      "type": "sse",
      "url": "https://events.corp.com/mcp/sse"
    }
  }
}
```

### 9.3 三种传输
- **stdio**：本地子进程，最常见。
- **SSE**：长连接事件流。
- **HTTP**（streamable HTTP）：常用于 SaaS。

### 9.4 工具命名
所有 MCP 工具在 CLI 里以 `mcp__<server>__<tool>` 形式呈现，可在 `permissions.allow` / `disallowedTools` 中按 glob 匹配。

### 9.5 项目级 MCP 的安全门禁
首次进入仓库时 `.mcp.json` 中声明的 server 默认**询问**才会启用；可用 `enabledMcpjsonServers` / `disabledMcpjsonServers` / `enableAllProjectMcpServers` 显式控制。

---

## 10. 内置工具

| 工具 | 作用 | 关键点 |
|------|------|--------|
| `Read` | 读文件（支持图片/PDF/Notebook） | 默认前 2000 行；图片直接送多模态模型 |
| `Write` | 覆写/新建文件 | 前置要求：先 Read 过该文件（避免盲覆盖） |
| `Edit` | 精确字符串替换 | `old_string` 必须唯一，否则需 `replace_all` |
| `NotebookEdit` | 修改 .ipynb 单元格 | 走 nbformat 解析 |
| `Bash` | 执行 shell | 可后台执行；自动 source `shell-snapshots` |
| `Glob` | 文件名匹配 | 高速 git-aware |
| `Grep` | ripgrep 包装 | 默认排除 .gitignore |
| `WebFetch` | 抓取 URL → 转 markdown 给模型 | 受 ask 权限保护，15 分钟缓存 |
| `WebSearch` | 在线检索 | 受地区/许可限制 |
| `Task`/`Agent` | 启动 subagent | 并发独立上下文 |
| `TodoWrite` | 维护任务清单 | 持久化到 `todos/` |
| `ExitPlanMode` | Plan 模式提交计划 | 仅在 plan 模式可用 |
| `KillShell` / `BashOutput` | 管理后台 Bash | 配合 run_in_background |

每个工具的实际许可由 §2.3 的规则字符串决定。

---

## 11. 权限模式

| 模式 | 含义 | 启动方式 |
|------|------|----------|
| `default` | 写操作 / 高风险命令逐次询问 | 默认 |
| `acceptEdits` | 文件编辑自动放行；其它仍按规则 | `Shift+Tab` 切换 |
| `plan` | 全只读：只能 Read/Grep/Glob/WebSearch；产出计划后必须 `ExitPlanMode` 等用户审批 | `--permission-mode plan` 或 Shift+Tab |
| `bypassPermissions` | 跳过所有提示（仅适合容器/CI） | `--dangerously-skip-permissions` 或 settings |

`deny` 列表在任何模式下都生效。

---

## 12. Statusline 与 Output Styles

### 12.1 Statusline
- `settings.json.statusLine.command` 指向一个脚本；CLI 周期性运行，把 stdout 显示在底部状态栏。
- 脚本通过 stdin 收到 JSON：`{ "model_id": "...", "session_id": "...", "cwd": "...", "transcript_path": "...", "version": "..." }`。
- 例：显示 `[branch · model · token-used]`。

### 12.2 Output Styles
- 文件：`.claude/output-styles/<name>.md` 或 `~/.claude/output-styles/<name>.md`。
- 通过 frontmatter `description` + 正文（替代默认的“Software engineer”系统人格），可整体改写助手的回应风格。
- `/output-style` 命令切换；`settings.json.outputStyle` 设置默认。

---

## 13. IDE 集成

### 13.1 VSCode 扩展 / JetBrains 插件
- 启动时在 `~/.claude/ide/<port>.lock` 写一份元数据。
- CLI（运行在 IDE 内置终端时）自动发现该 lock 并连接。
- 通过 JSON-RPC 提供：
  - `getOpenFiles` / `getActiveSelection`
  - `openDiff`：把 Edit/Write 的改动以 diff viewer 展示
  - `applyEdit` / `revertEdit`
  - `getDiagnostics`（LSP 诊断回灌给模型）
- 关闭 IDE 时 lock 文件被删除。

### 13.2 终端外连接
也可在普通终端运行 `claude`，再 `/ide` 选择已运行的 IDE。

---

## 14. 上下文窗口与压缩

- 模型总窗口（如 200K）由 CLI 估算 token 使用率；当 `usage / max ≥ 0.92` 触发自动压缩。
- 压缩走另一次模型调用（通常 `ANTHROPIC_SMALL_FAST_MODEL`），生成结构化摘要：
  - 已完成的任务列表
  - 关键决策
  - 仍打开的问题 / TODO
  - 重要文件清单（路径 + 用途）
- 摘要替换早期消息，保留最近 N 轮原始消息保证连贯。
- 用户可：
  - `/compact [focus]` 手动压缩并指定关注点
  - 通过 `PreCompact` hook 拒绝/扩展压缩
- **prompt caching**：Claude Code 默认启用 4 段 cache breakpoint（system / tools / history-prefix / current），重复运行时大量历史命中 cache，体现在 `usage.cache_read_input_tokens`。

---

## 15. CLI 参数与非交互模式

```
claude [prompt]                       # 单 prompt 后退出（非交互）
claude --print, -p                    # 打印结果到 stdout
claude --output-format text|json|stream-json
claude --input-format text|stream-json
claude --max-turns N                  # 限制 agent 循环步数
claude --model claude-opus-4-7
claude --permission-mode plan
claude --allowedTools "Read,Edit,Bash(git *)"
claude --disallowedTools "WebFetch"
claude --add-dir /srv/data            # 追加可访问目录
claude --resume [sessionId]
claude --continue
claude --dangerously-skip-permissions # 容器内
claude mcp add <name> -- <cmd> ...    # 注册 MCP server
claude config get/set <key>
claude doctor                         # 健康检查
claude update                         # 手动升级
```

### Headless / pipeline 用法
```bash
echo "summarize CHANGELOG" | claude -p --output-format json --max-turns 4
```
- `stream-json` 输出每条事件一行 JSON，便于 CI 流式解析。

---

## 16. Claude Agent SDK 与 CLI 的关系

- `@anthropic-ai/claude-agent-sdk`（TypeScript）/ `claude-agent-sdk`（Python）把 Claude Code 的核心 Harness 暴露为 API：
  - 同样的工具集（Read/Edit/Bash/...）
  - 同样的 hook / permission 模型
  - 同样的 `.claude/`、`CLAUDE.md`、MCP 加载逻辑
- 典型代码（Python）：
  ```python
  from claude_agent_sdk import query, ClaudeAgentOptions
  async for msg in query(
      prompt="重构 settings 加载器并跑测试",
      options=ClaudeAgentOptions(
          model="claude-sonnet-4-6",
          allowed_tools=["Read","Edit","Bash"],
          permission_mode="acceptEdits",
          cwd="/home/user/repo",
          mcp_servers={...},
      ),
  ):
      print(msg)
  ```
- CLI 本质是 SDK 的一个交互式前端 + TUI；理解 CLI 就等于理解 SDK 在跑什么。

---

## 17. 一次完整请求/响应内部流转（串起来）

1. 用户在 TUI 输入 `请优化 X 函数`。
2. CLI 触发 `UserPromptSubmit` hook（可改写/拒绝）。
3. CLI 组装请求体：
   - system：固定 system prompt + output style + 用户/项目 CLAUDE.md 拼接
   - tools：内置工具 schema + MCP 工具 schema（按权限过滤）
   - messages：历史 transcript（按 cache breakpoint 分段）+ 新输入
4. 通过 SSE 调用 `POST /v1/messages?stream=true`。
5. 收到 `tool_use` 事件 → 走权限链：`deny → ask → allow → 默认按 mode`。
6. 通过后执行工具（本地 Node 实现 / 子进程 / MCP RPC）。
7. 触发 `PreToolUse`、工具执行、`PostToolUse`。
8. 把 `tool_result` 追加到 messages，再次请求模型，循环直到 `stop_reason=end_turn`。
9. 触发 `Stop` hook，写一行 `summary` 进 jsonl，等待下一轮输入。
10. 退出时触发 `SessionEnd`，关闭 MCP 子进程、刷新 statsig 缓存。

---

## 18. 调试与观测

| 诉求 | 做法 |
|------|------|
| 看完整请求 | `CLAUDE_CODE_DEBUG=1 claude` 或 `--verbose` |
| 看 hook 日志 | hook 脚本自身写日志；`/hooks` 命令查看注册情况 |
| 看 MCP 启动错误 | `claude mcp list` / `MCP_TIMEOUT=30000` |
| 看 transcript | `claude --resume` 选择会话；或直接读 `~/.claude/projects/.../*.jsonl` |
| 看 token 用量 | `/cost`，或 transcript 中每条 `usage` |
| 健康检查 | `claude doctor` |

---

## 19. 实践建议

1. **先跑 `claude doctor`**，确认 Node、网络、credentials、MCP 都正常。
2. **通过 settings 分层管理权限**：
   - 用户级写默认 `defaultMode` / 通用 deny。
   - 项目共享 settings 写仓库相关 allow 列表与 hooks（提交进 git）。
   - `settings.local.json` 写个人临时偏好（gitignore）。
3. **CLAUDE.md 写“稳定的事实”**（构建命令、关键目录、约束），不写易变信息。
4. **大任务前显式 plan 模式**，让 Claude 先输出计划，避免自动执行破坏性操作。
5. **把 hook 当“合规层”**：自动屏蔽 `.env`、敏感目录、生产分支。
6. **MCP 优先于自写 shell 工具**：协议化、可重用、便于权限统一控制。
7. **会话长 > 30 轮**主动 `/compact` + 指定关注点，避免被自动压缩漂移。
8. **CI/容器**：用 `--print --output-format stream-json --max-turns N --dangerously-skip-permissions`，并通过环境变量注入 key。

---

## 20. 关键路径速查

| 想要做的事 | 改这里 |
|------------|--------|
| 全局禁某条命令 | `~/.claude/settings.json` 的 `permissions.deny` |
| 团队统一 hook | `<repo>/.claude/settings.json` + `<repo>/.claude/hooks/*` |
| 加自定义 slash 命令 | `<repo>/.claude/commands/<name>.md` |
| 加专用 reviewer 子代理 | `<repo>/.claude/agents/code-reviewer.md` |
| 接公司内部 API | `<repo>/.mcp.json` |
| 注入业务背景 | `<repo>/CLAUDE.md` + `@docs/*.md` |
| 自定义状态栏 | `~/.claude/settings.json` 的 `statusLine` |
| 改助手风格 | `~/.claude/output-styles/<name>.md` |
| 找上一次会话 | `~/.claude/projects/<escaped-cwd>/<uuid>.jsonl` |
| 重置凭据 | 删除 `~/.claude/.credentials.json` 后重新 `/login` |

---

> 本手册为底层实现速览；若需 API 字段最新细节，请以 docs.claude.com 为准。
