---
title: Codex 迁移全面分析
date: 2026-05-12
tags: [codex, 迁移, claude-code]
status: complete
---

# migrate-to-codex 全面分析

日期：2026-05-12  
对象：`/Users/panbk/.codex/skills/migrate-to-codex`

## 一句话定位

`migrate-to-codex` 是一个把 Claude Code 生态中的配置、指令、skills、slash commands、subagents、MCP 与部分 hooks 迁移到 Codex 生态的本地迁移器。它的本质不是“完全自动等价转换”，而是“静态扫描 + 结构化转换 + 风险标注 + 验证”的迁移辅助工具。

它能自动迁移结构明确、语义接近的内容；对运行时语义不同、权限边界不同、生命周期不同、插件体系不同的内容，它会保留为 Codex 可见的提示或报告项，并要求人工复核。

## 目的与作用

### 主要目的

1. 降低 Claude Code 用户迁移到 Codex 的人工成本。
2. 把分散在 `.claude/`、`.mcp.json`、`.claude.json`、`CLAUDE.md` 等位置的配置转换为 Codex 可识别的文件。
3. 在可转换与不可转换之间划清边界，避免伪装成 1:1 迁移。
4. 生成迁移报告，让使用者知道哪些项目已经写入、哪些项目需要人工检查。
5. 通过 `--validate-target` 检查迁移后的 Codex 目标目录是否至少在格式层面可用。

### 实际价值

它适合用作迁移的第一步：快速盘点现有 Claude Code 资产，批量生成 Codex 版本的基础文件，然后由人或 agent 继续修复语义差异。

它不适合直接作为“无人值守的最终迁移器”。尤其是权限、hooks、slash command 参数展开、插件、子代理运行模型等部分，迁移结果必须复核。

## 总体架构

项目目录按职责拆分：

```text
migrate-to-codex/
├── SKILL.md
├── references/
│   └── differences.md
├── agents/
│   └── openai.yaml
└── scripts/
    ├── migrate-to-codex.py
    ├── cli.py
    ├── migrate/
    │   ├── common.py
    │   ├── instructions.py
    │   ├── skills.py
    │   ├── codex_config.py
    │   ├── mcps.py
    │   ├── hooks.py
    │   ├── agents.py
    │   ├── plugins.py
    │   └── settings.py
    └── utils/
        ├── scan.py
        └── util.py
```

### 模块职责

| 模块 | 职责 |
| --- | --- |
| `SKILL.md` | 定义 agent 使用该迁移器时的操作流程、顺序、报告格式与自愈循环。 |
| `references/differences.md` | 记录 Claude Code 与 Codex 的迁移差异、可映射项、部分映射项和不支持项。 |
| `scripts/migrate-to-codex.py` | 入口文件，只负责引入 `cli.main()`。 |
| `scripts/cli.py` | CLI 编排层：解析参数、选择组件、扫描、规划、部署、报告、校验。 |
| `migrate/common.py` | 共享数据模型、frontmatter 解析、报告模型、路径常量、模型/权限映射。 |
| `migrate/instructions.py` | 将 `CLAUDE.md` / `claude.md` / `AGENTS.md` 迁移为 Codex `AGENTS.md`。 |
| `migrate/skills.py` | 将 Claude skills 和 slash commands 转成 Codex skills。 |
| `migrate/codex_config.py` | 生成 `.codex/config.toml`，整合模型、沙箱、MCP、hooks feature flag。 |
| `migrate/mcps.py` | 读取 `.mcp.json` / `.claude.json`，转换 MCP server 表。 |
| `migrate/hooks.py` | 将部分 Claude hooks 转成 `.codex/hooks.json`。 |
| `migrate/agents.py` | 将 `.claude/agents/*.md` 转成 `.codex/agents/*.toml`。 |
| `migrate/plugins.py` | 只报告 Claude plugins / marketplaces 需要人工迁移，不自动复制。 |
| `utils/scan.py` | 渲染源目录资产清单与迁移面清单。 |
| `utils/util.py` | JSONC、简化 YAML frontmatter、TOML 渲染、slug 等通用工具。 |

## 底层实现原理

### 1. 迁移面抽象

迁移器把 Claude Code 资产拆成几个 surface：

1. instructions
2. plugins
3. hooks
4. skills and commands
5. config and MCP
6. subagents

`cli.convert_scope()` 以固定顺序调用各 surface 的转换函数，并把结果汇总为统一的 `ConversionResult`。

统一结果包含三类信息：

| 数据 | 含义 |
| --- | --- |
| `summary` | 数量统计，例如 skills、subagents、MCP server 数量。 |
| `artifacts` | 准备写入 Codex 目标目录的文件、复制项或 symlink。 |
| `report_items` | 报告项，说明已转换、需要人工复核或不支持。 |

这个设计的关键是：转换阶段只生成计划和内容，不直接写文件。真正写入由部署阶段统一处理。

### 2. Artifact 模型

迁移输出统一表达为 `PlannedArtifact`：

| payload 类型 | 行为 |
| --- | --- |
| `GeneratedText` | 写入新生成的文本内容。 |
| `SourceCopy` | 从源文件复制到目标路径。 |
| `SourceSymlink` | 在目标位置创建指向源文件的 symlink。 |

这让不同 surface 可以用同一种方式输出目标文件。例如：

1. `AGENTS.md` 可以是 symlink，也可以是生成文本。
2. skill 支持文件可以是 `SourceCopy`。
3. `.codex/config.toml` 是 `GeneratedText`。
4. `.codex/agents/*.toml` 是 `GeneratedText`。

### 3. 扫描、规划、部署分离

CLI 提供四类主要模式：

| 模式 | 作用 |
| --- | --- |
| `--scan-only` | 只列出源目录中存在的支持项，不需要 target。 |
| `--plan` | 生成迁移计划，列出阶段、目标 artifact 和人工复核项，但不写文件。 |
| `--doctor` | 评估迁移就绪度，统计人工复核、冲突、孤儿文件风险。 |
| 普通运行 / `--dry-run` | 执行或模拟执行迁移，并输出 summary、inventory、surface 和 report。 |
| `--validate-target` | 验证已有 Codex 目标目录的格式和基本可用性。 |

这个分层让迁移过程更安全：

1. 先扫描源资产。
2. 再看迁移计划。
3. 再做 dry-run。
4. 确认后写入目标目录。
5. 最后验证目标目录。

### 4. Scope 处理

迁移器支持两种 source shape：

1. 单 scope：例如 `--source ~/.claude/ --target ~/.codex/` 或项目内 `./.claude/ -> ./.codex/`。
2. tree scope：如果 source 下同时有 `global/` 和 `project/`，会分别转换为 target 下的 `global/` 与 `project/`。

内部用 `ScopePaths(source, is_global)` 表示 scope。全局 scope 和项目 scope 在 instruction 候选文件上略有不同：项目 scope 不从 `.claude/CLAUDE.md` 读取 instruction 候选。

### 5. merge 与 replace 策略

默认部署模式是 `merge`：

1. 写入计划中的 artifact。
2. 保留目标目录中未被本次计划覆盖的旧 skills / agents。

`--replace` 会额外删除孤儿生成物：

1. `.agents/skills/*` 中本次计划没有生成的 skill 目录。
2. `.codex/agents/*.toml` 中本次计划没有生成的 agent 文件。

这使得 `merge` 更保守，`replace` 更接近“目标目录等于源目录映射结果”。

## 各内容范围与转换策略

## 1. Instructions

### 支持的来源

候选文件：

1. `.claude/CLAUDE.md`
2. `CLAUDE.md`
3. `claude.md`
4. `AGENTS.md`

目标：

```text
AGENTS.md
```

### 转换策略

如果源文件是 `AGENTS.md`，迁移器认为 Codex instruction 已存在，只写报告，不覆盖自己。

如果源文件是 Claude instruction，迁移器检查内容是否包含明显 Claude-only 标记：

```text
/hooks
.claude/agents/
.claude/settings
Subagent
subagent
permissionMode
ExitPlanMode
```

没有这些标记时，生成 `AGENTS.md` symlink，复用同一份 instruction。

有这些标记时，生成一份 `AGENTS.md` 文本副本，并追加：

```text
## MANUAL MIGRATION REQUIRED
```

提示用户清理 Claude hooks、slash commands、subagent、permission mode 等假设。

### 设计思路

这个策略很保守：provider-neutral instruction 用 symlink 减少重复；一旦发现 Claude-only 语义，就断开 symlink，避免 Codex 直接继承不适配的行为描述。

## 2. Skills 与 Slash Commands

### 支持的来源

Claude skills：

```text
.claude/skills/<name>/SKILL.md
.claude/skills/<name>.md
```

Claude slash commands：

```text
.claude/commands/**/*.md
```

目标：

```text
.agents/skills/<name>/SKILL.md
.agents/skills/source-command-<name>/SKILL.md
```

### Skill 转换

目录型 skill 会迁移：

```text
SKILL.md
scripts/
references/
assets/
```

单文件 `.md` legacy skill 只转成一个 `SKILL.md`，不会复制 sibling 支持目录。

Codex skill frontmatter 只保留：

```yaml
name: ...
description: ...
```

Claude `allowed-tools` 不会变成 Codex 权限边界，只作为提示文字追加到 `MANUAL MIGRATION REQUIRED` 中。

其他 Claude skill 字段也会进入人工复核报告，例如：

```text
user-invocable
model
effort
disable-model-invocation
argument-hint
context
agent
hooks
paths
shell
```

### Slash Command 转换

每个 `.claude/commands/**/*.md` 会变成一个 Codex skill，命名规则类似：

```text
source-command-<path-parts>
```

例如：

```text
.claude/commands/review/pr.md
```

可能变成：

```text
.agents/skills/source-command-review-pr/SKILL.md
```

slash command 的 body 会被保留在 `## Command Template` 中。

迁移器会检测以下 provider-specific 行为并标记人工复核：

| 行为 | 风险 |
| --- | --- |
| `$ARGUMENTS` / `$1` | Codex 不自动按 Claude slash command 方式展开参数。 |
| `{{name}}` | 模板变量只作为文本保留。 |
| ``!`command` `` | shell 输出插值不会自动执行。 |
| `@path` | 自动文件引用展开需要改写成显式读取指令。 |
| unsupported frontmatter | 需要人工确认是否可转为 Codex skill 指令。 |

### 设计思路

skills 是最适合自动迁移的内容，因为它们本质上是 prompt + 辅助文件。slash commands 则不同：它们依赖调用语法和运行时展开，所以迁移器只把它们包成 Codex skill，并明确要求人工改写调用语义。

## 3. MCP 与 `.codex/config.toml`

### 支持的来源

```text
.mcp.json
.claude.json
.claude/settings.json
.claude/settings.local.json
```

目标：

```text
.codex/config.toml
```

### 迁移内容

从 Claude settings 中读取：

| Claude 字段 | Codex 字段 |
| --- | --- |
| `model` | `model`，按模型族映射。 |
| `permissionMode` | `sandbox_mode`，仅部分映射。 |
| `enabledMcpjsonServers` | 影响每个 MCP server 的 `enabled`。 |
| `disabledMcpjsonServers` | 影响每个 MCP server 的 `enabled = false`。 |
| `hooks` | 如果有可转换 hooks，则写 `[features].codex_hooks = true`。 |

从 `.mcp.json` / `.claude.json` 读取：

```json
{
  "mcpServers": {
    "name": {
      "command": "...",
      "args": [],
      "env": {},
      "url": "...",
      "headers": {}
    }
  }
}
```

转为：

```toml
personality = "friendly"

[mcp_servers.name]
command = "..."
args = [...]
```

只要生成 config，迁移器会加入：

```toml
personality = "friendly"
```

这是为了让从 Claude Code 迁移来的使用体验更接近原本偏友好的风格。

### MCP headers 与 env 映射

| Claude 形态 | Codex 形态 |
| --- | --- |
| `headers.Authorization = "Bearer ${TOKEN}"` | `bearer_token_env_var = "TOKEN"` |
| `headers.X-Key = "${KEY}"` | `env_http_headers = { "X-Key" = "KEY" }` |
| 静态 headers | `http_headers` |
| `env.KEY = "${KEY}"` | `env_vars = ["KEY"]` |
| 静态 env | `env` |

`${VAR:-default}` 这类 fallback 不会保留 default 语义，只能抽取变量名。

### MCP 限制

| 内容 | 处理方式 |
| --- | --- |
| `type: sse` | Codex 当前不支持，标记人工复核。 |
| `oauth.clientId`、`headersHelper` 等 | unsupported field，标记人工复核。 |
| `allowedMcpServers` / `deniedMcpServers` | 不写入，需人工转为 policy。 |
| `.claude/settings.local.json` | 没有完全等价的 Codex local-only 项。 |

## 4. Hooks

### 支持的来源

```text
.claude/settings.json
.claude/settings.local.json
```

目标：

```text
.codex/hooks.json
.codex/config.toml 中的 [features].codex_hooks = true
```

### 支持的事件

迁移器只转换以下事件：

```text
PreToolUse
PostToolUse
SessionStart
UserPromptSubmit
Stop
```

只有这些事件中的 `type: "command"` hook 会被写入。`prompt`、`agent`、`http`、`async: true` 等都会跳过并标记人工复核。

### matcher 规则

Codex 只对以下事件保留 matcher：

```text
PreToolUse
PostToolUse
SessionStart
```

`UserPromptSubmit` 和 `Stop` 中的 matcher 会被忽略并标记人工复核。

Claude `if` 条件不迁移。

### 运行时差异

hooks 是高风险迁移面。即使成功生成 `.codex/hooks.json`，也不能代表行为等价。

重要差异：

1. Codex hooks 需要显式开启 `[features].codex_hooks = true`。
2. 当前 Codex `PreToolUse` / `PostToolUse` 主要面向 shell command。
3. Claude 的一些生命周期事件没有 Codex 等价项。
4. `Notification` 不等于 Codex `notify`，迁移器不会直接转换。
5. async、HTTP、agent/prompt 类型 hooks 不自动迁移。

## 5. Subagents

### 支持的来源

```text
.claude/agents/*.md
```

目标：

```text
.codex/agents/*.toml
```

### 基本转换

Claude subagent frontmatter 和 body 会转成 Codex custom agent TOML：

```toml
name = "..."
description = "..."
model = "..."
model_reasoning_effort = "..."
sandbox_mode = "workspace-write"
developer_instructions = """..."""
```

如果缺少 `name`，迁移器从文件名推断。

如果缺少 `description`，迁移器从第一个 Markdown heading 或文件名推断。

这些推断字段会被纳入人工复核。

### 模型映射

| Claude 模型前缀 | Codex 模型 |
| --- | --- |
| `claude-opus` | `gpt-5.4` |
| `claude-sonnet` | `gpt-5.4-mini` |
| `claude-haiku` | `gpt-5.4-mini` |

effort 映射：

| Claude family | low | medium | high | max |
| --- | --- | --- | --- | --- |
| opus | low | medium | high | xhigh |
| sonnet | medium | high | xhigh | xhigh |
| haiku | low | medium | high | xhigh |

sonnet 被整体提高一个 reasoning tier，是为了更贴近 coding-agent 场景。

### 权限映射

| Claude `permissionMode` | Codex `sandbox_mode` |
| --- | --- |
| `acceptEdits` | `workspace-write` |
| `readOnly` | `read-only` |

其他 `permissionMode` 不自动映射，会进入 `MANUAL MIGRATION REQUIRED`。

### prompt guidance 保留

Claude subagent 的以下字段不能作为硬权限迁移：

```text
skills
tools
disallowedTools
```

迁移器会把它们写入 `developer_instructions` 中，作为 prompt guidance。例如：

```text
You're allowed to use these tools:
- Read

Don't use these tools:
- Bash
```

但这不是 Codex 的权限边界。若需要硬限制，需要人工配置 sandbox、permissions、MCP tool filters 或 app tool filters。

### 不支持或高风险项

包括：

```text
mcpServers
hooks
memory
background
isolation
maxTurns
initialPrompt
```

这些行为和 Codex custom-agent 的运行模型不等价，迁移器不会自动转换。

## 6. Plugins

### 支持的来源

迁移器会检测：

```text
.claude/plugins
.claude/plugin-marketplaces.json
.claude-plugin/marketplace.json
```

### 转换策略

插件不自动迁移，只生成 manual review 报告项。

原因是 Claude Code plugins 可能包含：

1. commands
2. agents
3. MCP servers
4. skills
5. hooks
6. marketplaces
7. output styles
8. provider-specific metadata

Codex plugin 的结构和 manifest 不同，不能安全复制目录树。

## 命令与工作流

入口命令：

```bash
python3 /Users/panbk/.codex/skills/migrate-to-codex/scripts/migrate-to-codex.py
```

常用变量：

```bash
MIGRATE_TO_CODEX='python3 .codex/skills/migrate-to-codex/scripts/migrate-to-codex.py'
```

### 推荐迁移顺序

```bash
$MIGRATE_TO_CODEX --source ~/.claude/ --scan-only
$MIGRATE_TO_CODEX --source ~/.claude/ --target ~/.codex/ --plan
$MIGRATE_TO_CODEX --source ~/.claude/ --target ~/.codex/ --doctor
$MIGRATE_TO_CODEX --source ~/.claude/ --target ~/.codex/ --dry-run
$MIGRATE_TO_CODEX --source ~/.claude/ --target ~/.codex/
$MIGRATE_TO_CODEX --validate-target ~/.codex/
```

项目级迁移：

```bash
$MIGRATE_TO_CODEX --source ./.claude/ --target ./.codex/ --dry-run
$MIGRATE_TO_CODEX --source ./.claude/ --target ./.codex/
$MIGRATE_TO_CODEX --validate-target ./.codex/
```

只迁移部分组件：

```bash
$MIGRATE_TO_CODEX --source ./.claude/ --target ./.codex/ --skills
$MIGRATE_TO_CODEX --source ./.claude/ --target ./.codex/ --mcp
$MIGRATE_TO_CODEX --source ./.claude/ --target ./.codex/ --subagents
```

默认不传组件参数时迁移：

```text
mcp
skills
subagents
```

instructions、hooks、plugins 的报告/转换由 scope 转换流程处理，不属于 `DEFAULT_COMPONENTS` 的选择集。

## 验证能力

`--validate-target` 做的是静态验证，不是运行时验证。

检查内容：

| 目标 | 验证 |
| --- | --- |
| `.codex/config.toml` | TOML 可解析。 |
| MCP command | command 是否在 `PATH` 上。 |
| `.agents/skills/*/SKILL.md` | frontmatter 是否有 `name` 和 `description`。 |
| `.codex/agents/*.toml` | TOML 可解析，且有 `name`、`description`、`developer_instructions`。 |
| `AGENTS.md` | 文件大小是否低于 32KB review threshold。 |

这不能证明：

1. MCP server 一定能启动。
2. hooks 行为与 Claude 等价。
3. slash command 迁移后的 skill 可按原方式调用。
4. 子代理权限被硬性限制。
5. 插件完成迁移。

## 核心策略总结

### 策略 1：能结构化转换的就生成 Codex 原生文件

例如：

1. `.mcp.json` -> `.codex/config.toml`
2. `.claude/agents/*.md` -> `.codex/agents/*.toml`
3. `.claude/skills/*` -> `.agents/skills/*`

### 策略 2：语义不等价时保留提示，但标记人工复核

例如：

1. `allowed-tools`
2. slash command 参数展开
3. shell interpolation
4. agent tool allow/deny
5. unsupported MCP 字段

这些会进入 `MANUAL MIGRATION REQUIRED` 或 report item。

### 策略 3：高风险 provider runtime 行为不假装迁移成功

例如：

1. plugins
2. async hooks
3. HTTP hooks
4. Notification hooks
5. subagent background/isolation/maxTurns
6. source provider 的 marketplace

迁移器只报告，不自动复制。

### 策略 4：先计划，后写入

所有转换先生成 `ConversionResult` 和 `DeploymentPlan`，再由部署阶段统一写文件。这样可以支持：

1. `--plan`
2. `--doctor`
3. `--dry-run`
4. collision 检测
5. orphan cleanup
6. migration report 写入

### 策略 5：报告驱动的自愈循环

`SKILL.md` 要求 agent 按循环处理：

1. `--plan` 或 `--doctor`
2. `--dry-run`
3. 正式迁移
4. 修复生成文件中的 `MANUAL MIGRATION REQUIRED`
5. `--validate-target`
6. 重新运行迁移器与 validator，直到没有可处理的 generated-artifact 问题

## 可适配内容范围

### 自动化程度较高

| 内容 | 适配程度 | 说明 |
| --- | --- | --- |
| provider-neutral instructions | 高 | 可 symlink 到 `AGENTS.md`。 |
| 普通 Claude skills | 高 | prompt 与支持目录可迁移。 |
| MCP stdio/http 基础配置 | 中高 | command、args、url、env、headers 可迁移。 |
| 基础 subagent prompt | 中高 | 可转为 Codex custom-agent TOML。 |
| model / effort | 中 | 按模型族做启发式映射。 |
| `acceptEdits` / `readOnly` | 中 | 可映射为 Codex sandbox。 |

### 需要人工复核

| 内容 | 原因 |
| --- | --- |
| slash commands | 参数、模板、文件引用、shell 插值运行时不等价。 |
| `allowed-tools` | Codex skill 没有同等硬权限字段。 |
| subagent `tools` / `disallowedTools` | 只能保留为 prompt guidance。 |
| subagent `skills` | Codex 没有相同的 spawn-time preload 语义。 |
| hooks | 生命周期和匹配范围不同。 |
| MCP auth fallback | `${VAR:-default}` default 语义不保留。 |
| instruction 中 Claude-only 描述 | 需要人工改写为 Codex 语义。 |

### 不自动迁移

| 内容 | 原因 |
| --- | --- |
| Claude plugins | Codex plugin manifest 和布局不同。 |
| plugin marketplaces | 不自动 fetch、install 或转换 marketplace。 |
| unsupported hook events | Codex 没有对应生命周期。 |
| HTTP/prompt/agent/async hooks | 当前转换器只写 command hooks。 |
| subagent background/isolation/maxTurns | Codex custom-agent 文件不表达等价运行模型。 |
| `.claude/settings.local.json` 的 local-only 语义 | Codex 项目配置信任模型不同。 |

## 迁移报告语义

报告项常见 status：

| status | 含义 |
| --- | --- |
| `rewritten` | 已生成或重写 Codex-facing artifact。 |
| `manual_fix_required` | 已生成或发现相关内容，但需要人工复核。 |
| `symlinked` | 目标通过 symlink 连接到源文件。 |
| `overwritten` | 目标已有 Codex artifact，将被覆盖。 |
| `would_delete` / `deleted` | `--replace` 下孤儿 artifact 将被或已被删除。 |
| `ok` | validator 检查通过。 |
| `warning` | validator 或报告发现非致命风险。 |
| `error` | validator 发现格式或必需字段错误。 |

正式迁移后报告写入：

```text
.codex/migrate-to-codex-report.txt
```

## 设计优点

1. **边界清晰**：能迁移、部分迁移、不能迁移分别处理。
2. **可审计**：每个 artifact 和 report item 都可追踪。
3. **安全默认**：默认 merge，不删除未计划的旧 artifact。
4. **格式验证**：至少能发现 TOML、frontmatter、必需字段问题。
5. **保留上下文**：不支持字段不会静默丢失，而是变成人工复核提示。
6. **模块化**：每类迁移面有独立模块，扩展成本较低。

## 设计局限

1. **不是语义等价迁移器**：无法证明运行时行为一致。
2. **YAML 解析是简化实现**：只覆盖 frontmatter 常见子集，不是完整 YAML parser。
3. **MCP JSON 读取不统一支持 JSONC**：settings 读取支持 JSONC，但 `.mcp.json` / `.claude.json` 使用 `json.loads`，注释或 trailing comma 可能失败。
4. **权限迁移偏提示化**：很多 Claude 权限字段只能放入 prompt guidance。
5. **hooks 迁移风险高**：Codex hook runtime 范围和 Claude 不同。
6. **plugins 只报告**：插件体系需要人工迁移。
7. **validation 是静态的**：不能替代真实运行测试。

## 实践建议

### 推荐使用方式

1. 先只跑 `--scan-only` 了解资产范围。
2. 再跑 `--plan` 看会生成哪些文件。
3. 用 `--doctor` 判断人工复核量和风险。
4. 用 `--dry-run` 看完整报告。
5. 正式迁移后，先读 `.codex/migrate-to-codex-report.txt`。
6. 逐个搜索 `MANUAL MIGRATION REQUIRED`。
7. 修复后运行 `--validate-target`。
8. 对 MCP、hooks、subagents 做实际运行验证。

### 复核重点

优先检查这些内容：

1. `.codex/config.toml`
2. `.codex/hooks.json`
3. `.codex/agents/*.toml`
4. `.agents/skills/source-command-*/SKILL.md`
5. 所有 `MANUAL MIGRATION REQUIRED`
6. `.codex/migrate-to-codex-report.txt`

### 何时用 `--replace`

只有在你明确希望目标 Codex skills / agents 与源 Claude assets 保持同步，并且确认目标中没有手工维护的 Codex artifact 时，才使用 `--replace`。

否则使用默认 `merge`。

## 结论

`migrate-to-codex` 的核心思想是：不要把跨 agent 平台迁移伪装成简单文件复制。它通过静态转换把能安全映射的部分落到 Codex 原生文件中；对不能安全映射的部分，保留上下文、写入人工复核块、生成报告，并要求验证。

它的最佳定位是“迁移加速器”和“迁移审计器”，不是“完全自动兼容层”。真正可靠的迁移流程应当是：

```text
scan -> plan -> doctor -> dry-run -> migrate -> review manual blocks -> validate -> runtime test
```

只要按这个流程使用，它可以显著减少重复迁移工作，同时避免把 Claude Code 运行时语义误带入 Codex。
