---
title: 知识总览
date: 2026-05-19
tags: [索引]
status: complete
---

# 知识总览

个人技术知识库入口。按主题分类，持续更新。md 是源；运行 `scripts/verify.sh` 后会构建一份 HTML 镜像到 `dist/`，作为更友好的阅读视图。

## 学习路径

### 想理解 AI Agent 怎么工作？

1. [Claude Code 核心设计工程剖析](ai-agent/claude-code-core-design-analysis.md) — 从源码还原角度理解 Agent runtime、工具、权限、上下文和扩展机制
2. [Agent 使用、学习与知识化技术总结](ai-agent/agent-learning-knowledge-technical-summary.md) — 把 Agent 使用经验沉淀为任务、流程、技能和知识体系
3. [Claude Code 执行机制全景分析](ai-agent/claude-execution-mechanics.md) — 从底层理解 Claude Code 的会话、工具、权限、记忆机制
4. [MCP 全面理解](ai-agent/mcp-fundamentals.md) — Agent 与外部系统交互的协议标准
5. [小红书 MCP 架构](ai-agent/xiaohongshu-mcp.md) — MCP 的真实落地案例

### 想从 Claude Code 迁移到 Codex？

1. [迁移全面分析](codex/migrate-analysis.md) — 两个生态的整体对比
2. [CC Steward Sync 对照](codex/cc-steward-sync.md) — 管家模式差异详解
3. [官方迁移思路](codex/migrate-official-guide.md) — Codex 官方建议
4. [本地会话结构](codex/local-sessions-structure.md) — 会话存储层面的差异

### 想搞定网络代理问题？

1. [代理网络基础](networking/proxy-basics/) — 从零理解代理、机场、节点
2. [终端代理切换](networking/v2ray-proxy-shell-switch.md) — Shell 环境变量与代理的关系
3. [V2RayN OAuth 事件复盘](incidents/v2rayn-oauth-2026-04-11.md) — 代理导致 OAuth 失败的真实案例

## 按主题浏览

### AI Agent

| 文档 | 日期 | 标签 |
|------|------|------|
| [Claude Code 核心设计工程剖析](ai-agent/claude-code-core-design-analysis.md) | 2026-05-21 | `claude-code` `agent` `架构` |
| [Agent 使用、学习与知识化技术总结](ai-agent/agent-learning-knowledge-technical-summary.md) | 2026-05-21 | `agent` `大模型` `知识管理` |
| [Claude Code 执行机制](ai-agent/claude-execution-mechanics.md) | 2026-04-18 | `claude-code` `架构` |
| [Claude Code Stats 本地实现](ai-agent/claude-code-stats-internals.md) | 2026-05-26 | `claude-code` `架构` |
| [Claude Code /rename 实现](ai-agent/claude-code-rename-internals.md) | 2026-05-26 | `claude-code` `架构` |
| [MCP 全面理解](ai-agent/mcp-fundamentals.md) | 2026-04-16 | `mcp` `协议` |
| [小红书 MCP 架构](ai-agent/xiaohongshu-mcp.md) | 2026-04-16 | `mcp` `架构` |
| [Tw93 Agent 实践](ai-agent/tw93-agent.md) | 2026-03-21 | `agent` `阅读笔记` |
| [Tw93 Claude 经验](ai-agent/tw93-claude.md) | 2026-03-12 | `claude-code` `阅读笔记` |

### Codex

| 文档 | 日期 | 标签 |
|------|------|------|
| [迁移全面分析](codex/migrate-analysis.md) | 2026-05-12 | `codex` `迁移` |
| [CC Steward Sync 对照](codex/cc-steward-sync.md) | 2026-05-15 | `codex` `迁移` |
| [官方迁移思路](codex/migrate-official-guide.md) | 2026-05-15 | `codex` `迁移` |
| [本地会话结构](codex/local-sessions-structure.md) | 2026-05-16 | `codex` `会话` |

### 网络与代理

| 文档 | 日期 | 标签 |
|------|------|------|
| [代理网络基础](networking/proxy-basics/) | 2026-05-16 | `代理` `网络` |
| [V2Ray Shell 切换](networking/v2ray-proxy-shell-switch.md) | 2026-04-18 | `v2ray` `终端` |

### 事故复盘

| 文档 | 日期 | 标签 |
|------|------|------|
| [V2RayN OAuth 事件](incidents/v2rayn-oauth-2026-04-11.md) | 2026-04-11 | `v2ray` `oauth` `故障复盘` |

## 标签索引

| 标签 | 相关文档数 |
|------|-----------|
| `claude-code` | 7 |
| `mcp` | 2 |
| `agent` | 5 |
| `codex` | 4 |
| `迁移` | 3 |
| `v2ray` | 3 |
| `代理` | 2 |
| `阅读笔记` | 2 |
| `大模型` | 1 |
| `知识管理` | 1 |
| `故障复盘` | 1 |

---

## 目录结构约定

| 路径 | 角色 |
|---|---|
| `README.md` | 知识库入口（本文件），承担总览 + 学习路径 + 主题表格 |
| `_meta/template.md` | 新文档骨架，供作者复制使用 |
| `<topic>/<doc>.md` | 单文件主题，最常见形态 |
| `<topic>/<doc>/README.md` + `<doc>/assets/` | 目录形态主题，当一篇笔记需要 ≥1 附件（图、附文）时升级 |
| `incidents/` | 事故复盘；累计 ≥3 篇时按 `incidents/YYYY/MM-DD-slug.md` 重组 |
| `dist/` | 由 `scripts/build-html.py` 生成的 HTML 镜像，不要手改 |

新增笔记的步骤：复制 [_meta/template.md](_meta/template.md) → 改 frontmatter → 写正文 → 在本文件对应分类表格里加一行 → 运行 `scripts/verify.sh` 重建 HTML。
