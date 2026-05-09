# migrate-to-codex (skill bundle)

Claude Code skill that migrates a Claude Code configuration tree into the
equivalent Codex configuration. One-way, non-destructive.

## Layout

```
migrate-to-codex/
├── SKILL.md                    # Skill entrypoint (Claude Code reads this)
├── README.md                   # You are here
└── references/
    ├── protocol.md             # Full agent behavior contract
    └── differences.md          # Surface-by-surface mapping (Claude → Codex)
```

The migrator script (`scripts/migrate-to-codex.py`) is **not** included in
this bundle; install it separately under
`.codex/skills/migrate-to-codex/scripts/` (the path the SKILL.md references).
The skill itself only carries the rules + spec.

## Install

Project scope:
```
cp -R panbk-agent-config/skills/migrate-to-codex .claude/skills/
```

User scope:
```
cp -R panbk-agent-config/skills/migrate-to-codex ~/.claude/skills/
```

## Trigger phrases

- "migrate to Codex"
- "switch to Codex"
- "convert .claude to .codex"
- "produce .codex from this .claude tree"

## Scope

In scope:
- Reading `.claude/` / `~/.claude/` / `.mcp.json` / `.claude.json`.
- Writing `AGENTS.md`, `.codex/`, `.agents/`, `~/.codex/`.

Out of scope:
- Reverse migration (Codex → Claude Code).
- Editing source Claude Code files.
- Touching unrelated repos / secrets.

See `SKILL.md` for the full contract.
