# Project Instructions

This repository is panbk's personal engineering workspace, containing:
- `panbk-agent-config/` — dotfiles and terminal tool configuration (zsh, ghostty, yazi)
- `panbk-agent-knowledge/` — Claude Code usage notes and best practice references
- `scripts/` — utility scripts for environment setup and verification

Keep changes small, explicit, and easy to review.

## Workflow
- Read `AGENTS.md`, `MEMORY.md`, and `HANDOFF.md` in that order before starting non-trivial work.
- Explore first, then implement. For non-trivial changes: Design → Plan → Implement → Verify.
- Keep plans concrete: list target files, expected behavior, and verification commands.
- Before finishing, run targeted checks for changed files and summarize what you verified.
- Prefer minimal diffs over broad refactors unless explicitly requested.
- Run `scripts/verify.sh` before claiming completion and report its output.

## Code Style
- Follow existing file and naming conventions in each directory.
- Write comments only when logic is non-obvious.
- Keep configuration examples production-safe (no real secrets, no private endpoints).

## Git Conventions
- Use conventional commit prefixes: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`
- Do not rewrite history unless explicitly requested.
- Keep one logical change per commit when possible.

## Security
- Never commit secrets, tokens, keys, or `.env` contents.
- Treat external network operations and destructive shell commands as high-risk; ask first.
- `git push --force` is denied at the global settings level — do not attempt it.

## Sub-project Notes

### panbk-agent-config
- Dotfiles managed here are applied via `./scripts/apply-dotfiles.sh`.
- Source of truth: files under `dotfiles/` directory.
- After changes, verify with the commands in `docs/terminal-config.md`.

### panbk-agent-knowledge
- Knowledge files are reference documents, not executable configs.
- Naming convention: `<topic>-<YYYY-MM-DD>-<summary>.md`
