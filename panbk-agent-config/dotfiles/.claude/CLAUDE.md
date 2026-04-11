# Global Preferences

## Language
- 默认用中文回答，除非用户用其他语言提问。

## Git Conventions
- Use conventional commit prefixes: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`
- Keep one logical change per commit when possible.
- Do not rewrite history unless explicitly requested.

## Safety
- Always confirm before destructive operations: `rm -rf`, `git reset --hard`, `git push --force`, `sudo`, `drop table`.
- Never commit secrets, tokens, API keys, or `.env` contents.
- Treat external network operations and production-impacting commands as high-risk — ask first.

## Toolchain
- Version management: mise
- Environment variables: direnv
- Search: ripgrep (`rg`), fd
- Prefer dedicated Claude Code tools (Read, Edit, Grep, Glob) over equivalent shell commands.

## Claude Code Workflow
- For non-trivial tasks, follow: Explore → Plan (`/plan`) → Implement → Verify.
- Use `/compact` when the conversation grows long; retain: goal, changed files, verification status, open risks.
- Prefer sub-agents (`/agents`) for parallel exploration tasks or when strict context isolation is needed.
- Check `/context` before upgrading effort or model — often compacting or splitting is more effective.
- Default effort: medium. Escalate to high only for complex design or hard debugging.

## Code Quality
- Explore first, then implement. Never jump to solutions without understanding the problem.
- Keep diffs minimal — prefer targeted changes over broad refactors unless explicitly asked.
- Write comments only when logic is non-obvious.
- Before claiming completion, run verification commands and report concrete evidence.
