# Migrate-to-Codex Agent Protocol

This document is the normative behavior contract for any agent invoking the
`migrate-to-codex` skill. The SKILL.md is the short form; this file is the
full form. When in doubt, this file wins.

---

## 1. Scope

A migration "run" is bounded by:
- **One source root**: `~/.claude/` *or* `./.claude/` (never both at once).
- **One target root**: the matching `~/.codex/` *or* `./.codex/`.

Global and project migrations are independent runs. Never mix source roots
inside a single migration step.

---

## 2. Autonomy

After the user has selected a target, the agent proceeds end-to-end without
requesting per-step confirmation. The agent may freely:

- Run the migrator (scan / plan / doctor / dry-run / real / validate).
- Create, edit, replace, or delete generated Codex artifacts inside the
  selected target (`AGENTS.md`, `.codex/`, `.agents/`, or `~/.codex/`).
- Re-run the migrator and validator as many times as needed.

The agent may NOT:

- Edit any source Claude Code file: `.claude/`, `~/.claude/`, `.mcp.json`,
  `.claude.json`.
- Edit unrelated project code, secrets, or any other repository.
- Modify unrelated existing Codex config entries: `notify`, `projects`,
  `marketplaces`, or unrelated MCP servers in `.codex/config.toml` or
  `~/.codex/config.toml`. Preserve them byte-for-byte unless they fail
  validation or directly conflict with the migration. Never ask about them
  unless one of those two conditions applies.

If a problem can only be fixed by changing the source, leave clear manual
guidance inside the generated Codex artifact instead of changing the source.

---

## 3. Mandatory order

Each run executes surfaces in this order. The migrator CLI uses the same
order; align with it.

| # | Surface | Output |
|---|---|---|
| 1 | `instructions` | `AGENTS.md` from `CLAUDE.md` / existing `AGENTS.md` |
| 2 | `plugins` | Report rows only — Claude plugin trees + marketplaces are manual work |
| 3 | `hooks` | Rewrite supported events into `.codex/hooks.json`; set `[features].codex_hooks = true` in `.codex/config.toml` |
| 4 | `skills` & `commands` | Write Codex skills under `.agents/skills/<name>/SKILL.md` |
| 5 | `config` | Write `.codex/config.toml` from Claude model / sandbox settings and MCP servers; include `personality = "friendly"` whenever the config is freshly generated |
| 6 | `subagents` | Write Codex custom agents under `.codex/agents/<name>.md` |
| 7 | `validate` | `--validate-target` against the target |

Use `--replace` only when orphan generated skills or agents (sources gone
upstream) should be deleted from the target.

---

## 4. TODO discipline

The agent uses the host harness's built-in TODO tool (Claude Code's
TodoWrite). It does NOT create `MIGRATION_TODOS.md` or any TODO file unless
the user explicitly asks.

Each TODO item has `step` and `status`. Statuses: `pending`, `in_progress`,
`completed`. Items must be specific to the selected artifacts. Use literal
`source → Codex target` labels. Examples:

- `Inspect .claude/commands → Codex skills/prompts`
- `Inspect .claude/agents → .codex/agents`
- `Inspect .mcp.json → .codex/config.toml MCP servers`
- `Inspect .claude/settings.json hooks → .codex/hooks.json`
- `Migrate safe selected artifacts → Codex files`
- `Validate generated .codex/config.toml`
- `Validate generated .codex/agents`
- `Report migrated artifacts and manual-review items`

Before finishing the run, every step must be `completed`; nothing may remain
`in_progress`.

---

## 5. Inspection before write

Always run inspection passes before any write:

- `--scan-only` — list active and inactive source surfaces.
- `--plan` — print staged Codex artifact paths + report rows.
- `--doctor` — summarize readiness, manual-review work, validation risks.

Then dry-run, then write:

- `--dry-run` — compute the full write set without touching disk.
- (no flag) — apply.

---

## 6. Self-healing loop

Loop until the selected migration is complete:

1. `--plan` or `--doctor`.
2. `--dry-run`.
3. Real run.
4. Fix every generated `## MANUAL MIGRATION REQUIRED` block and every
   `manual_fix_required` / `skipped` row that can be resolved inside Codex
   artifacts.
5. `--validate-target`.
6. Re-run migrator + validator until both have no actionable
   generated-artifact fixes left.

If a row requires source-provider changes or product judgment, leave the
generated Codex artifact with clear manual guidance and move on. Do not
edit source files to silence a row.

---

## 7. Review order after each apply

Inspect the terminal output AND `.codex/migrate-to-codex-report.txt`, then
review generated artifacts in this order:

1. `AGENTS.md`
2. `.agents/skills/`
3. `.codex/config.toml`
4. `.codex/hooks.json`
5. `.codex/agents/`
6. Plugin report rows (manual)

Run `--validate-target` against each target after edits, and re-run
`--dry-run` to confirm the run is now idempotent.

---

## 8. Final report

Render one markdown table per scope that has rows. No prose before or
after the table output.

- One scope with rows → render only the table, no heading.
- Multiple scopes with rows → one heading before each table.
- User scope heading: `**User Config**`.
- Project scope heading: the **actual project folder name** (never
  `Current Project`).

Columns:

```
Status | Item | Notes
```

### 8.1 Status

| Status | Meaning |
|---|---|
| `Added` | Codex artifact created or changed; no special review needed |
| `Check before using` | Codex artifact created or changed, but semantics shifted, behavior was inferred, tool rules were preserved as guidance, or unsupported behavior was dropped |
| `Not Added` | Source artifact detected; no Codex artifact created |

### 8.2 Item

Format: `<inline-code-artifact-type> <plain-text-item-name>`.

Artifact type must be **singular** and one of:

- `Skill`
- `Slash command`
- `Subagent`
- `MCP`
- `Hook`
- `Plugin`

### 8.3 Notes

Always required. Short, plain, literal. Avoid internal jargon (e.g. do not
write `runtime expansion`). Prefer these canonical phrases:

- `Converted into a Codex skill`
- `Added as a Codex subagent`
- `Added to Codex config`
- `Converted into a Codex hook`
- `Converted, but some Claude hook behavior differs in Codex`
- `Codex does not have an equivalent notification hook`
- `Plugin needs manual setup`
- `Plugin marketplace needs manual setup`

### 8.4 Inclusion rules

The table covers only the **non-native follow-up migration work you
personally performed** in this run: skills created from slash commands,
subagents, MCP servers, hooks, unsupported / local plugin notes, and
manual-review caveats.

Include programmatic native import rows for config, instructions, skills,
or supported plugins ONLY if you personally migrated them in this
follow-up run.

### 8.5 Reference example

```
**northstar-support-portal**

| Status              | Item                       | Notes                                                       |
|---------------------|----------------------------|-------------------------------------------------------------|
| Added               | `Slash command` pr-review  | Converted into a Codex skill                                |
| Added               | `Subagent` release-lead    | Added as a Codex subagent                                   |
| Check before using  | `Hook` PreToolUse          | Converted, but some Claude hook behavior differs in Codex   |
| Not Added           | `Hook` Notification        | Codex does not have an equivalent notification hook         |
| Not Added           | `Plugin` team-macros       | Plugin needs manual setup                                   |
```

---

## 9. Glossary

- **Source surface** — a Claude Code configuration concept the migrator
  knows about (instructions, hooks, commands, agents, MCP, plugins).
- **Target artifact** — the Codex file the migrator writes for a given
  surface.
- **Manual migration block** — a `## MANUAL MIGRATION REQUIRED` section
  written into a generated Codex artifact when the migrator could not
  fully translate the source.
- **Orphan** — a generated Codex artifact whose source has been deleted.
  Cleaned up only with explicit `--replace`.
