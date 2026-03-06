# session-search skill

Use this skill when the user asks about Claude Code chat history, session logs,
conversation forks, or wants to search past conversations.

## Critical knowledge before using any session tool

Claude Code JSONL session files are **trees**, not linear logs.

- Each record has a `parentUuid` field linking it to its predecessor.
- When two records share the same `parentUuid`, that is a **fork point** —
  two diverging branches of the same conversation.
- A single `.jsonl` file may contain records from multiple `sessionId` values
  (this happens when a child session resumes a parent session).
- **Do not use raw `grep` to search sessions** — grep is blind to the tree
  structure and cannot tell you which branch a match is on.

## Session file locations

```
~/.claude/projects/{project-slug}/{session-uuid}.jsonl
```

Project slug = filesystem path with `/` replaced by `-`, prefixed with the
leading `-`. Example: `/home/aurora` → `-home-aurora`.

Subagent logs are in `{session-uuid}/subagents/` subdirectories and should
normally be searched separately.

## Using the CLI tool

All commands are available via `claude-session` (installed at
`~/_/claude-session-tools/bin/claude-session`):

```bash
# List all sessions with fork counts
python3 ~/_/claude-session-tools/bin/claude-session list

# Search for a string across all sessions, fork-aware
python3 ~/_/claude-session-tools/bin/claude-session search "your query"

# Show the conversation tree for a session
python3 ~/_/claude-session-tools/bin/claude-session tree <session-id-prefix>

# Show fork points in a session
python3 ~/_/claude-session-tools/bin/claude-session forks <session-id-prefix>

# Walk a specific branch from a uuid
python3 ~/_/claude-session-tools/bin/claude-session branch <session-id> <uuid-prefix>
```

## Common mistakes to avoid

1. **Do not grep JSONL files for content** — JSON-escaping, tree structure,
   and multi-session files all make raw grep unreliable. Use `claude-session search`.

2. **Do not assume one file = one conversation** — use `forks` to check.

3. **Do not assume the most recent file is the active session** — compare
   by process (`ps aux | grep claude`) and PTY to find which file is live.

4. **Content not yet on disk** — an active session writes records per-turn
   but may lag. If a user says "I can see it in my terminal," believe them
   before claiming the content doesn't exist.

5. **Two files containing overlapping content** — when a session is resumed,
   the child session's records may appear in the parent file tagged with the
   child's `sessionId`. Check `session_ids` in the tree, not just the filename.
