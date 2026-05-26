---
title: Claude Code /rename 会话改名的底层实现
date: 2026-05-26
tags: [claude-code, 架构, 会话, rename]
status: complete
---

# Claude Code /rename 会话改名的底层实现

> 适用对象：想理解 Claude Code 会话标题如何生成、存储、检索的人
> 证据来源：对本机 Claude Code `2.1.150` 单文件二进制(`/opt/claude-code/bin/claude`)的字符串反查 + 本地 `~/.claude/` 会话文件核对
> 标注约定：函数/变量名来自压缩产物,仅作行为描述,不代表源码真实命名

Claude Code 支持给会话起一个**人类可读的标题**,既能在启动时用 `--name` 指定,也能在会话进行中用 `/rename` 改名。本文拆解它的底层实现,核心结论先行:**`/rename` 与 `--name` 最终都落到同一个内部工具 `rename_session`,把标题以 `custom-title` 记录持久化进会话 transcript,再驱动 prompt box、`/resume` 选择器与终端标签页标题**;未命名时由 `rename_generate_name` 基于首个有意义提问自动生成标题。

> [!NOTE]
> 常见误解:以为只有 `--name` 命令行参数、没有斜杠命令。实际上 `/rename` 是真实存在的会话内命令,二进制里能直接搜到 `/rename`、`/rename <name>`、`Rename the current conversation` 等字符串。两者的区别只是触发时机:`--name` 在启动时设定,`/rename` 在会话进行中改名。

## 两个入口

| 入口 | 形态 | 帮助/描述文案 |
|---|---|---|
| `--name <name>` / `-n` | CLI 启动参数 | "Set a display name for this session (shown in the prompt box, /resume picker, and terminal title)" |
| `/rename [name]` | 会话内斜杠命令 | "Rename the current conversation" |

`/rename` 的引导文案还包括:

- "/rename to add a name"
- "/rename to find them easily in /resume later"
- "/rename to tell them apart at a glance"

即改名的产品目的是:让会话在 `/resume` 选择器里**可搜索、可区分**。

## 底层工具：rename_session

两个入口最终都调用一个内部工具 `rename_session`:

```
rename_session({ title: string })
// 描述: "Sets the user-facing title for the current session."
// 校验: title.trim() 非空,否则报 "title must be non-empty"
```

实现要点(均为二进制字符串确证):

1. **入参 schema**:`{ title: y.string() }`(zod),处理时先 `title.trim()`。
2. **空值校验**:`trim` 后为空直接拒绝,错误信息 `title must be non-empty`。
3. **上下文依赖**:需要 UI 注册了 `onRenameSession` 回调才能用;否则报错
   `rename_session is not supported in this context (onRenameSession callback not registered)`。
   ——这解释了为什么非交互/某些嵌入场景下无法改名。

> [!TIP]
> `rename_session` 是工具化的,意味着模型自身也能在合适时机发起改名(例如对话主题切换后),而不只是用户手动敲 `/rename`。

## 自动命名：rename_generate_name

未显式命名时,标题由自动生成器产出,标记为 `querySource: "rename_generate_name"`:

- 生成一个"topic title"(主题式标题)。
- 取材:`First meaningful user prompt in the session`(会话中**首个有意义的用户提问**),并结合 Git 信息(如分支)。
- `/rename` 或 `--name` 的作用就是用用户输入**覆盖**这个自动标题。

## 持久化

标题落盘在会话 transcript(JSONL)里,与 Stats 用的是同一套存储:

```
~/.claude/projects/<编码后的项目路径>/<sessionId>.jsonl
```

标题记录格式(实测,通常位于文件首行):

```json
{ "type": "custom-title", "customTitle": "<用户提供的名字>", "sessionId": "<uuid>" }
```

相关函数/字段符号:

| 符号 | 行为 |
|---|---|
| `custom-title` / `customTitle` | transcript 中的标题记录类型与字段 |
| `saveCustomTitle` | 写入/更新标题记录 |
| `searchSessionsByCustomTitle` | `/resume` 选择器按标题搜索 |
| `isCustomTitleEnabled` | 标题特性开关判定 |
| `customTitles` | 标题集合(批量读取) |

## 配置开关：terminalTitleFromRename

一个布尔配置控制改名是否同步到终端标签页标题:

- `terminalTitleFromRename`(**默认 `true`**):`/rename` 会更新终端标签页标题。
- 设为 `false`:保留**自动生成的 topic title**,不让手动改名覆盖终端标题。

文案原文:"`/rename` updates the terminal tab title (defaults to true). Set to false to keep auto-generated topic titles."

## 边界与遥测

**Swarm 协作场景**会拒绝改名:

```
Cannot rename: This session is a swarm teammate. Teammate names are set by the team leader.
```

即作为团队队友(teammate)的会话,名字由 leader 统一指派,不可自行改名。

**遥测事件**(`tengu_*`):

| 事件 | 触发时机 |
|---|---|
| `tengu_session_rename_started` | 发起改名 |
| `tengu_session_renamed` | 改名完成 |
| `tengu_rename_full_session_fork` | 改名涉及 fork 整段会话时 |

## 数据流总览

```
用户敲 /rename foo   ──┐
启动加 --name foo    ──┤──▶ rename_session({title:"foo"})
模型自动改名          ──┘            │ trim + 非空校验
                                     ▼
                          saveCustomTitle 写入 transcript
                          {type:"custom-title", customTitle:"foo", sessionId}
                                     │
              ┌──────────────────────┼───────────────────────┐
              ▼                      ▼                        ▼
        prompt box 显示      /resume 选择器               终端标签页标题
                       (searchSessionsByCustomTitle)  (受 terminalTitleFromRename 控制)

未命名 ──▶ rename_generate_name 基于"首个有意义提问"+Git 生成 topic title
```

## 总结

- `/rename`(会话内)与 `--name`(启动时)是同一能力的两个入口,底层统一走内部工具 `rename_session`,入参 `title`,空值即拒。
- 标题以 `custom-title` 记录持久化进 `~/.claude/projects/**/<sessionId>.jsonl`,与 Stats 共用同一套本地 transcript 存储。
- 标题影响三处展示:prompt box、`/resume` 选择器(可搜索)、终端标签页标题(后者受 `terminalTitleFromRename` 开关控制)。
- 未命名时由 `rename_generate_name` 基于首个有意义提问 + Git 信息自动生成主题标题;手动改名只是覆盖它。
- 边界:swarm 队友会话不可自行改名;非交互上下文因缺少 `onRenameSession` 回调而不支持。
