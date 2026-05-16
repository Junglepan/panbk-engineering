# v2rayN 代理与终端下载切换总结（2026-04-18）

## 1. 背景与问题

在终端执行 Bun 安装时出现报错：
- `curl: (35) LibreSSL SSL_connect: SSL_ERROR_SYSCALL`
- Bun 下载失败（GitHub release 资源）

排查后确认，核心不是 Bun 本身，而是终端代理环境变量导致的网络路径问题。

## 2. 根因

当时 shell 全局导出了以下代理变量（大小写都有）：
- `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY`
- `http_proxy` / `https_proxy` / `all_proxy`

并且都指向本地端口 `127.0.0.1:10808`。

这意味着：
- `curl` 和依赖 `curl` 的安装脚本都会优先走该代理。
- 一旦该端口不可用或当前链路不适配目标站点，就会出现 TLS/连接异常。

## 3. 最终目标（当前已实现）

你希望的行为是：
- 新开终端默认走 `127.0.0.1:10808`（保持平时使用习惯）
- 需要下载时手动切换到 `127.0.0.1:7890`

已在 `~/.zshrc` 中落地为函数化切换。

## 4. 当前可用命令

```bash
proxy_on      # 切到 10808（默认）
proxy_7890    # 临时切到 7890（下载时用）
proxy_off     # 关闭代理
proxy_status  # 查看当前代理变量
```

其中 `~/.zshrc` 启动时会自动执行 `proxy_on`，所以新终端默认是 `10808`。

## 5. 推荐使用流程

1. 平时正常使用（默认 `10808`）

```bash
proxy_status
```

2. 需要下载（例如 bun / npm / curl 某些资源）时：

```bash
proxy_7890
# 执行下载命令
proxy_on
```

3. 如果要彻底直连测试：

```bash
proxy_off
# 测试完成后恢复
proxy_on
```

## 6. 针对单条命令临时指定代理（不改全局）

如果不想切全局变量，可对单条命令指定：

```bash
curl -x http://127.0.0.1:7890 -fsSL https://bun.sh/install | bash
```

或：

```bash
HTTPS_PROXY=http://127.0.0.1:7890 HTTP_PROXY=http://127.0.0.1:7890 <你的命令>
```

## 7. 快速排查清单

1. 查看当前代理变量：

```bash
proxy_status
```

2. 确认目标端口是否可用（10808/7890）：

```bash
curl -I --proxy http://127.0.0.1:10808 https://github.com
curl -I --proxy http://127.0.0.1:7890 https://github.com
```

3. 若下载失败，先做“变量-端口-命令”三段核对：
- 变量是否切到期望端口
- 端口对应代理程序是否在运行
- 下载命令是否继承了当前 shell 环境

## 8. 一句话结论

这次问题本质是“终端代理环境变量与目标下载链路不匹配”，不是 Bun 安装器问题；
通过 `proxy_on / proxy_7890 / proxy_off` 的函数化切换，已经实现了“默认 10808、下载时临时 7890”的稳定工作流。
