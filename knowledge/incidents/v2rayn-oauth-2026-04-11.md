---
title: V2RayN 与 Claude OAuth 冲突排查复盘
date: 2026-04-11
tags: [v2ray, claude-code, oauth, 故障复盘]
status: complete
---

# Claude + v2rayN 连接与认证故障复盘（2026-04-11）

## 1. 事件摘要

本次故障并非单点问题，而是「代理端口配置」「本地网关配置」「OAuth 回调链路」叠加导致。

主要报错：
- `Unable to connect to API (UND_ERR_SOCKET)`
- `401 Invalid API key`
- `OAuth error: protocol mismatch`

核心结论：
- `UND_ERR_SOCKET` 是网络层（socket）问题。
- `401` 是认证层问题。
- `protocol mismatch` 是 OAuth 回调协议链路问题，通常与本地网关/代理改写有关。

## 2. 错误类型与定位结果

### 2.1 `UND_ERR_SOCKET`
含义：Claude 进程到目标地址（代理或 API）建连失败。

本次证据：
- 环境变量曾指向 `127.0.0.1:7890`
- 但本机实际监听的是 `127.0.0.1:10808`（v2rayN）

因此：配置指向了不存在的代理端口，导致 socket 失败。

### 2.2 `401 Invalid API key`
含义：HTTP 请求到了服务端，但鉴权失败。

本次高关联因素：
- 曾存在 `ANTHROPIC_BASE_URL=http://127.0.0.1:3456`
- 请求被改写到本地网关链路，鉴权行为不再是“官方直连默认路径”

因此：即使代理连通，也可能在网关层触发鉴权失败。

### 2.3 `OAuth error: protocol mismatch`
含义：OAuth 授权/回调的协议（http/https）或回调通道不一致。

本次高关联因素：
- `ANTHROPIC_BASE_URL` 指向本地 `http://127.0.0.1:3456`
- 本地回调若被代理或网关处理不当，易出现协议不匹配
- 缺失/错误的 `NO_PROXY` 会增加本地回调被代理劫持概率

## 3. 配置与链路变化（前后对比）

## 3.1 Claude 配置演化

历史快照（`~/.claude/file-history/.../55ba...`）：
- `v1`：
```json
{
  "env": {},
  "includeCoAuthoredBy": false
}
```

- `v2`（关键变更）：
```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:3456"
  },
  "model": "gpt-5-codex",
  "permissions": { ... }
}
```

- `v3`：仍保留 `ANTHROPIC_BASE_URL`，去掉了 `model`。

当前配置（已修正）：
- 文件：`~/.claude/settings.json`
- 关键项：
  - `model = claude-sonnet-4-6`
  - 无 `ANTHROPIC_BASE_URL`
  - 保留安全 permissions

## 3.2 Shell 代理配置演化

早期：固定 7890（但你实际使用 v2rayN 10808）
```bash
http_proxy/https_proxy/all_proxy -> 127.0.0.1:7890
```

当前（已修正）：
- 文件：`~/.zshrc`
- 基于 v2rayN 实际 inbound 设置为 10808（mixed）
```bash
http_proxy/https_proxy/HTTP_PROXY/HTTPS_PROXY = http://127.0.0.1:10808
all_proxy/ALL_PROXY = socks5://127.0.0.1:10808
NO_PROXY/no_proxy = localhost,127.0.0.1,::1
unset ANTHROPIC_BASE_URL
```

## 3.3 链路变化图

### 故障链路（不稳定）
Claude -> `ANTHROPIC_BASE_URL(http://127.0.0.1:3456)` -> 本地网关 -> 外网

风险：
- 依赖本地网关实现与状态
- OAuth 回调更容易出现协议/重定向不一致

### 修复后链路（稳定）
Claude -> `api.anthropic.com`（官方）

出站通过 v2rayN：
- HTTP(S) 代理：`127.0.0.1:10808`
- SOCKS 代理：`127.0.0.1:10808`

本地回调绕过代理：
- `NO_PROXY=localhost,127.0.0.1,::1`

## 4. 本次具体修改清单

1. 删除 `~/.claude/settings.json` 中的 `ANTHROPIC_BASE_URL`
2. 将 `model` 明确为 `claude-sonnet-4-6`
3. 将 `.zshrc` 代理固定到 v2rayN 实际端口 `10808`
4. 同时导出大小写代理变量（兼容不同 CLI/库）
5. 增加 `NO_PROXY/no_proxy` 保护 OAuth 本地回调
6. 清理旧端口 `7890` 作为默认入口的配置依赖

## 5. 为什么你可以用 v2rayN 使用 Claude

原因是你的 v2rayN 当前 inbound 配置为：
- `protocol = mixed`
- `listen = 127.0.0.1`
- `port = 10808`

`mixed` 入口可同时承接 HTTP 与 SOCKS5，因此：
- `http_proxy/https_proxy -> http://127.0.0.1:10808` 可用
- `all_proxy -> socks5://127.0.0.1:10808` 也可用

这就是当前“同一端口兼容两套代理变量”的基础。

## 6. 为什么之前“看起来一直能用”

因为当时你运行在另一条链路：
- Claude 请求先打到本地 `3456` 网关（`ANTHROPIC_BASE_URL`）
- 只要该网关短期内状态正常，就会“看起来可用”

但这条链路对环境变化很敏感：
- 网关状态、代理状态、OAuth 回调策略任一变化，都可能触发异常
- 所以表现为“之前正常，后来突然不行”

## 7. 当前修改的长期影响

正向影响：
- 链路更简单（去掉本地网关层）
- 故障面更小，排障成本降低
- 与 v2rayN 当前真实配置一致，降低端口错配概率
- OAuth 回调更稳定（`NO_PROXY` 生效）

注意事项：
- 若未来 v2rayN 改端口（不是 10808），需同步改 `.zshrc`
- 若你未来确实需要本地 API 网关（3456），应单独管理该模式，不要与 OAuth 登录链路混用

## 8. 推荐运行规范（以后避免复发）

1. 固定一个常用代理端口并版本化记录（当前为 10808）
2. 不在日常配置中保留 `ANTHROPIC_BASE_URL`（除非明确进入网关模式）
3. 永远保留 `NO_PROXY=localhost,127.0.0.1,::1`
4. 每次异常按分层排查：
- `UND_ERR_SOCKET` -> 先查端口监听与代理变量
- `401` -> 查鉴权来源与登录态
- `protocol mismatch` -> 查 OAuth 回调是否被代理/网关改写

## 9. 快速自检命令

```bash
# 1) 看代理环境
env | rg -i '^(http_proxy|https_proxy|all_proxy|HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY|no_proxy|ANTHROPIC_BASE_URL)='

# 2) 看 v2rayN 端口是否监听
lsof -nP -iTCP -sTCP:LISTEN | rg '127.0.0.1:(10808|10809|7890|7891)'

# 3) 看 Claude 登录状态
claude auth status

# 4) 测试 Anthropic 可达性（通过当前代理）
curl -I --max-time 12 https://api.anthropic.com
```

