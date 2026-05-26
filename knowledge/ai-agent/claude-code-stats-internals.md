---
title: Claude Code Stats 标签页的本地实现原理
date: 2026-05-26
tags: [claude-code, 架构, stats, 本地优先]
status: complete
---

# Claude Code Stats 标签页的本地实现原理

> 适用对象：想理解 Claude Code 数据分层、或想离线复刻一份用量看板的人
> 证据来源：对本机 `@anthropic-ai/claude-code@2.1.42` 的 `cli.js` 反查 + 本地 `~/.claude/` 文件结构核对
> 标注约定：函数/变量名来自压缩产物,仅作行为描述,不代表源码真实命名

Claude Code 的 Stats 标签页(`/usage` 面板里的 Stats 子页)展示会话热力图、token 总量、连击天数等行为统计。本文逐指标拆解其底层实现,核心结论先行:**整张 Stats 面板 100% 由本地会话 transcript 计算得出,不调用任何服务端接口**,与隔壁服务端权威的 Usage 标签形成鲜明对照。

## 背景：Stats 在产品里的位置

顶部标签栏为 `Settings · Status · Config · Usage · Stats`,Stats 下有 `Overview` 与 `Models` 两个子页。Overview 呈现:

- GitHub 式贡献热力图(周一/三/五行 × 月份列,`Less … More` 分桶)
- 时间范围切换:`All time · Last 7 days · Last 30 days`(按 `r` 循环)
- 汇总卡:Favorite model、Total tokens、Sessions、Active days、Most active day、Longest session、Longest streak、Current streak
- 一句趣味对比(如 "longest session ~366x longer than a World Cup soccer match")
- 交互:`r` 切时间范围、`ctrl+s` 复制

> [!NOTE]
> Stats 与 Usage 是两类不同的数据。Stats = 你本地记录的**历史行为分析**;Usage = 服务端权威的**账户配额利用率**(5h/周滚动窗口)。前者全本地,后者全服务端,两者没有重叠地带。

## 数据存储层

所有原料是 Claude Code 写在磁盘上的会话 transcript:

```
~/.claude/projects/<编码后的项目路径>/<sessionId>.jsonl   # 每行一条消息记录
~/.claude/history.jsonl                                  # 命令历史
~/.claude/stats-cache.json                               # 聚合结果缓存(cache version = 2)
```

每个 `.jsonl` 文件对应一个会话,文件名即 `sessionId`。每行是一条 JSON 记录,实测字段:

```
cwd, entrypoint, gitBranch, isSidechain, message, parentUuid,
permissionMode, promptId, sessionId, timestamp, type, userType, uuid, version
```

统计真正依赖的关键字段:

| 字段 | 用途 |
|---|---|
| `timestamp` | 活跃天、连击、最长会话、热力图、时间范围过滤 |
| `sessionId`(= 文件名) | 会话计数、按会话分组算时长 |
| `message.model` | Favorite model、按模型分账 |
| `message.usage` | token 累加:`input_tokens` / `output_tokens` / `cache_creation_input_tokens` / `cache_read_input_tokens` |
| `type` | 区分消息类型,过滤无效行 |

## 聚合管线

核心是一个聚合函数(压缩符号 `of1(files, opts)`),输入是一批 session 文件路径,输出一个统计对象:

```
{ totalSessions, totalMessages, totalDays, activeDays,
  streaks, dailyActivity, dailyModelTokens, longestSession,
  modelUsage, firstSession… }
```

实现要点(均为代码确证):

1. **分批并发读取**:文件按每批 20 个(`M=20`)切片,`Promise.all` 并发解析,避免一次性打开过多文件。
2. **基于 mtime 的跳读优化**:若指定了 `fromDate`,先 `stat(file)` 取 `mtime`,文件修改时间早于范围起点则直接 `skipped`,不读内容。这让 `Last 7 days` 这类查询不必解析全部历史文件。
3. **逐行解析与校验**:对每行用谓词(`rI`)判断是否有效记录,无效行丢弃;读失败的文件记日志后跳过,不让单个坏文件拖垮整体。
4. **缓存**:结果写入 `stats-cache.json`,带版本号(`= 2`),版本不匹配(`version !== …`)即失效重算;配合文件 `mtimeMs` 判断增量。

> [!TIP]
> 这套"扫本地文件 + mtime 跳读 + 版本化缓存"的设计,正是它能瞬时切换 All time / Last 7/30 days 且离线可用的原因。

## 逐指标拆解

| 指标 | 底层算法 | 本地可算 |
|---|---|---|
| **热力图** | `dailyActivity`:按 `timestamp` 的日期聚合活跃量,渲染成日历网格,`Less…More` 为强度分桶 | ✅ |
| **Favorite model** | `modelUsage`:按 `message.model` 计数/计 token,取 argmax | ✅ |
| **Total tokens** | 累加每条记录 `usage` 的 input+output+cache 各项 | ✅ |
| **Sessions** | `totalSessions`:distinct `sessionId`(即 `.jsonl` 文件数) | ✅ |
| **Active days** | `activeDays = Set(活跃日期).size`;分母 `totalDays = ceil((末时间戳 − 首时间戳) / 86400000) + 1` | ✅ |
| **Most active day** | `dailyActivity` 取活跃量最大的日期 | ✅ |
| **Longest session** | 同一 `sessionId` 内 `max(timestamp) − min(timestamp)` 的最大值 | ✅ |
| **Longest / Current streak** | 连击函数扫连续活跃日期,返回 `{currentStreak, longestStreak, currentStreakStart, longestStreakStart, longestStreakEnd}` | ✅ |
| **All time / Last 7/30 days** | 对同一批本地记录做日期区间过滤(配合 mtime 跳读) | ✅ |
| **趣味对比** | 见下节,纯展示层 | ✅ |

> [!WARNING]
> `Longest session: 22d 21h 15m` 这类超长值是按会话首末时间戳之差算的,代表会话被长期挂起/空置,**不是真实在线交互时长**。同理 token 数是当初 API 响应回填进 transcript 的历史值,不是实时重算。

## 趣味对比的实现

末尾那句"比 X 长/短多少倍"是一张**硬编码的对照表**,用 `longestSession` 的分钟数去匹配:

```
a TED talk            18min     an episode of The Office   22min
listening to Abbey Road 47min   a yoga class               60min
a World Cup soccer match 90min  a half marathon           120min
the movie Inception  148min     watching Titanic          195min
a transatlantic flight 420min   a full night of sleep     480min
```

纯本地、纯展示,无任何外部依赖。

## 本地 vs 服务端边界

| | Stats 标签 | Usage 标签 |
|---|---|---|
| 数据源 | 本地 `~/.claude/projects/**/*.jsonl` | 服务端 `GET /api/oauth/usage` + `anthropic-ratelimit-unified-*` 响应头 |
| 缓存 | `stats-cache.json`(磁盘) | 无磁盘缓存,仅内存 |
| 离线 | 可用 | 不可用 |
| 口径 | 本机所有会话的历史行为 | 账户跨所有设备的滚动配额 |

本地 transcript 只记录**这台机器的消耗**,看不到手机/网页端/其他项目的用量,也不知道服务端的窗口边界与重置点——这就是 Usage 必须走服务端、而 Stats 能全本地的根本原因。

## 可复刻性

Stats 的全部指标都能离线重建,只要解析 `~/.claude/projects/**/*.jsonl`:

- 按 `sessionId` 分组 → 会话数、最长会话
- 按 `timestamp` 日期去重 → 活跃天、连击、热力图
- 累加 `message.usage` → token 总量、按模型分账
- 按 `message.model` 计数 → Favorite model

注意需复刻聚合器的两个工程细节才能高效:**mtime 跳读**(避免全量解析)与**版本化缓存**。

## 总结

- Stats 标签页是一个**本地优先(local-first)**的分析视图:原料是已落盘的会话 transcript,经分批解析 + 版本化缓存聚合而成,完全不依赖服务端。
- 逐指标看,热力图、token、会话数、活跃天、连击、最长会话、Favorite model、趣味对比**无一例外可纯本地计算**。
- 它与服务端权威的 Usage 标签构成清晰分层:历史行为分析归本地,实时配额状态归服务端。
- 据此可以用本仓库的 md→html 流水线,自建一份离线用量看板。
