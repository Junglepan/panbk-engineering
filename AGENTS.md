## Default Engineering Workflow (Mandatory)

For feature work, bugfixes, and refactors, follow this order unless user explicitly overrides:

1) Use `brainstorming` to clarify goals, constraints, non-goals, and acceptance criteria.
2) Use `writing-plans` to produce step-by-step implementation tasks with file paths and verification steps.
3) Implement via `test-driven-development` (RED -> GREEN -> REFACTOR).
4) If failures or unexpected behavior occur, use `systematic-debugging` before proposing fixes.
5) Before claiming completion, run `verification-before-completion` with concrete command/test evidence.
6) When work is done, use `finishing-a-development-branch` for merge/PR/cleanup decision.

Additional rules:
- No quick fixes without root-cause analysis for bugs.
- No completion claims without verification output.
- Keep changes minimal and aligned to accepted plan.

## Context Files (Mandatory Read Order)

Before implementation, read in this order:
1) `AGENTS.md` (this file)
2) `MEMORY.md` (long-term preferences and decisions)
3) `HANDOFF.md` (current task state and next actions)

## Compact Instructions

When context grows large, summarize and retain:
- Goal, constraints, and acceptance criteria
- Files changed and why
- Verification status (passed/failed/not run)
- Open risks and explicit next step

Do not drop unresolved blockers or pending decisions during compaction.

## Completion Gate

Before claiming completion:
- Run `scripts/verify.sh`
- Report key outputs (pass/fail + failing command if any)
- Update `HANDOFF.md` if work is partial
