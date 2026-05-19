# MEMORY

## Long-Term Preferences
- Prefer concise implementation with explicit verification output.
- For medium/large changes: plan first, then implement.
- Avoid quick fixes without root-cause evidence.

## Project Decisions
- Project-level workflow is defined in `AGENTS.md`.
- Superpowers skills are vendored under `.agents/skills/superpowers`.
- Completion requires running `scripts/verify.sh`.

## Common Commands
- Run checks: `scripts/verify.sh`
- Branch status: `git status -sb`
- Recent commits: `git log --oneline -n 10`

## Update Rules
- Add durable decisions only (not temporary notes).
- If a decision is superseded, update the old line instead of duplicating.
