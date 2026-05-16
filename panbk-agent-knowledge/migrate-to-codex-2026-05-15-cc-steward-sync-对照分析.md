# migrate-to-codex 与 ClaudeCodex-Together 同步逻辑对照分析

日期：2026-05-15  
对象：

- `/Users/panbk/.codex/skills/migrate-to-codex`
- `/Users/panbk/Programmer/ClaudeCodex-Together`

## 一句话结论

Codex 的 `migrate-to-codex` 是一个面向 Claude Code -> Codex 的“静态扫描、结构化转换、风险报告、目标校验、自愈复查”迁移器。`ClaudeCodex-Together` 当前同步中心确实是基于这套迁移思想实现的，但更像一个轻量产品化子集：它保留了扫描、计划、dry-run、执行的用户流程，也覆盖了 instructions、skills、subagents、commands 的基础识别；但还没有完全继承官方 migrator 的 artifact/report 模型、MCP/hooks/settings 转换、subagent TOML 输出、`.agents/skills` 目标路径、validator 和 manual-review 闭环。

因此，当前同步中心可以作为可视化迁移入口，但如果目标是“和 Codex migrate-to-codex 行为对齐”，还需要补齐语义转换与验证层。

## migrate-to-codex 的核心模型

本地 skill 文件：`/Users/panbk/.codex/skills/migrate-to-codex/SKILL.md`

它定义的迁移顺序是：

1. 使用任务列表跟踪迁移步骤。
2. 阅读 `references/differences.md`。
3. 先 `--scan-only`、`--plan`、`--doctor`，再写入。
4. 按固定顺序转换：
   - instructions
   - plugins report
   - hooks
   - skills and slash commands
   - config and MCP
   - subagents
5. dry-run 后真实写入。
6. 检查 `.codex/migrate-to-codex-report.txt`。
7. 按 `AGENTS.md`、`.agents/skills/`、`.codex/config.toml`、`.codex/hooks.json`、`.codex/agents/` 顺序复查。
8. 运行 `--validate-target`。
9. 修复 generated artifact 后再次 dry-run / validate。

关键点：它不是一次性 copy 工具，而是一个迁移闭环。它把“能自动写入”和“必须人工复核”同时编码进输出。

## 源码结构与职责

迁移器核心入口在：

- `scripts/migrate-to-codex.py`
- `scripts/cli.py`

转换模块在：

- `scripts/migrate/instructions.py`
- `scripts/migrate/skills.py`
- `scripts/migrate/codex_config.py`
- `scripts/migrate/mcps.py`
- `scripts/migrate/hooks.py`
- `scripts/migrate/agents.py`
- `scripts/migrate/plugins.py`
- `scripts/migrate/common.py`

其中 `common.py` 是设计核心。它定义了统一迁移模型：

- `ConversionResult`：一次转换的汇总结果。
- `MigrationSummary`：统计数量，例如 instructions、skills、subagents、MCP servers。
- `PlannedArtifact`：准备写入的目标 artifact。
- `GeneratedText`：生成文本。
- `SourceCopy`：复制源文件。
- `SourceSymlink`：创建 symlink。
- `MigrationReportItem`：迁移报告项。

这个模型的价值是：每个 surface 只负责“生成计划和报告”，不直接写文件；真正写入由 `cli.py` 的部署层统一处理。

## 各 surface 的迁移规则

### Instructions

来源候选：

- `.claude/CLAUDE.md`
- `CLAUDE.md`
- `claude.md`
- `AGENTS.md`

目标：

- `AGENTS.md`

如果内容不含明显 Claude-only 标记，迁移器会倾向于 symlink 到源文件，避免重复维护。Claude-only 标记包括 `/hooks`、`.claude/agents/`、`.claude/settings`、`Subagent`、`permissionMode`、`ExitPlanMode` 等。

如果发现 Claude-only 语义，则生成 Codex 专用副本，并追加 `## MANUAL MIGRATION REQUIRED`，提醒清理 hooks、slash commands、subagent、permission mode 等假设。

### Skills 与 Slash Commands

Claude skills 来源：

- `.claude/skills/<name>/SKILL.md`
- `.claude/skills/<name>.md`

目标：

- `.agents/skills/<name>/SKILL.md`

目录型 skill 的 `scripts/`、`references/`、`assets/` 会被复制。

Claude slash commands 来源：

- `.claude/commands/*.md`

目标：

- `.agents/skills/source-command-<name>/SKILL.md`

slash command 会被包装成 Codex skill，但 `$ARGUMENTS`、`$1`、`{{var}}`、``!`command` ``、`@file` 等运行时展开语义会保留为 manual-review 文本，不假装等价。

### MCP 与 config

来源：

- `.mcp.json`
- `.claude.json`
- `.claude/settings.json`
- `.claude/settings.local.json`

目标：

- `.codex/config.toml`

迁移器会把 Claude MCP server 转成 `[mcp_servers.<name>]`，并处理一部分环境变量和 header 形式：

- `Authorization: Bearer ${VAR}` -> `bearer_token_env_var`
- `${VAR}` header -> `env_http_headers`
- 静态 header -> `http_headers`
- `${VAR}` env self-reference -> `env_vars`
- 字面量 env -> `env`

它也会把部分 model / permissionMode 映射为 Codex 的 `model` / `sandbox_mode`，并在生成 config 时加入 `personality = "friendly"`。

### Hooks

来源：

- `~/.claude/settings.json`
- `.claude/settings.json`
- `.claude/settings.local.json`

目标：

- `.codex/hooks.json`
- `.codex/config.toml` 中 `[features].codex_hooks = true`

支持的 Codex hook event：

- `PreToolUse`
- `PostToolUse`
- `SessionStart`
- `UserPromptSubmit`
- `Stop`

但行为不是 1:1。Codex 只执行 command handler，跳过 async / prompt / agent handler；`PreToolUse` / `PostToolUse` 当前主要面向 shell command；部分 matcher 会被忽略。因此 hooks 转换一般都需要人工复核。

### Subagents

来源：

- `.claude/agents/*.md`

目标：

- `.codex/agents/*.toml`

迁移器会把 Claude frontmatter 转成 Codex custom-agent TOML：

- `name` -> `name`
- `description` -> `description`
- `model` -> Codex model family mapping
- `effort` -> `model_reasoning_effort`
- `permissionMode: acceptEdits` -> `sandbox_mode = "workspace-write"`
- `permissionMode: readOnly` -> `sandbox_mode = "read-only"`
- agent body -> `developer_instructions`

Claude 的 `skills`、`tools`、`disallowedTools` 不会变成硬权限，只会保留为 `developer_instructions` 里的提示，并生成 manual-review 报告。

### Plugins

Claude plugins 和 marketplaces 只报告，不自动迁移：

- `.claude/plugins/`
- `.claude/plugin-marketplaces.json`
- `.claude-plugin/marketplace.json`

原因是 Claude plugin 可能包含 commands、agents、MCP、hooks、skills、marketplace metadata 等多种 provider-specific 结构。迁移器把它们列为 manual follow-up，不复制 plugin tree。

## ClaudeCodex-Together 当前同步逻辑

当前实现已迁到 Electron 后端：

- `electron/backend/sync.ts`
- `electron/backend/agents.ts`
- `electron/backend/config.ts`
- `electron/backend/files.ts`
- 前端入口：`src/modules/sync/SyncCenter.tsx`

同步中心的产品流程是：

1. scan：扫描 Claude 侧配置。
2. plan：展示转换计划和统计。
3. dry-run：模拟写入。
4. execute：执行写入。

这和 `migrate-to-codex` 的体验模型一致。

### 当前已继承的思想

1. 分 global / project scope。
2. 先扫描，再计划，再 dry-run，再写入。
3. 指令迁移到 `AGENTS.md`。
4. skills、agents、commands 作为不同 item 分类展示。
5. 对风险项使用 `check` / warnings 标注。
6. 不直接改 Claude source path。
7. 默认不覆盖已存在目标，除非 replace / overwrite。

### 当前实现的简化点

`electron/backend/sync.ts` 目前是手写轻量 converter，不是直接调用官方 migrator。

主要差异：

| 领域 | migrate-to-codex | ClaudeCodex-Together 当前实现 |
| --- | --- | --- |
| 统一模型 | `ConversionResult` + `PlannedArtifact` + `MigrationReportItem` | `items` + `actions` 简化模型 |
| instructions | neutral 时可 symlink，Claude-only 时追加 manual block | 直接复制内容，只用 slash command 正则给 warning |
| skills 目标 | `.agents/skills/<name>/SKILL.md` | 当前写到 `.codex/skills/<name>.md` |
| skill support dirs | 复制 `scripts/`、`references/`、`assets/` | 未复制 |
| slash commands | 转为 `.agents/skills/source-command-<name>/SKILL.md` | 标记 unsupported，不迁移 |
| subagents | 写 `.codex/agents/<name>.toml` | 当前写 `.codex/agents/<name>.md` |
| subagent 权限 | model/effort/permissionMode/tools/skills 部分映射或 manual guidance | 只保留 `tools` 注释 |
| MCP | `.mcp.json` / `.claude.json` -> `.codex/config.toml` | 未实现 |
| hooks | 部分转 `.codex/hooks.json` 并启用 `codex_hooks` | 未实现，且 `unsupportedHooks` 常量未进入 makeItems 流程 |
| plugins | report manual migration | 未扫描/报告 |
| report file | 写 `.codex/migrate-to-codex-report.txt` | 未生成 |
| validator | `--validate-target` 校验 TOML、skills、agents、AGENTS.md size、MCP command | 未实现等价校验 |
| merge/replace | merge 保留孤儿；replace 删除 orphan generated skills/agents | replace 只控制是否覆盖目标文件，不清理 orphan |

## 对当前项目的关键风险判断

### 1. Codex skills 路径不一致

官方 migrate-to-codex 把 Codex skills 写到：

```text
.agents/skills/<name>/SKILL.md
```

当前 `sync.ts` 写到：

```text
.codex/skills/<name>.md
```

但 `agents.ts` 中 Codex 文件定义仍展示 `.codex/skills/`，这和本地 Codex skill 规范存在潜在不一致。若要与 migrate-to-codex 对齐，应优先确认当前 Codex CLI 实际读取路径，然后统一 UI、resolver、writer、sync 目标。

### 2. Codex subagent 文件格式不一致

官方 migrator 输出：

```text
.codex/agents/<name>.toml
```

当前同步中心输出：

```text
.codex/agents/<name>.md
```

而 `electron/backend/config.ts` 的 `resolveCodex()` 用 `.toml` 后缀扫描 agents。这意味着同步写出的 agent 和解析视图可能不一致。这个是当前最值得优先修正的结构差异。

### 3. 当前同步中心缺少 manual-review artifact

官方 migrator 的核心不是“警告文字”，而是把 manual guidance 写进生成文件，例如：

```text
## MANUAL MIGRATION REQUIRED
```

当前实现主要把 warning 放在 UI item 上。这样用户执行同步后，风险信息不一定随 artifact 留存。对长期配置管理来说，manual guidance 应该写入目标文件或迁移报告。

### 4. 当前 dry-run 没有 validator 语义

当前 dry-run 只告诉用户哪些路径会写入、哪些会跳过。官方 `--validate-target` 会检查：

- `.codex/config.toml` TOML parseability
- skill frontmatter
- custom-agent TOML 必需字段
- `AGENTS.md` 大小阈值
- MCP command 是否在 PATH

如果同步中心要接近 migrate-to-codex，应该新增“写入后验证”或至少“计划阶段静态验证”。

## 建议的实现演进顺序

### 第一优先级：修正目标路径和格式

1. skills 迁移目标对齐 `.agents/skills/<name>/SKILL.md`。
2. commands 转成 Codex skills，而不是直接 unsupported。
3. subagents 输出 `.codex/agents/<name>.toml`。
4. resolver 与 UI 同步显示这些路径。

### 第二优先级：引入 report/manual-review 模型

1. 在 `sync.ts` 中把 `items/actions` 扩展为接近 `ConversionResult` 的结构。
2. 每个 action 携带 `status`、`manualReview`、`warnings`。
3. 执行后生成 `.codex/migrate-to-codex-report.txt` 或产品自有 report。
4. 对 Claude-only semantics 写入目标 artifact 的 manual block。

### 第三优先级：补 MCP/hooks/settings

1. 读取 `.mcp.json` / `.claude.json`。
2. 生成 `.codex/config.toml` 的 MCP server table。
3. 支持 bearer/env/header 映射。
4. 读取 `.claude/settings.json` hooks。
5. 生成 `.codex/hooks.json`，并启用 `[features].codex_hooks = true`。

### 第四优先级：加入 validator

1. 校验 TOML parse。
2. 校验 skill frontmatter。
3. 校验 agent TOML 必需字段。
4. 校验 AGENTS.md size。
5. 校验 MCP command 是否在 PATH。

## 对产品定位的总结

`ClaudeCodex-Together` 不需要完全复制 `migrate-to-codex` 的 CLI 行为，但应该继承它的三个原则：

1. **迁移不是复制**：每个 provider 差异都必须显式表达。
2. **风险必须留痕**：manual-review 不能只停留在 UI，一旦写入目标，风险也要进入目标文件或报告。
3. **验证是迁移的一部分**：dry-run 只证明路径计划，不证明生成物能被 Codex 使用。

当前同步逻辑已经具备可视化迁移流程的外壳。下一步应该把官方 migrator 的“artifact/report/validator”内核逐步移植进来。

## 可复用知识点

后续修改同步中心时，可以把官方 migrator 抽象成这几个概念：

```text
scan source surfaces
  -> convert each surface into planned artifacts
  -> attach report items and manual-review caveats
  -> dry-run planned writes
  -> write artifacts
  -> validate target
  -> report residual manual work
```

最小可落地的数据模型：

```ts
interface PlannedArtifact {
  kind: 'file' | 'skill' | 'agent' | 'config' | 'hook'
  target: string
  content?: string
  sourceCopy?: string
  sourceSymlink?: string
  status: 'added' | 'check' | 'not_added'
  notes: string
  manualReview: string[]
}
```

这个模型比当前 `WriteAction { target, content }` 更接近真实迁移需求，也能支撑 UI 展示、dry-run、execute、report 和 validate。

