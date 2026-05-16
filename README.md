# panbk-engineering

> 个人工程知识库与 AI Agent 配置工作空间

## 目录结构

```
.
├── panbk-agent-config/    # Agent 配置与终端工具 dotfiles
│   ├── claude/            # Claude Code 配置与子代理
│   ├── codex/             # Codex CLI 配置
│   ├── terminal/          # Ghostty / Zsh / Yazi 配置
│   └── scripts/           # 环境部署脚本
├── panbk-agent-knowledge/ # 技术知识文档
├── scripts/               # 项目级工具脚本
└── CLAUDE.md              # Claude Code 项目指令
```

## 知识文档索引

### Claude Code & Agent

| 文档 | 主题 |
|------|------|
| [Claude 执行机制全景分析](panbk-agent-knowledge/claude-execution-mechanics-2026-04-18-全景分析.md) | Claude Code 内部执行流程与机制拆解 |
| [Codex 本地会话结构与统计口径](panbk-agent-knowledge/codex-local-sessions-2026-05-16-结构与统计口径.md) | Codex CLI 会话存储结构分析 |
| [迁移到 Codex — 全面分析](panbk-agent-knowledge/migrate-to-codex-2026-05-12-全面分析.md) | Claude Code 与 Codex 迁移对比 |
| [迁移到 Codex — CC Steward Sync 对照](panbk-agent-knowledge/migrate-to-codex-2026-05-15-cc-steward-sync-对照分析.md) | CC 与 Codex 管家模式对照 |
| [迁移到 Codex — 官方思路总结](panbk-agent-knowledge/migrate-to-codex-2026-05-15-官方思路总结.md) | 官方迁移建议整理 |
| [MCP 基础全面理解](panbk-agent-knowledge/mcp-fundamentals-2026-04-16-全面理解.md) | Model Context Protocol 原理与实践 |
| [小红书 MCP 架构与实现原理](panbk-agent-knowledge/xiaohongshu-mcp-2026-04-16-架构与实现原理.md) | 小红书 MCP 服务端实现分析 |

### 网络与代理

| 文档 | 主题 |
|------|------|
| [代理网络基础](panbk-agent-knowledge/proxy-network-basics/) | V2Ray / Clash 代理网络入门指南 |
| [V2Ray 代理 Shell 切换总结](panbk-agent-knowledge/v2ray-proxy-shell-switch-2026-04-18-总结.md) | 终端代理环境变量切换方案 |
| [V2RayN OAuth 事件复盘](panbk-agent-knowledge/claude-v2rayn-oauth-incident-2026-04-11-复盘.md) | V2RayN 与 Claude OAuth 冲突排查 |

## 快速开始

```bash
# 部署 dotfiles 到本地
./panbk-agent-config/scripts/apply-dotfiles.sh

# 运行项目验证
./scripts/verify.sh
```

## License

MIT
