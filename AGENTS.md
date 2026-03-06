# AGENTS.md — claude-session-tools
# BIAFRAL warrant for ~/_/claude-session-tools/

## Purpose

Fork-aware Claude Code session search library.
Corrects the ecosystem-wide assumption that JSONL = linear log.

## Key invariant

A Claude Code JSONL session file is a TREE. parentUuid creates the structure.
Fork points are nodes with multiple children. Do not treat it as linear.

## Agent instructions

- Use `claude-session search` instead of grep for session content search
- Use `claude-session forks` before claiming a session has no forks
- Trust user reports over negative grep results on active sessions
