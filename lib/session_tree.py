"""
session_tree.py — Fork-aware Claude Code session parser.

Claude Code stores conversations as JSONL files in:
    ~/.claude/projects/{project-slug}/{session-uuid}.jsonl

CRITICAL: The JSONL is NOT a linear log. It is a TREE. The `parentUuid`
field links each record to its parent, forming a directed tree. When two
records share the same `parentUuid`, that is a FORK POINT — two branches
diverging from the same conversation state.

A single file may also contain records from multiple sessions (different
`sessionId` values), e.g. when a child session's records are written back
into the parent session file upon resume.

All existing tools (claude-code-log, cclv, claude-replay, etc.) as of
2026-03 treat the JSONL as linear and are blind to fork structure.

Record fields (observed, not guaranteed complete):
    uuid          — unique ID for this record in this file
    parentUuid    — UUID of the predecessor record (None for root)
    type          — user | assistant | system | progress | queue-operation
                    | file-history-snapshot
    sessionId     — which session generated this record
    timestamp     — ISO-8601
    message       — dict with Anthropic API message structure
                    .role, .content (list of blocks), .model, .id
    isSidechain   — bool, whether this is a tool-use sidechain
    cwd           — working directory when record was created
    version       — claude-code version string
    gitBranch     — git branch at time of record
    permissionMode
"""

import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


PROJECTS_DIR = Path.home() / ".claude" / "projects"


@dataclass
class Record:
    uuid: str
    parent_uuid: Optional[str]
    type: str
    session_id: str
    timestamp: str
    message: dict
    raw: dict

    def text(self) -> str:
        """Extract plain text content from the message."""
        msg = self.message
        if not isinstance(msg, dict):
            return ""
        content = msg.get("content", [])
        if isinstance(content, str):
            return content
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif block.get("type") == "thinking":
                parts.append("[thinking] " + block.get("thinking", ""))
        return "\n".join(parts)

    def role(self) -> str:
        msg = self.message
        if isinstance(msg, dict):
            return msg.get("role", self.type)
        return self.type


class SessionTree:
    """
    A conversation tree loaded from a single JSONL session file.

    The tree is built from parentUuid links. Use fork_points() to find
    where branches diverge. Use branch(uuid) to walk a specific branch.
    """

    def __init__(self, path: Path):
        self.path = path
        self.session_id = path.stem
        self.records: dict[str, Record] = {}        # uuid -> Record
        self.children: dict[str, list[str]] = defaultdict(list)  # parentUuid -> [uuid]
        self.roots: list[str] = []
        self.session_ids: set[str] = set()
        self._load()

    def _load(self):
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                uuid = obj.get("uuid")
                if not uuid:
                    continue

                rec = Record(
                    uuid=uuid,
                    parent_uuid=obj.get("parentUuid"),
                    type=obj.get("type", "?"),
                    session_id=obj.get("sessionId", ""),
                    timestamp=obj.get("timestamp", ""),
                    message=obj.get("message", {}),
                    raw=obj,
                )
                self.records[uuid] = rec
                self.session_ids.add(rec.session_id)

                if rec.parent_uuid:
                    self.children[rec.parent_uuid].append(uuid)
                else:
                    self.roots.append(uuid)

    def fork_points(self) -> list[tuple[str, list[str]]]:
        """
        Return list of (parent_uuid, [child_uuids]) where branching occurs.
        Only includes conversation forks (user/assistant children), not
        incidental progress/system racing.
        """
        forks = []
        for parent_uuid, child_uuids in self.children.items():
            if len(child_uuids) < 2:
                continue
            # Filter to meaningful types only
            meaningful = [
                u for u in child_uuids
                if self.records.get(u) and
                   self.records[u].type in ("user", "assistant", "system")
            ]
            if len(meaningful) >= 2:
                forks.append((parent_uuid, meaningful))
        return sorted(forks, key=lambda x: self.records.get(x[0], Record("","","","","",{},{})).timestamp)

    def branch(self, from_uuid: str) -> list[Record]:
        """
        Walk the primary (first-child) branch from a given uuid to a leaf.
        Returns records in order.
        """
        result = []
        current = from_uuid
        visited = set()
        while current and current not in visited:
            visited.add(current)
            rec = self.records.get(current)
            if rec:
                result.append(rec)
            kids = self.children.get(current, [])
            current = kids[0] if kids else None
        return result

    def branch_from_parent(self, parent_uuid: str, child_uuid: str) -> list[Record]:
        """Walk a specific branch starting at child_uuid."""
        return self.branch(child_uuid)

    def ancestors(self, uuid: str) -> list[Record]:
        """Return all ancestors of a record, oldest first."""
        chain = []
        current = uuid
        visited = set()
        while current and current not in visited:
            visited.add(current)
            rec = self.records.get(current)
            if not rec:
                break
            chain.append(rec)
            current = rec.parent_uuid
        return list(reversed(chain))

    def search(self, query: str, case_sensitive: bool = False) -> list[tuple[Record, list[Record]]]:
        """
        Search all records for query string.
        Returns list of (matching_record, ancestor_chain).
        """
        if not case_sensitive:
            query = query.lower()

        results = []
        for rec in self.records.values():
            if rec.type not in ("user", "assistant"):
                continue
            text = rec.text()
            hay = text if case_sensitive else text.lower()
            if query in hay:
                results.append((rec, self.ancestors(rec.uuid)))
        return results

    def conversation_threads(self) -> list[list[Record]]:
        """
        Return all leaf-to-root paths as separate conversation threads.
        Each thread is one complete branch of the tree.
        """
        def find_leaves():
            all_uuids = set(self.records.keys())
            parent_uuids = set(self.children.keys())
            return all_uuids - parent_uuids

        threads = []
        for leaf in find_leaves():
            thread = self.ancestors(leaf)
            if thread:
                threads.append(thread)
        return threads


def all_sessions() -> list[SessionTree]:
    """Load all session trees from ~/.claude/projects/."""
    sessions = []
    if not PROJECTS_DIR.exists():
        return sessions
    for jsonl in PROJECTS_DIR.rglob("*.jsonl"):
        if "/subagents/" in str(jsonl):
            continue
        try:
            sessions.append(SessionTree(jsonl))
        except Exception:
            pass
    return sessions


def find_session(session_id_prefix: str) -> Optional[SessionTree]:
    """Find a session by UUID prefix."""
    for jsonl in PROJECTS_DIR.rglob("*.jsonl"):
        if jsonl.stem.startswith(session_id_prefix):
            return SessionTree(jsonl)
    return None
