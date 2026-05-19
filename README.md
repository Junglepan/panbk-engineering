# panbk-engineering

> 个人工程知识库与配置工作空间

## 目录结构

```
.
├── knowledge/             # 知识库
│   ├── ai-agent/          #   AI Agent / Claude / MCP
│   ├── codex/             #   Codex CLI 迁移与分析
│   ├── networking/        #   网络与代理
│   └── incidents/         #   事故复盘
├── config/                # 配置库
│   ├── terminal/          #   终端工具 dotfiles (zsh, ghostty, yazi)
│   ├── claude/            #   Claude Code 配置与子代理
│   ├── codex/             #   Codex CLI 配置
│   └── config.yaml        #   工具依赖清单
├── scripts/               # 项目级工具脚本
└── CLAUDE.md              # Claude Code 项目指令
```

## 知识文档索引

### AI Agent

| 文档 | 主题 |
|------|------|
| [Claude 执行机制全景分析](knowledge/ai-agent/claude-execution-mechanics.md) | Claude Code 内部执行流程与机制拆解 |
| [MCP 基础全面理解](knowledge/ai-agent/mcp-fundamentals.md) | Model Context Protocol 原理与实践 |
| [小红书 MCP 架构与实现原理](knowledge/ai-agent/xiaohongshu-mcp.md) | 小红书 MCP 服务端实现分析 |
| [Tw93 Agent 总结](knowledge/ai-agent/tw93-agent.md) | Tw93 的 Agent 实践 |
| [Tw93 Claude 总结](knowledge/ai-agent/tw93-claude.md) | Tw93 的 Claude 使用经验 |

### Codex

| 文档 | 主题 |
|------|------|
| [迁移全面分析](knowledge/codex/migrate-analysis.md) | Claude Code 与 Codex 迁移对比 |
| [CC Steward Sync 对照](knowledge/codex/cc-steward-sync.md) | CC 与 Codex 管家模式对照 |
| [官方迁移思路](knowledge/codex/migrate-official-guide.md) | 官方迁移建议整理 |
| [本地会话结构](knowledge/codex/local-sessions-structure.md) | Codex CLI 会话存储结构分析 |

### 网络与代理

| 文档 | 主题 |
|------|------|
| [代理网络基础](knowledge/networking/proxy-basics/) | V2Ray / Clash 代理网络入门指南 |
| [V2Ray Shell 切换](knowledge/networking/v2ray-proxy-shell-switch.md) | 终端代理环境变量切换方案 |

### 事故复盘

| 文档 | 主题 |
|------|------|
| [V2RayN OAuth 事件](knowledge/incidents/v2rayn-oauth-2026-04-11.md) | V2RayN 与 Claude OAuth 冲突排查 |

## 快速开始

```bash
# 部署 dotfiles 到本地
./config/apply-dotfiles.sh

# 运行项目验证
./scripts/verify.sh
```

## License

MIT
