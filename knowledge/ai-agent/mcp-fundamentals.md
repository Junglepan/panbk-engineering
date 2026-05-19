---
title: MCP 全面理解：协议、架构与概念对比
date: 2026-04-16
tags: [mcp, agent, 协议]
status: complete
---

# MCP 全面理解：协议、架构与概念对比

> 日期：2026-04-16

---

## 一、MCP 是什么，为什么需要它

**MCP（Model Context Protocol）** 是 Anthropic 提出的开放标准协议，解决一个核心问题：

> AI 模型如何安全、标准化地调用外部世界的能力？

### 没有 MCP 之前的困境

每个 AI 应用都要自己实现工具集成：
- GitHub 插件 = 自定义代码
- 数据库查询 = 自定义代码
- 文件操作 = 自定义代码

工具与模型之间没有统一接口，**换一个模型或换一个工具，一切重写**。

### MCP 的解法

定义一套标准协议，让任意 MCP Server 可以接入任意支持 MCP 的 AI Client：

```
AI Client（Claude / Cursor / Gemini）
        ↕ MCP 协议（标准化）
MCP Server（GitHub / 数据库 / 小红书 / 任意工具）
```

类比：就像 USB 协议让任意设备可以接入任意电脑，MCP 让任意工具可以接入任意 AI。

---

## 二、MCP 核心架构：三个角色

```
┌──────────────────────────────────────┐
│           Host Application           │  ← 用户交互入口（Claude Desktop、Claude Code）
│  ┌────────────────────────────────┐  │
│  │         MCP Client             │  │  ← 协议实现层，管理与 Server 的连接
│  └──────────┬─────────────────────┘  │
└─────────────┼────────────────────────┘
              │ MCP Protocol
    ┌─────────┴──────────┐
    ▼                    ▼
MCP Server A        MCP Server B        ← 工具提供者（可以有多个）
（文件系统）         （小红书）
```

### Host
- 运行 AI 模型的宿主程序（如 Claude Desktop、Claude Code CLI）
- 负责展示界面、管理用户会话
- 可以同时连接多个 MCP Server

### MCP Client
- Host 内部的协议客户端
- 负责与 MCP Server 握手、发现工具、发送调用请求
- 一个 Client 对应一个 Server 连接

### MCP Server
- 独立运行的服务进程
- 暴露能力给 AI（Tools / Resources / Prompts）
- 可以是本地进程，也可以是远程 HTTP 服务

---

## 三、MCP 的三种原语（Primitives）

MCP Server 可以暴露三类能力，职责各不相同：

### 1. Tools（工具）—— 执行动作

> 让 AI **做事情**，有副作用，会改变外部状态。

```
特征：
- 有明确输入参数（JSON Schema 定义）
- 执行后有返回结果
- 可能有副作用（写文件、发请求、发帖子）
- AI 根据用户意图自主决定是否调用

例子：
- search_feeds(keywords)   → 搜索小红书笔记
- publish_content(...)     → 发布笔记
- bash(command)            → 执行 shell 命令
- create_file(path, content) → 创建文件
```

### 2. Resources（资源）—— 读取数据

> 让 AI **获取上下文**，只读，不改变状态。

```
特征：
- 类似"文件"或"数据库记录"，有唯一 URI
- AI 可以订阅变更（动态资源）
- 不执行操作，只提供数据

例子：
- file:///project/README.md  → 项目说明文档
- db://users/1234            → 数据库中某条记录
- config://app/settings      → 应用配置
```

### 3. Prompts（提示模板）—— 引导交互

> 预定义的**交互模式**，帮助用户快速触发特定工作流。

```
特征：
- 可带参数，生成定制化 prompt
- 由用户主动触发（不是 AI 自主调用）
- 类似"快捷指令"

例子：
- /summarize-pr → 生成 PR 总结的 prompt 模板
- /debug-error  → 填入错误信息，生成调试 prompt
```

### 三者对比

| 维度 | Tools | Resources | Prompts |
|------|-------|-----------|---------|
| 谁触发 | AI 自主决定 | AI 自主读取 | 用户主动触发 |
| 有无副作用 | 有 | 无（只读） | 无 |
| 类比 | 函数调用 | 文件读取 | 快捷指令模板 |

---

## 四、MCP 传输层：两种通信方式

### stdio（标准输入输出）
```
Host 进程 ──stdin/stdout──▶ MCP Server 进程（本地）

特点：
- 适合本地工具（文件系统、shell 命令）
- Server 由 Host 启动，随 Host 关闭
- 简单，无需网络，延迟最低
```

### HTTP（Streamable HTTP / SSE）
```
Host ──HTTP POST /mcp──▶ MCP Server（本地或远程）

特点：
- 适合远程服务或需要持久运行的服务
- 支持流式响应（SSE）
- xiaohongshu-mcp 用的就是这种（端口 18060）
```

---

## 五、工具调用的完整生命周期

```
1. 连接阶段（握手）
   Client → Server: initialize()
   Server → Client: 返回 capabilities（支持哪些原语）

2. 发现阶段
   Client → Server: tools/list()
   Server → Client: 返回所有 Tool 的名称 + 参数 Schema

3. 推理阶段（在 LLM 内部）
   Host 把 Tool 列表注入 system prompt
   用户输入 → LLM 判断：需要调用哪个 Tool，参数是什么

4. 执行阶段
   Client → Server: tools/call("search_feeds", {keywords: "护肤"})
   Server 执行实际逻辑（浏览器、API、数据库……）
   Server → Client: 返回结构化结果

5. 继续推理
   LLM 拿到结果，继续生成回复或决定下一步调用
```

---

## 六、核心对比：MCP Tool vs 内置 Tool vs Skill

这是理解 Claude 生态最容易混淆的三个概念。

### 内置 Tool（Claude Code 原生工具）

> Claude Code 硬编码内置的能力，**不走 MCP 协议**。

```
特征：
- 由 Anthropic 直接集成在 Claude Code 里
- 无需配置，开箱即用
- 执行在 Claude Code 进程内部

例子：
Read, Write, Edit, Bash, Grep, Glob,
WebSearch, WebFetch, Agent, ...
```

### MCP Tool（外部扩展工具）

> 通过 MCP 协议连接的**外部服务**暴露的工具。

```
特征：
- 运行在独立进程（本地或远程）
- 需要在配置文件中声明才能使用
- 可以由任何人开发和发布

例子：
xiaohongshu-mcp 的 search_feeds
GitHub MCP 的 create_issue
Postgres MCP 的 query_db

配置方式（~/.claude/settings.json）：
{
  "mcpServers": {
    "xiaohongshu": {
      "command": "xiaohongshu-mcp",
      "args": []
    }
  }
}
```

### Skill（技能/斜线命令）

> 预定义的**工作流指令**，本质是结构化的 prompt 或 instruction 文件。

```
特征：
- 不是可执行程序，是 markdown 格式的指令文档
- 用 /skill-name 触发，或通过 Skill tool 调用
- 引导 Claude 以特定方式完成特定任务
- 存放在 ~/.claude/skills/ 或项目 .claude/skills/

例子：
/review   → 按固定格式做代码审查
/security-review → 执行安全检查流程
/simplify → 对代码做简化重构

本质：高质量的 system prompt 片段，而不是工具
```

### 三者核心区别总结

| 维度 | 内置 Tool | MCP Tool | Skill |
|------|-----------|----------|-------|
| 本质 | 原生能力 | 外部服务接口 | 工作流指令 |
| 执行者 | Claude Code 进程 | 独立 MCP Server 进程 | Claude 模型本身 |
| 有副作用吗 | 有（Bash/Write） | 有 | 无（只引导行为） |
| 需要配置吗 | 不需要 | 需要注册 Server | 需要放置文件 |
| 谁来开发 | Anthropic | 任何人 | 任何人 |
| 类比 | 操作系统内置命令 | 第三方 CLI 工具 | Shell 脚本别名 |

### 三者的依赖深度

**内置 Tool** —— 依赖 Claude Code 安装本身，无需额外配置，权限可在 `settings.json` 中 allow/deny。

**MCP Tool** —— 依赖链最长，任意一环断掉工具即不可用：
```
1. MCP Server 进程必须在运行
   ↓
2. settings.json 里已注册该 Server
   ↓
3. Server 自身运行环境就绪
   （Go 二进制 / Python venv / Node.js / Docker）
   ↓
4. Server 依赖的外部资源可用
   （Cookie、API Key、数据库连接、网络……）
```

**Skill** —— 依赖一个 `.md` 文件存在于正确路径：
```
~/.claude/skills/review.md      ← 全局
.claude/skills/security.md     ← 项目级
```
无进程、无网络、无凭证，触发后全靠 Claude 模型自身推理执行。  
代价是**只能引导行为，不能直接操作外部系统**（除非 Skill 指令里调用了其他 Tool）。

**一句话总结依赖深度：**
```
内置 Tool  →  依赖 Claude Code 安装
MCP Tool   →  依赖运行中的外部进程 + 环境 + 凭证
Skill      →  依赖一个 markdown 文件
```

---

## 七、一个完整场景串联三者

**场景**：用户说"帮我搜索小红书的护肤帖子，总结后写入文档"

```
1. Claude 调用 MCP Tool（外部扩展）
   → search_feeds(keywords="护肤")
   → xiaohongshu-mcp Server 启动 Headless Chrome 执行搜索
   → 返回帖子列表

2. Claude 调用内置 Tool（原生能力）
   → Write("/tmp/summary.md", 总结内容)
   → 直接在本地写入文件

3. 如果用 /review Skill 审查输出
   → Skill 加载 review.md 的指令
   → Claude 模型按指令格式做内容审查
   → 没有任何工具调用，纯语言模型推理
```

---

## 八、注册到 Claude Code vs 独立启动的区别

MCP Server 有两种使用方式，区别在于**谁管理进程生命周期，以及 Claude 是否感知它的存在**。

### 独立启动（不注册）

```
你手动启动 Server 进程
Claude Code 不知道它存在
只能通过 REST /api/v1/* 直接调用（自己写脚本）
Claude 无法用自然语言触发它的工具
```

适合：把 MCP Server 当普通 HTTP API 用，自己写自动化脚本调用。

### 注册到 Claude Code MCP 配置

```json
// ~/.claude/settings.json
{
  "mcpServers": {
    "xiaohongshu": {
      "command": "xiaohongshu-mcp",  // stdio 模式：Claude Code 负责启停进程
      "args": []
      // 或 HTTP 模式：
      // "url": "http://localhost:18060/mcp"  进程仍需自己启动
    }
  }
}
```

注册后的变化：

| 能力 | 未注册 | 已注册 |
|------|--------|--------|
| Claude 感知 Tool 列表 | 否 | 是（对话开始时自动发现） |
| 自然语言触发工具 | 否 | 是 |
| 进程生命周期管理 | 手动 | Claude Code 托管（stdio 模式） |
| 权限管控 | 无 | 走 Claude Code allow/deny 体系 |

### stdio vs HTTP 注册方式的差异

- **stdio**：`"command"` 字段，Claude Code 负责启动/关闭 Server 进程，进程随会话生灭
- **HTTP**：`"url"` 字段，Server 进程独立常驻，Claude Code 只负责发请求，不管进程

**一句话总结：**
> 不注册 = 你手动调 HTTP 接口；注册了 = Claude 能自主调用，工具成为它能力的一部分。

---

## 九、MCP 生态现状

```
官方维护的 MCP Servers（Anthropic/Model-Context-Protocol）：
- filesystem    本地文件操作
- github        GitHub API
- postgres      PostgreSQL 查询
- brave-search  网页搜索
- slack         Slack 消息
- google-maps   地图查询

社区维护：
- xiaohongshu-mcp  小红书自动化
- mcp-obsidian     Obsidian 笔记
- mcp-linear       Linear 项目管理
- ...（数千个）

MCP Registry：
- mcp.so / glama.ai / smithery.ai 等聚合平台
```

---

## 九、关键认知总结

1. **MCP = AI 世界的 USB 协议**，解决 AI ↔ 工具的标准化互联问题
2. **三种原语职责分明**：Tools 执行动作、Resources 提供数据、Prompts 引导交互
3. **Tool ≠ Skill**：Tool 是可执行的程序接口；Skill 是引导模型行为的指令文本
4. **内置 Tool vs MCP Tool**：前者内置在 Claude Code，后者是外部进程，通过协议通信
5. **没有官方 API 也能做 MCP Server**，但复杂度转移到数据获取层（爬虫/浏览器自动化）
6. **MCP Server 本身开发简单**，官方提供 Python/TypeScript/Go SDK，几十行代码即可起步
