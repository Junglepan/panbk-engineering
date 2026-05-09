# Claude Code ↔ Codex: Surface-by-surface differences

> Docs last checked: 2026-05-09
> Refresh this file from `developers.openai.com/codex/...` and `docs.claude.com/...`
> if the date above is more than ~30 days old.

This is the deep mapping table the migrator uses for translation decisions.
The SKILL.md and protocol.md describe **what** to migrate; this file
describes **how each surface maps**, **what is lossy**, and **where manual
work is required**.

---

## 1. Top-level layout

| Concept | Claude Code | Codex |
|---|---|---|
| Project instructions | `CLAUDE.md` (root, recursive parents merged) | `AGENTS.md` (root only) |
| User instructions | `~/.claude/CLAUDE.md` | `~/.codex/AGENTS.md` |
| File imports | `@path/to/file.md` inside CLAUDE.md | Not supported — **inline contents during migration** |
| Project settings | `.claude/settings.json` | `.codex/config.toml` |
| User settings | `~/.claude/settings.json` | `~/.codex/config.toml` |
| Local-only override | `.claude/settings.local.json` | No native equivalent — record as manual note |
| Slash commands | `.claude/commands/*.md` | `.agents/skills/<name>/SKILL.md` |
| Subagents | `.claude/agents/*.md` | `.codex/agents/<name>.md` |
| Hooks | `.claude/settings.json` `hooks` | `.codex/hooks.json` (gated by `[features].codex_hooks`) |
| MCP servers | `.mcp.json` / settings `mcpServers` | `.codex/config.toml` `[mcp_servers.<name>]` |
| Plugins | `.claude/plugins/` + marketplaces | No auto-migration; report only |

---

## 2. Instructions (`CLAUDE.md` → `AGENTS.md`)

- **Format**: Both are Markdown with no required frontmatter at the root level.
- **Imports**: Claude Code expands `@path` inline, depth ≤ 5. Codex does not.
  The migrator must inline imports during conversion. Mark inlined sections
  with an HTML comment for traceability.
- **Recursive parents**: Claude Code walks parent directories collecting
  `CLAUDE.md`. Codex reads only the root `AGENTS.md`. The migrator should
  concatenate parent files into the generated `AGENTS.md` with clear
  section headers (`## From <relative-path>`).
- **Memory hierarchy**: User-level + project-level both apply. Migrate
  user `CLAUDE.md` to `~/.codex/AGENTS.md` independently.

---

## 3. Slash commands → Skills

Claude Code slash commands live in `.claude/commands/<name>.md` and are
invoked as `/<name>`. Codex has no slash command primitive — the closest
equivalent is a Skill.

### 3.1 Frontmatter mapping

| Claude Code field | Codex Skill field | Notes |
|---|---|---|
| `description` | `description` | Direct |
| `argument-hint` | (drop) | Encode in skill body as a usage example |
| `allowed-tools` | (drop) | Codex skill tool gating differs; preserve as guidance text |
| `model` | (drop) | Codex skills inherit the run's model |

### 3.2 Body transformations

| Claude Code construct | Codex translation |
|---|---|
| `$ARGUMENTS` | Replace with a usage block; explain that the user supplies args at invocation |
| `$1`, `$2`, ... | Same — preserve as documented placeholders |
| `` !`shell command` `` | Convert to a documented step ("Run: `shell command`"). **Do not** keep the leading `!` — Codex does not pre-execute. Mark this row as `Check before using`. |
| `@path/to/file` | Inline file contents during migration |

### 3.3 Output location

`./.agents/skills/<name>/SKILL.md` (project) or `~/.agents/skills/<name>/SKILL.md`
(global, if Codex global skills are supported in this version — otherwise
report as manual).

---

## 4. Subagents → Codex custom agents

| Claude Code agent field | Codex agent field | Notes |
|---|---|---|
| `name` | filename | `<name>.md` |
| `description` | `description` | Direct |
| `tools` (CSV of tool names) | `tools` | Tool names overlap mostly; map MCP tool names by full `mcp__server__tool` form |
| `model` | `model` | Direct, but Codex may not recognize Claude model IDs — fall back to default and note `Check before using` |
| Body (system prompt) | Body | Direct |

Output: `.codex/agents/<name>.md`.

---

## 5. Hooks

Claude Code has 8 hook events. Codex's hook surface is narrower. Map
conservatively.

| Claude Code event | Codex equivalent | Status |
|---|---|---|
| `PreToolUse` | `pre_tool_use` | Converted, but matcher syntax differs → `Check before using` |
| `PostToolUse` | `post_tool_use` | Converted, but Codex output schema differs → `Check before using` |
| `UserPromptSubmit` | `user_prompt_submit` | Converted |
| `Stop` | `stop` | Converted |
| `SubagentStop` | `subagent_stop` (if supported) | If absent in target Codex version → `Not Added` |
| `Notification` | (none) | `Not Added`, note `Codex does not have an equivalent notification hook` |
| `PreCompact` | (none) | `Not Added`, note `Codex compaction is not user-hookable` |
| `SessionStart` / `SessionEnd` | `session_start` / `session_end` | Converted |

### 5.1 JSON schema differences

Claude Code hooks read JSON from stdin and write JSON to stdout / use exit
codes (0 / 2 / other). Codex hooks use a structured config plus a script
path; any logic that depended on Claude's `permissionDecision` /
`hookSpecificOutput` fields must be flagged with a `## MANUAL MIGRATION
REQUIRED` block in the generated `.codex/hooks.json`.

### 5.2 Feature flag

Generated hooks are inert until `[features].codex_hooks = true` is added to
`.codex/config.toml`. The migrator must set this flag whenever any hook is
emitted.

---

## 6. MCP servers

`.mcp.json` and `settings.json.mcpServers` map directly to
`[mcp_servers.<name>]` in `.codex/config.toml`.

| Claude transport | TOML key | Notes |
|---|---|---|
| `stdio` (default) | `command`, `args`, `env` | Direct |
| `sse` | `transport = "sse"`, `url` | Direct |
| `http` (streamable HTTP) | `transport = "http"`, `url` | Direct; preserve `headers` |

### 6.1 Auth & secrets

- Never copy literal secrets across files. Replace any inline token with
  `${env:VAR_NAME}` and emit a `Check before using` row referencing the
  env var the user must set in their Codex environment.
- `apiKeyHelper` (Claude-specific) has no Codex equivalent — record as
  manual note.

### 6.2 Project-level MCP gating

Claude Code requires explicit user approval per project before activating
`.mcp.json` servers. Codex has its own enable/disable model — the
migrator should write servers as enabled and emit a `Check before using`
row when the source had them in the disabled list.

---

## 7. Permissions / sandbox / model

| Claude Code (`settings.json`) | Codex (`config.toml`) | Notes |
|---|---|---|
| `model` | `model` | Map by family; if the exact Claude model ID is not a Codex model, fall back to the Codex default and note `Check before using` |
| `permissions.defaultMode` | `[sandbox].mode` | `default` → `default`, `acceptEdits` → `auto-edit`, `plan` → `read-only`, `bypassPermissions` → `danger-full-access` |
| `permissions.allow` / `ask` / `deny` | (no direct equivalent) | Preserve as guidance text in `AGENTS.md`; emit `Check before using` |
| `permissions.additionalDirectories` | `[sandbox].writable_paths` | Direct |
| `env` | `[env]` table | Direct |
| `includeCoAuthoredBy` | (none) | Drop; record as manual note |
| `statusLine` | (none) | Drop; record as manual note |

When generating a fresh `.codex/config.toml`, always emit
`personality = "friendly"` at the top level.

---

## 8. Plugins / marketplaces

No auto-migration. Claude Code's `~/.claude/plugins/config.json`,
plugin trees, and marketplace registrations have no Codex equivalent.
Emit one `Not Added` row per plugin and per marketplace, with notes:

- `Plugin needs manual setup`
- `Plugin marketplace needs manual setup`

If a plugin contributes its own commands / agents / hooks / MCP, the
migrator should additionally process those contributions through the
normal surface pipelines and emit a separate row for each, marked
`Check before using` (because plugin context is lost).

---

## 9. CLAUDE.md feature surface that has no Codex home

The following Claude Code primitives have no clean Codex target. The
migrator records them in a `## MANUAL MIGRATION REQUIRED` section in
`AGENTS.md` so the user is aware:

- Output styles (`.claude/output-styles/*.md`)
- Statusline scripts
- Co-authored-by config
- `apiKeyHelper`
- Local override settings (`settings.local.json`)
- IDE lock metadata (`~/.claude/ide/`)

---

## 10. Validation checklist

After every apply, `--validate-target` confirms:

1. `AGENTS.md` parses as Markdown and has no unresolved `@import`.
2. `.codex/config.toml` parses as TOML; `[features].codex_hooks` is set
   iff `.codex/hooks.json` exists.
3. Every entry under `.agents/skills/` has a valid `SKILL.md` with a
   `name` and `description` in frontmatter.
4. Every entry under `.codex/agents/` has a valid frontmatter and body.
5. No file under the target contains literal secrets matching common
   patterns (`AKIA...`, `ghp_...`, `sk-...`, `xoxb-...`).
6. No reference to source paths (`.claude/`, `~/.claude/`) remains in any
   generated artifact unless inside a manual-migration block.
