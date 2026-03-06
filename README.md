# claude-session-tools

Fork-aware Claude Code session search and inspection.

## The problem with every other tool

All existing tools ([claude-code-log](https://github.com/daaain/claude-code-log),
[cclv](https://github.com/albertov/cclv),
[claude-replay](https://github.com/es617/claude-replay),
[@constellos/claude-code-kit](https://www.npmjs.com/package/@constellos/claude-code-kit),
etc.) treat Claude Code JSONL files as **linear logs**.

They are not. They are **trees**.

Each record has a `parentUuid` field. When two records share the same
`parentUuid`, the conversation has **forked** — two branches exist from that
point forward, both stored in the same file. You can resume a session in two
terminals, have both conversations diverge, and the single JSONL file contains
both branches as a tree.

Raw `grep` on a JSONL file is also unreliable:
- A single file may contain records from multiple `sessionId` values
- Content from an active session may not be flushed to disk yet
- Matches in one branch look identical to matches in another

This library correctly parses the tree.

## Install

No external dependencies. Pure Python 3.8+.

```bash
git clone https://github.com/aurora-thesean/claude-session-tools
cd claude-session-tools
ln -s "$PWD/bin/claude-session" ~/.local/bin/claude-session
```

## Usage

```bash
# List all sessions with fork counts
claude-session list

# Search across all sessions, fork-aware
claude-session search "en_core_web_sm"

# Show conversation tree for a session
claude-session tree 22262eab

# Show fork points
claude-session forks 22262eab

# Walk a specific branch from a uuid
claude-session branch 22262eab 7be366c9
```

## JSONL format reference (observed, 2026-03)

Each line is a JSON object. Relevant fields:

| Field | Type | Description |
|-------|------|-------------|
| `uuid` | string | Unique ID for this record within the file |
| `parentUuid` | string\|null | Links to predecessor. Fork = multiple records with same parentUuid |
| `type` | string | `user`, `assistant`, `system`, `progress`, `queue-operation`, `file-history-snapshot` |
| `sessionId` | string | Which session generated this record. One file can have multiple. |
| `timestamp` | string | ISO-8601 |
| `message` | dict | Anthropic API message: `.role`, `.content` (list of blocks), `.model`, `.id` |
| `isSidechain` | bool | Whether this is a tool-use sidechain |
| `cwd` | string | Working directory at time of record |
| `version` | string | claude-code version |

Content blocks inside `message.content`:
- `{"type": "text", "text": "..."}` — main text
- `{"type": "thinking", "thinking": "..."}` — extended thinking
- `{"type": "tool_use", ...}` — tool call
- `{"type": "tool_result", ...}` — tool result

## Claude Code skill

Install the skill for agents:

```bash
mkdir -p ~/.claude/skills
cp skills/session-search.md ~/.claude/skills/
```

Agents can then invoke it with `/session-search` or by referencing the skill
in CLAUDE.md.

## Related tools in the ecosystem

- [claude-JSONL-browser](https://github.com/withLinda/claude-JSONL-browser) — web viewer
- [claude-code-log](https://github.com/daaain/claude-code-log) — HTML/Markdown export
- [ccusage](https://github.com/ryoppippi/ccusage) — token usage analysis
- [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) — curated list

## Part of the Thesean software ecosystem

This package follows [agent-packaging-standard](https://github.com/aurora-thesean/agent-packaging-standard):
FHS + semver artifact identity. Versioned at `~/.local/opt/aurora-thesean/claude-session-tools/`.

## License

MIT
