#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$HOME/.config/ghostty" "$HOME/.config/yazi" "$HOME/.claude/agents"

# Terminal tools
cp "$REPO_ROOT/terminal/zsh/.zshrc" "$HOME/.zshrc"
cp "$REPO_ROOT/terminal/ghostty/config" "$HOME/.config/ghostty/config"
cp "$REPO_ROOT/terminal/yazi/yazi.toml" "$HOME/.config/yazi/yazi.toml"

# Claude Code
cp "$REPO_ROOT/claude/CLAUDE.md" "$HOME/.claude/CLAUDE.md"
cp "$REPO_ROOT/claude/settings.json" "$HOME/.claude/settings.json"
cp "$REPO_ROOT/claude/agents/"*.md "$HOME/.claude/agents/"

echo "Applied terminal: ~/.zshrc ~/.config/ghostty/config ~/.config/yazi/yazi.toml"
echo "Applied claude:   ~/.claude/CLAUDE.md ~/.claude/settings.json ~/.claude/agents/"
