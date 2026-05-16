# Claude & Codex 本地会话文件结构与统计口径

日期：2026-05-16

本文总结 Claude Code 和 Codex CLI 本地会话文件的组成、JSONL 记录类型，以及统计会话指标时的口径差异。重点说明两家 Token 报告语义的根本不同，以及如何在工具中统一展示。

---

## 1. 文件位置与命名

### Claude Code

```text
~/.claude/projects/{project-slug}/{uuid}.jsonl
```

- `{project-slug}`：项目路径的编码形式，如 `-Users-panbk-Programmer-MyProject`
- `{uuid}.jsonl`：UUID 格式的文件名，即 native session ID，可用于 `claude --resume {uuid}`
- 跳过目录：`subagents/`、`memory/`、`worktrees/`、`node_modules/`
- 过滤条件：文件大小 ≥ 200 字节

### Codex CLI

```text
~/.codex/sessions/{year}/{month}/{day}/rollout-{timestamp}-{uuid}.jsonl
```

- 按日期目录组织
- 文件名包含创建时间戳和 UUID
- 一个 `.jsonl` 文件对应一个会话

---

## 2. JSONL 记录类型

### 2.1 Claude Code

每行是一条独立 JSON 记录，顶层 `type` 字段决定语义。

#### 可见消息类型

**`user`** — 用户消息

```json
{
  "type": "user",
  "uuid": "...",
  "sessionId": "...",
  "timestamp": "2026-05-16T01:00:00.000Z",
  "cwd": "/path/to/project",
  "message": {
    "content": "请帮我修复这个 bug" | [
      { "type": "text", "text": "..." },
      { "type": "tool_result", "tool_use_id": "toolu_xxx", "content": "..." }
    ]
  }
}
```

- `message.content` 可以是字符串或数组
- 数组中可包含 `tool_result` 块（工具执行结果）
- 常见顶层字段：`uuid`、`parentUuid`、`sessionId`、`cwd`、`gitBranch`、`entrypoint`、`version`

**`assistant`** — 模型响应

```json
{
  "type": "assistant",
  "uuid": "...",
  "timestamp": "2026-05-16T01:00:01.000Z",
  "message": {
    "model": "claude-sonnet-4-6",
    "content": [
      { "type": "text", "text": "我来看看这个问题" },
      { "type": "tool_use", "id": "toolu_xxx", "name": "Bash", "input": { "command": "pwd", "description": "..." } },
      { "type": "thinking", "thinking": "..." }
    ],
    "usage": {
      "input_tokens": 6,
      "output_tokens": 185,
      "cache_creation_input_tokens": 26222,
      "cache_read_input_tokens": 0
    }
  }
}
```

- `message.model`：模型名称，如 `claude-opus-4-7`、`claude-sonnet-4-6`；值为 `<synthetic>` 时跳过
- `message.content` 数组中的 block 类型：
  - `text`：文本输出
  - `tool_use`：工具调用（包含 `name`、`id`、`input`）
  - `thinking`：思维链（不展示为可见消息）
- `message.usage`：Token 用量（**关键差异点，见第 3 节**）
- 部分记录含 `message.usage.iterations[]`，其中的 token 值与顶层重复，不应重复计算

**工具调用与结果的关系：**

- `tool_use` 出现在 `assistant` 消息的 content 数组中
- `tool_result` 出现在后续 `user` 消息的 content 数组中
- 两者通过 `tool_use.id` / `tool_result.tool_use_id` 关联

**Skill 和 Subagent 识别：**

- Skill：`tool_use` block 中 `name === "Skill"`，从 `input.skill` 提取技能名
- Subagent：`tool_use` block 中 `name === "Agent"`，从 `input.subagent_type` 提取子代理类型

#### 系统消息类型

**`system`** — 系统事件，由 `subtype` 区分

```json
{ "type": "system", "subtype": "turn_duration", "durationMs": 39768, "messageCount": 34, "timestamp": "..." }
```

常见 subtype：
- `turn_duration`：轮次耗时（`durationMs` 字段），是耗时统计的唯一来源
- `stop_hook_summary`：hook 执行摘要
- `away_summary`：离开摘要
- `api_error`：API 错误
- `compact_boundary`：上下文压缩边界

#### 元数据类型（不计入可见消息）

以下类型在统计时完全跳过：

- `permission-mode`：权限模式切换
- `file-history-snapshot`：文件快照
- `attachment`：附件
- `ai-title`：AI 生成的标题
- `last-prompt`：上次提示
- `queue-operation`：队列操作
- `summary`：摘要
- `result`：结果

### 2.2 Codex CLI

每行是一条独立 JSON 记录，顶层 `type` 字段决定语义。

**`session_meta`** — 会话元信息

```json
{
  "timestamp": "2026-05-16T02:00:00.000Z",
  "type": "session_meta",
  "payload": { "id": "...", "cwd": "/path/to/project" }
}
```

**`turn_context`** — 回合上下文

```json
{
  "timestamp": "2026-05-16T02:00:01.000Z",
  "type": "turn_context",
  "payload": {
    "cwd": "/path/to/project",
    "model": "gpt-5.5",
    "collaboration_mode": { "settings": { "model": "gpt-5.5" } }
  }
}
```

- `payload.model` 是模型分布的可靠来源
- 注意 `collaboration_mode.settings.model` 重复了模型名，用 regex 全文匹配会导致双倍计数

**`event_msg`** — 事件消息，由 `payload.type` 区分

```json
// 用户消息
{ "type": "event_msg", "payload": { "type": "user_message", "message": "..." } }

// Agent 消息
{ "type": "event_msg", "payload": { "type": "agent_message", "message": "..." } }

// Token 统计
{
  "type": "event_msg",
  "payload": {
    "type": "token_count",
    "info": {
      "last_token_usage": {
        "input_tokens": 23332,
        "output_tokens": 240,
        "cached_input_tokens": 3456,
        "reasoning_output_tokens": 76,
        "total_tokens": 23572
      },
      "total_token_usage": { ... },
      "model_context_window": 200000
    }
  }
}
```

- `last_token_usage`：当次调用的 token 用量（**推荐使用**）
- `total_token_usage`：累计 token（不推荐，早期版本可能不存在）
- `last_token_usage` 可能为 `null`（会话首行），需做空值检查
- 其他 `payload.type`：`patch_apply_end`、`task_started`、`task_complete`、`web_search_end`、`turn_aborted` 等（不计入可见消息）

**`response_item`** — 模型响应和工具调用，由 `payload.type` 区分

```json
// 消息
{ "type": "response_item", "payload": { "type": "message", "role": "assistant", "content": [...] } }

// 普通工具调用
{ "type": "response_item", "payload": { "type": "function_call", "name": "exec_command", "call_id": "call-1", "arguments": "{\"cmd\":\"pwd\"}" } }

// 普通工具结果
{ "type": "response_item", "payload": { "type": "function_call_output", "call_id": "call-1", "output": "..." } }

// 自定义工具调用
{ "type": "response_item", "payload": { "type": "custom_tool_call", "name": "apply_patch", "call_id": "call-2", "input": "..." } }

// 自定义工具结果
{ "type": "response_item", "payload": { "type": "custom_tool_call_output", "call_id": "call-2", "output": "..." } }

// 推理（不展示为可见消息）
{ "type": "response_item", "payload": { "type": "reasoning" } }
```

---

## 3. Token 口径差异（核心知识点）

**这是两家最重要的差异，直接影响 UI 展示的可比性。**

### Claude (Anthropic API)

```json
{
  "input_tokens": 6,
  "output_tokens": 185,
  "cache_creation_input_tokens": 26222,
  "cache_read_input_tokens": 0
}
```

- `input_tokens`：**仅新增、未缓存的输入 token**（不含缓存命中和缓存创建）
- `cache_read_input_tokens`：从 prompt cache 读取的输入 token
- `cache_creation_input_tokens`：写入 prompt cache 的输入 token
- **实际总输入** = `input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens`

### Codex (OpenAI API)

```json
{
  "input_tokens": 23332,
  "output_tokens": 240,
  "cached_input_tokens": 3456,
  "reasoning_output_tokens": 76,
  "total_tokens": 23572
}
```

- `input_tokens`：**全部输入 token**（已包含缓存命中）
- `cached_input_tokens`：`input_tokens` 的子集，表示缓存命中部分
- `reasoning_output_tokens`：`output_tokens` 的子集，表示推理 token
- `total_tokens` = `input_tokens` + `output_tokens`

### 对照表

| 概念 | Claude 字段 | Codex 字段 |
|------|------------|-----------|
| 总输入 | `input_tokens + cache_creation + cache_read` | `input_tokens` |
| 新增输入（非缓存） | `input_tokens` | `input_tokens - cached_input_tokens` |
| 缓存读取/命中 | `cache_read_input_tokens` | `cached_input_tokens` |
| 缓存创建 | `cache_creation_input_tokens` | 无此字段 |
| 总输出 | `output_tokens` | `output_tokens` |
| 推理输出 | 无此字段 | `reasoning_output_tokens`（子集） |

### 统一展示口径

UI 展示时应统一为「总输入」口径：

- **输入 Token**：Claude = `input + cache_read + cache_creation`；Codex = `input`（原始值）
- **输出 Token**：两家均为 `output_tokens`（直接可比）
- **总 Token**：`输入 + 输出`
- **缓存命中**：Claude = `cache_read_input_tokens`；Codex = `cached_input_tokens`
- **缓存创建**：Claude = `cache_creation_input_tokens`；Codex = 无（展示 0）

不统一口径的后果：Claude 显示 input 0.06M（仅新增），Codex 显示 input 539M（含缓存），差距 9000 倍，误导用户以为 Codex 消耗远高于 Claude。统一后 Claude 828M / Codex 692M，同一量级，符合实际。

---

## 4. 指标统计口径

### 总会话

- Claude：统计 `~/.claude/projects/**/*.jsonl` 文件数（排除 subagents/memory/worktrees/node_modules 目录，排除 <200 字节文件）
- Codex：统计 `~/.codex/sessions/**/*.jsonl` 文件数

### 总消息（可见消息）

Claude 计入：
- `type === "user"` 且 content 非空
- `type === "assistant"` 且 content 非空（text/tool_use blocks）
- `tool_use` 和 `tool_result` blocks 分别拆为独立消息

Claude 不计入：
- `type` 属于元数据类型（permission-mode 等 8 种）
- `type === "system"`（turn_duration 等）
- `thinking` blocks

Codex 计入：
- `event_msg` 的 `user_message` 和 `agent_message`
- `response_item` 的 `message`（role 为 user/assistant 且内容非空）
- `response_item` 的 `function_call`、`function_call_output`、`custom_tool_call`、`custom_tool_call_output`

Codex 不计入：
- `session_meta`、`turn_context`、`compacted`
- `event_msg` 的 `token_count`、`patch_apply_end` 等
- `response_item` 的 `reasoning`
- developer/system 角色消息

### 工具调用次数

- Claude：统计 `tool_use` blocks 数量（不含 `tool_result`）
- Codex：统计 `function_call` + `custom_tool_call`（不含 `_output` 结果记录）
- 工具名称：Claude 从 `tool_use.name`；Codex 从 `payload.name`

### 模型分布

- Claude：从 `assistant` 消息的 `message.model` 提取，跳过 `<synthetic>`
- Codex：从 `turn_context` 的 `payload.model` 提取
- 注意：Codex 的 `turn_context` 中 `collaboration_mode.settings.model` 会重复模型名，用 regex 全文匹配会导致双倍计数，应改用 per-line JSON.parse 只取 `payload.model`

### Token 用量

- Claude：从 `assistant` 消息的 `message.usage` 提取（detail 层），或 regex per-line first-match 扫描（summary 层）
- Codex：从 `event_msg` 的 `token_count` → `info.last_token_usage` 提取
- 见第 3 节口径统一说明

### 耗时

- Claude：从 `system` 消息的 `subtype === "turn_duration"` 提取 `durationMs`，累加所有轮次
- Codex：**无可靠 duration 字段**，应展示 "—" 或 0

### 技能/子代理

- Claude：从 `tool_use` block 的 `input` 字段结构化提取——`name === "Skill"` 时取 `input.skill`；`name === "Agent"` 时取 `input.subagent_type`
- Codex：当前 JSONL 中无对应结构

---

## 5. 两层提取策略

为平衡性能和精度，采用两层提取：

| 层 | 用途 | 方法 | 数据来源 |
|---|---|---|---|
| Summary（列表） | 快速展示所有会话 | `fd.read` 只读前 1MB + regex 快扫 + 线性缩放 | `fastScanToolStats` |
| Detail（详情） | 单个会话完整信息 | `fs.readFile` 全量读取 + JSON.parse 每行 | `normalizeMessages` / `normalizeCodexRow` |

### Summary 层注意事项

- Claude 和 Codex 都只读前 1MB（`SCAN_LIMIT`），超出部分按比例缩放
- Token 统计：Claude 用 regex per-line first-match（避免 `usage.iterations[]` 重复）；Codex 用 per-line JSON.parse 提取 `last_token_usage`
- 工具统计：Claude 用 `"tool_use".*?"name":"xxx"` regex；Codex 用 `"function_call".*?"name":"xxx"` regex
- 模型统计：Claude 用全文 regex；Codex 必须 per-line JSON.parse `turn_context` 行（避免嵌套 model 字段重复计数）
- 缩放影响：工具/消息/token 统计可能因分布不均而有误差，但满足列表场景的精度需求

### Detail 层注意事项

- 全量 JSON.parse 保证精确
- `tool_use` / `tool_result` blocks 拆分为独立 `SessionMessage`
- `thinking` blocks 跳过
- Codex 的 `token_count` 事件转为不可见的 system 消息，携带 `tokenUsage` 字段
- Codex 的 `turn_context` 转为不可见的 system 消息，携带 `model` 字段

### 性能参考

- Claude 16 sessions / 33ms（文件较小，多数 <1MB）
- Codex 48 sessions / 111ms（含 85MB 大文件，限读 1MB 后）
- Codex 未优化前全量读取：1056ms

---

## 6. 会话 ID 体系

| ID 类型 | 生成方式 | 用途 |
|---------|---------|------|
| Session ID | `SHA1("agent:absolutePath")` | 稳定唯一标识，跨平台一致 |
| Native ID | Claude: 文件名中的 UUID；Codex: `session_meta.payload.id` | 用于 `claude --resume` 等原生命令 |

---

## 7. 实现注意事项

1. **Token 口径必须统一**：Claude 的 `input_tokens` 仅是新增部分，展示前需加上 `cache_creation` + `cache_read`，否则与 Codex 不可比。
2. **不要依赖 `total_token_usage`**：Codex 早期版本可能无此字段；即使存在也是累计值，不适合逐行求和。
3. **Codex `last_token_usage` 可为 null**：会话首行的 `token_count` 事件中此字段为 null，需做空值检查。
4. **Codex model 需 per-line 解析**：`turn_context` 行中 `collaboration_mode.settings.model` 与 `payload.model` 重复，全文 regex 会双倍计数。
5. **工具 TOP 需保留 count**：overview 聚合应累加工具的调用次数，而非统计「使用过该工具的会话数」。
6. **Codex 无 duration**：当前 JSONL 中没有 `turn_duration` 或等效字段，不应伪造，展示 "—"。
7. **`cached_input_tokens` 映射为缓存读取**：不是缓存创建；Codex 无缓存创建字段。
8. **Skill/Subagent 从结构化字段提取**：不要用 regex 匹配自然语言（如 `"Used Skill: xxx"`），会误匹配普通文本中的 "skill" 等词。应从 `tool_use` block 的 `input.skill` / `input.subagent_type` 字段精确提取。
9. **Summary 层性能优先**：大文件（85MB+）必须限读前 1MB + 缩放，全量读取会导致秒级延迟。
