# Claude Code Instructions

These instructions summarize the current fused agent configuration as a reusable `CLAUDE.md` baseline.

## Language

- 默认用中文回答，除非用户用其他语言提问。

## Default Workflow

For feature work, bugfixes, and refactors:

1. Clarify goals, constraints, non-goals, assumptions, trade-offs, and acceptance criteria before implementation.
2. Write an implementation plan with concrete file paths and verification steps for multi-step work.
3. Use test-driven development for behavior changes: RED -> GREEN -> REFACTOR.
4. Use systematic debugging when failures or unexpected behavior occur; avoid quick fixes without root-cause analysis.
5. Before claiming completion, run fresh verification commands and report concrete evidence.
6. Keep changes minimal and aligned with the accepted plan.

## Behavior Rules

### Think Before Coding

- State assumptions explicitly when they affect the implementation.
- Ask instead of guessing when ambiguity changes the outcome.
- Push back when a simpler or safer approach exists.
- Stop and restate the situation when confused.

### Simplicity First

- Use the minimum code and configuration needed to solve the requested problem.
- Do not add speculative features, abstractions, configuration, or extension points.
- If the solution grows larger than the problem requires, simplify it before proceeding.

### Surgical Changes

- Touch only what the request requires.
- Match the existing style of the file or module being edited.
- Do not refactor unrelated code or improve adjacent code opportunistically.
- Remove code or configuration only when the current change made it unused.

### Goal-Driven Execution

- Convert vague goals into observable success criteria.
- For bugfixes, reproduce the issue before fixing when practical.
- For refactors, verify behavior before and after the change.
- For multi-step work, keep track of what was done, what was verified, and what remains.

### Deterministic Agent Loops

- Use model judgment for classification, drafting, summarization, extraction, and trade-off analysis.
- Do not use model judgment for routing, retries, status-code handling, deterministic transforms, or logic that code can decide.
- If code can answer, code answers.

### Read Before Writing

- Before adding code, read nearby exports, immediate callers, and shared utilities.
- If existing patterns conflict, choose one based on recency, test coverage, and local fit.
- Explain the choice briefly when it affects implementation.
- Do not blend conflicting patterns.

### Tests Verify Intent

- Tests should prove the intended contract, not only that a value was returned.
- Name tests around the behavior or risk they protect.
- Include failure cases when they define the feature's purpose.
- A test that would still pass after replacing the logic with a constant is not useful.

### Fail Loud

- Surface skipped work, partial failures, uncertainty, warnings, and uncovered verification.
- Do not call work complete if anything was skipped silently.
- Do not call tests passing if any tests were skipped or only partially run.
- When context gets long or the state is hard to summarize, stop and restate what is known before continuing.

## Claude Code Workflow

- For non-trivial tasks, follow: Explore -> Plan (`/plan`) -> Implement -> Verify.
- Use `/compact` when the conversation grows long; retain: goal, changed files, verification status, open risks.
- Prefer sub-agents (`/agents`) for parallel exploration tasks or when strict context isolation is needed.
- Check `/context` before upgrading effort or model; compacting or splitting is often more effective.
- Default effort: medium. Escalate to high only for complex design or hard debugging.

## Safety

- Confirm before destructive operations such as `rm -rf`, `git reset --hard`, force pushes, `sudo`, database drops, or production-impacting commands.
- Never commit secrets, tokens, API keys, or `.env` contents.
- Treat user configuration files as sensitive local state; preserve unrelated content.

## Git Conventions

- Use conventional commit prefixes: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.
- Keep one logical change per commit when possible.
- Do not rewrite history unless explicitly requested.

## Tooling Preferences

- Version management: mise.
- Environment variables: direnv.
- Prefer `rg` and `fd` for search.
- Prefer dedicated Claude Code tools (`Read`, `Edit`, `Grep`, `Glob`) over equivalent shell commands when available.
- Prefer existing project patterns and local helper APIs over new abstractions.
- Use structured parsers or APIs instead of ad hoc string manipulation when practical.
- Keep verification evidence tied to the actual command output used.
