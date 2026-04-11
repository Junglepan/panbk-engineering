#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$HOME/.config/ghostty" "$HOME/.config/yazi" "$HOME/.claude/agents"
cp "$REPO_ROOT/dotfiles/.zshrc" "$HOME/.zshrc"
cp "$REPO_ROOT/dotfiles/.config/ghostty/config" "$HOME/.config/ghostty/config"
cp "$REPO_ROOT/dotfiles/.config/yazi/yazi.toml" "$HOME/.config/yazi/yazi.toml"
cp "$REPO_ROOT/dotfiles/.claude/CLAUDE.md" "$HOME/.claude/CLAUDE.md"
cp "$REPO_ROOT/dotfiles/.claude/settings.json" "$HOME/.claude/settings.json"
cp "$REPO_ROOT/dotfiles/.claude/agents/"*.md "$HOME/.claude/agents/"

echo "Applied: ~/.zshrc ~/.config/ghostty/config ~/.config/yazi/yazi.toml"
echo "Applied: ~/.claude/CLAUDE.md ~/.claude/settings.json ~/.claude/agents/"
