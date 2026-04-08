#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$HOME/.config/ghostty" "$HOME/.config/yazi"
cp "$REPO_ROOT/dotfiles/.zshrc" "$HOME/.zshrc"
cp "$REPO_ROOT/dotfiles/.config/ghostty/config" "$HOME/.config/ghostty/config"
cp "$REPO_ROOT/dotfiles/.config/yazi/yazi.toml" "$HOME/.config/yazi/yazi.toml"

echo "Applied: ~/.zshrc ~/.config/ghostty/config ~/.config/yazi/yazi.toml"
