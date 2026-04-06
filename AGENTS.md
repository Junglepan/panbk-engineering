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
