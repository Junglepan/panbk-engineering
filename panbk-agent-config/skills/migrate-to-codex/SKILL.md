---
name: migrate-to-codex
description: Migrate Claude Code instruction files, slash commands, subagents, hooks and MCP config into Codex's AGENTS.md / .codex/ / .agents/ layout. Use when the user asks to "migrate to Codex", "switch to Codex", "convert .claude to .codex", or wants to take a Claude Code project / global setup and produce equivalent Codex configuration.
---

# migrate-to-codex

A one-way, non-destructive migrator that turns a Claude Code configuration tree (`.claude/`, `~/.claude/`, `.mcp.json`, `.claude.json`) into the equivalent Codex configuration (`AGENTS.md`, `.codex/`, `.agents/`, `~/.codex/`).

This skill encodes both the **transformation rules** and the **agent behavior contract**. The migrator script lives at `scripts/migrate-to-codex.py`; the deep mapping table lives at `references/differences.md`; the full protocol lives at `references/protocol.md`.

---

## When to invoke

- User explicitly asks to migrate / convert / switch from Claude Code to Codex.
- User points at a `.claude/` tree and wants `.codex/` produced.
- User asks for a parity check between an existing `.claude/` and `.codex/`.

Do NOT invoke for:
- Reverse migration (Codex → Claude Code) — out of scope.
- Editing or "cleaning up" Claude Code source files.
- General Codex configuration help with no source to migrate from.

---

## Source → target map

| Claude Code source | Codex target | Notes |
|---|---|---|
| `CLAUDE.md` / `AGENTS.md` | `AGENTS.md` | Top-level instructions |
| `.claude/commands/*.md` (slash commands) | `.agents/skills/<name>/SKILL.md` | Each slash command becomes a Skill |
| `.claude/agents/*.md` (subagents) | `.codex/agents/<name>.md` | Codex custom agents |
| `.mcp.json` / `mcpServers` in settings | `.codex/config.toml` `[mcp_servers.<name>]` | Stdio/SSE/HTTP all supported |
| `.claude/settings.json` `hooks` | `.codex/hooks.json` + `[features].codex_hooks = true` | Some events have no Codex equivalent |
| `.claude/settings.json` model / sandbox | `.codex/config.toml` (top-level + `[sandbox]`) | Adds `personality = "friendly"` when generating fresh |
| Plugins / Marketplaces | (no auto-migration) | Reported as manual work only |

Scopes:
- **Global**: `~/.claude/` → `~/.codex/`
- **Project**: `./.claude/` → `./.codex/`

Migrate each scope independently; never mix source roots in a single run.

---

## Autonomy contract

Once the user has selected a source/target pair, proceed end-to-end without asking for confirmation between steps:

1. Run scan / plan / doctor.
2. Dry-run the migration.
3. Apply for real.
4. Read the report.
5. Fix every `## MANUAL MIGRATION REQUIRED` block and every `manual_fix_required` row that can be resolved **inside Codex artifacts only**.
6. Run `--validate-target`.
7. Loop steps 2–6 until the report and validator have no actionable Codex-side fixes left.

### Hard boundaries (never cross)

- **Never edit source Claude Code files**: `.claude/`, `~/.claude/`, `.mcp.json`, `.claude.json`.
- **Never touch unrelated project code, secrets, or another repository.**
- **Preserve unrelated Codex config**: `notify`, `projects`, `marketplaces`, and unrelated MCP servers in `.codex/config.toml` / `~/.codex/config.toml` must stay byte-equivalent unless they fail validation or directly conflict with the migration.
- If a problem can only be fixed by changing the source, **leave clear manual guidance inside the generated Codex artifact** instead of changing the source.

---

## Mandatory migration order

Do not reorder. Each step assumes the previous step has produced its artifacts.

1. **Instructions** — `CLAUDE.md` / `AGENTS.md` → `AGENTS.md`
2. **Plugins** — report only; produce manual-migration rows
3. **Hooks** — write `.codex/hooks.json`; set `[features].codex_hooks = true` in `.codex/config.toml`
4. **Skills & commands** — write `.agents/skills/<name>/SKILL.md`
5. **Config** — write `.codex/config.toml` (model, sandbox, MCP servers, `personality = "friendly"` when generating fresh)
6. **Subagents** — write `.codex/agents/<name>.md`
7. **Validate** — `--validate-target`

---

## TODO list rules

Use Claude Code's built-in TodoWrite tool. Do **not** create `MIGRATION_TODOS.md` or any free-standing TODO file unless the user explicitly asks.

Each TODO must use the literal `source → Codex target` form so the trail is auditable:

- `Inspect .claude/commands → Codex skills/prompts`
- `Inspect .claude/agents → .codex/agents`
- `Inspect .mcp.json → .codex/config.toml MCP servers`
- `Inspect .claude/settings.json hooks → .codex/hooks.json`
- `Migrate safe selected artifacts → Codex files`
- `Validate generated .codex/config.toml`
- `Validate generated .codex/agents`
- `Report migrated artifacts and manual-review items`

Status values: `pending`, `in_progress`, `completed`. Before finishing, ensure every step is `completed` and none is `in_progress`.

---

## CLI surface

```
MIGRATE='python3 .codex/skills/migrate-to-codex/scripts/migrate-to-codex.py'

# Inspection (read-only)
$MIGRATE --source ~/.claude/  --scan-only
$MIGRATE --source ~/.claude/  --target ~/.codex/  --plan
$MIGRATE --source ~/.claude/  --target ~/.codex/  --doctor

# Apply (global)
$MIGRATE --source ~/.claude/  --target ~/.codex/  --dry-run
$MIGRATE --source ~/.claude/  --target ~/.codex/

# Apply (project)
$MIGRATE --source ./.claude/  --target ./.codex/  --dry-run
$MIGRATE --source ./.claude/  --target ./.codex/

# Validate after edits
$MIGRATE --validate-target ~/.codex/
$MIGRATE --validate-target ./.codex/

# Discover all flags (incl. --replace for orphan cleanup)
$MIGRATE --help
```

After every real run, read `.codex/migrate-to-codex-report.txt` and the terminal output before deciding next steps.

Review generated artifacts in this order: `AGENTS.md` → `.agents/skills/` → `.codex/config.toml` → `.codex/hooks.json` → `.codex/agents/` → plugin report rows.

---

## Final report format

Output **one markdown table per scope that has rows**, with no surrounding prose.

- Single scope with rows → render only the table, no heading.
- Multiple scopes with rows → render one heading per table.
- User-scope heading: `**User Config**`.
- Project-scope heading: the **actual project folder name** (e.g. `**northstar-support-portal**`). Never `Current Project`.

Columns are exactly:

```
Status | Item | Notes
```

### Status values

| Status | Meaning |
|---|---|
| `Added` | Codex artifact created/changed; no special review needed |
| `Check before using` | Codex artifact created/changed but semantics shifted, behavior was inferred, tool rules became guidance, or unsupported behavior was dropped |
| `Not Added` | Source artifact detected; no Codex artifact created (e.g. plugin, unsupported hook event) |

### Item column

`<artifact-type-inline-code> <item-name-plain-text>`. Artifact type must be **singular** and one of:

- `` `Skill` ``
- `` `Slash command` ``
- `` `Subagent` ``
- `` `MCP` ``
- `` `Hook` ``
- `` `Plugin` ``

### Notes column

Always required. Keep it short, plain, literal. Avoid implementation jargon (e.g. don't say "runtime expansion"). Prefer these canonical phrases:

- `Converted into a Codex skill`
- `Added as a Codex subagent`
- `Added to Codex config`
- `Converted into a Codex hook`
- `Converted, but some Claude hook behavior differs in Codex`
- `Codex does not have an equivalent notification hook`
- `Plugin needs manual setup`
- `Plugin marketplace needs manual setup`

### Scope of the table

Include only the **non-native follow-up work you personally performed** in this run: skills created from slash commands, subagents, MCP servers, hooks, unsupported/local plugin notes, and manual-review caveats.

Include programmatic native import rows for config / instructions / skills / supported plugins **only if you personally migrated them** in this follow-up run.

### Example

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

## Self-healing loop

```
loop:
  --plan or --doctor
  --dry-run
  real run
  fix every ## MANUAL MIGRATION REQUIRED block in generated Codex artifacts
  fix every manual_fix_required / skipped row that can be solved inside Codex artifacts
  --validate-target
  if report has actionable Codex-side issues OR validator fails:
    continue
  else:
    break
```

The loop terminates only when **both** the report and the validator agree that no Codex-side fix remains. Source-side issues never gate termination — they are recorded as guidance in the generated artifact.

---

## References

- `references/protocol.md` — full text of the agent behavior contract.
- `references/differences.md` — Claude Code ↔ Codex deep mapping (hooks, sandbox, permissions, env vars). Refresh from Codex docs if its `Docs last checked` date is stale.
- `scripts/migrate-to-codex.py` — the migrator (reads source, writes target, emits report).
