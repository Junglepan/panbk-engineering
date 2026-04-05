# Project Instructions

This repository currently contains lightweight bootstrap modules. Keep changes small, explicit, and easy to review.

## Workflow
- Explore first, then implement.
- For non-trivial changes, use a four-step flow: Design -> Plan -> Implement -> Verify.
- Keep plans concrete: list target files, expected behavior, and verification commands.
- Before finishing, run targeted checks for changed files and summarize what you verified.
- Prefer minimal diffs over broad refactors unless explicitly requested.

## Code Style
- Follow existing file and naming conventions in each directory.
- Write comments only when logic is non-obvious.
- Keep configuration examples production-safe (no real secrets, no private endpoints).

## Git Conventions
- Use conventional commit prefixes, for example `feat:`, `fix:`, `docs:`, `chore:`.
- Do not rewrite history unless explicitly requested.
- Keep one logical change per commit when possible.

## Security
- Never commit secrets, tokens, keys, or `.env` contents.
- Treat external network operations and destructive shell commands as high-risk; ask first.
