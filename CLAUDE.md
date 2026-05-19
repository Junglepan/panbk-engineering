# Project Instructions

This repository is panbk's personal engineering workspace, containing:
- `knowledge/` — technical knowledge documents organized by topic
- `config/` — dotfiles and agent configuration (claude, codex, terminal tools)
- `scripts/` — utility scripts for environment setup and verification

Keep changes small, explicit, and easy to review.

## Workflow
- Read `AGENTS.md`, `.claude/MEMORY.md`, and `.claude/HANDOFF.md` in that order before starting non-trivial work.
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

### config/
- Dotfiles managed here are applied via `./config/apply-dotfiles.sh`.
- Source of truth: files under `config/terminal/`.

### knowledge/
- Knowledge files are reference documents, not executable configs.
- Organized by topic in subdirectories (ai-agent, codex, networking, incidents).
