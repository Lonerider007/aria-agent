"""Relation graph — (src, relation, dst, weight, ts) store.

Lightweight semantic graph in SQLite. Auto-recorded events:
  - file edits:           (file_path, 'modified_by', task_id)
  - file creates:         (file_path, 'created_in', project)
  - project switches:     (project, 'switched_to', timestamp)
  - tool errors:          (file_path, 'error_during', task_id)
  - acceptance results:   (project, 'verified_at', task_id)
  - api spec fetches:     (domain, 'spec_fetched_for', task_id)

Used by recall.py to boost relevance scores for entities related to the current query.
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

DB_PATH = Path.home() / ".aria" / "relations.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.execute(
        "CREATE TABLE IF NOT EXISTS relations ("
        "id INTEGER PRIMARY KEY,"
        "src TEXT NOT NULL,"
        "relation TEXT NOT NULL,"
        "dst TEXT NOT NULL,"
        "weight REAL DEFAULT 1.0,"
        "ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    c.execute("CREATE INDEX IF NOT EXISTS idx_src ON relations(src)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_dst ON relations(dst)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_rel ON relations(relation)")
    return c


def add(src: str, relation: str, dst: str, weight: float = 1.0) -> None:
    if not src or not relation or not dst:
        return
    try:
        with _conn() as c:
            c.execute(
                "INSERT INTO relations(src,relation,dst,weight,ts) VALUES (?,?,?,?,?)",
                (str(src)[:300], str(relation)[:60], str(dst)[:300], float(weight), datetime.now().isoformat()),
            )
    except Exception:
        pass  # graph is best-effort; never break the agent


def query(src: str = None, relation: str = None, dst: str = None, limit: int = 50) -> List[Tuple]:
    """Return (src, relation, dst, weight, ts) tuples matching any of the criteria."""
    try:
        with _conn() as c:
            sql = "SELECT src,relation,dst,weight,ts FROM relations WHERE 1=1"
            params: list = []
            if src:
                sql += " AND src = ?"; params.append(src)
            if relation:
                sql += " AND relation = ?"; params.append(relation)
            if dst:
                sql += " AND dst = ?"; params.append(dst)
            sql += " ORDER BY ts DESC LIMIT ?"
            params.append(limit)
            return list(c.execute(sql, params))
    except Exception:
        return []


def neighbors(node: str, depth: int = 1, limit: int = 30) -> List[str]:
    """Return nodes connected to `node` within `depth` hops (deduped)."""
    if not node:
        return []
    seen = {node}
    frontier = {node}
    for _ in range(max(1, depth)):
        next_frontier: set = set()
        for n in frontier:
            for row in query(src=n, limit=limit):
                next_frontier.add(row[2])
            for row in query(dst=n, limit=limit):
                next_frontier.add(row[0])
        new = next_frontier - seen
        if not new:
            break
        seen.update(new)
        frontier = new
    seen.discard(node)
    return list(seen)[:limit]


def stats() -> dict:
    try:
        with _conn() as c:
            total = c.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
            rels = dict(c.execute("SELECT relation, COUNT(*) FROM relations GROUP BY relation").fetchall())
            return {"total": total, "by_relation": rels}
    except Exception:
        return {"total": 0, "by_relation": {}}
