# Terminal Config 说明

## 目标

这套配置面向日常开发的高频路径：搜索、跳转、版本切换、文件预览、目录环境加载。

## 为什么是这套

1. 高收益工具
- `fzf`：交互式筛选与历史检索。
- `ripgrep/fd`：文件与文本搜索提速。
- `bat/eza`：更清晰的内容与目录展示。

2. 开发环境一致性
- `direnv`：目录级环境变量自动加载。
- `mise`：多语言版本统一管理。

3. 文件管理体验
- `yazi` + `mediainfo/unar/p7zip`：预览与压缩包处理完整。

4. 跳转效率
- `zoxide`：智能目录跳转，`j` 作为快捷别名。

## 已应用配置

1. Zsh
- 路径优先级：`/opt/homebrew/bin` 提前。
- 历史策略：`APPEND_HISTORY`、`INC_APPEND_HISTORY`、`SHARE_HISTORY`、`EXTENDED_HISTORY`。
- 集成：`fzf`、`direnv`、`mise`、`zoxide`。
- 别名：`ls/ll/la` 使用 `eza`，`cat` 使用 `bat`，`find` 使用 `fd`。

2. Ghostty
- 保留透明与快速终端能力。
- 将 `scrollback-limit` 收敛到 `20000000`，平衡可回溯与内存占用。

3. Yazi
- 启用隐藏文件显示、自然排序。
- 增加编辑/打开/Finder 定位的 opener。

## 管理方式

仓库内文件为配置基线：
- `dotfiles/.zshrc`
- `dotfiles/.config/ghostty/config`
- `dotfiles/.config/yazi/yazi.toml`

一键应用：
```bash
./scripts/apply-dotfiles.sh
```

## 验证

```bash
zsh -ic 'command -v fzf rg fd bat eza direnv mise yazi zoxide'
zsh -ic 'setopt | grep -E "sharehistory|incappendhistory|extendedhistory|histignoredups"'
yazi --version
mise --version
direnv version
```
