"""Undo log — track recent file mutations so `/undo` can reverse them.

Captures a backup BEFORE every write_file / edit_file / delete_file. Stored under
`~/.aria/undo/<session>/<seq>.json` with the original content. On `/undo`, the
last entry is restored and removed from the log.

Out of scope (intentionally): run_command rollback, git revert. For those use git.
"""
import json
import os
import shutil
import time
from pathlib import Path
from typing import List, Optional

UNDO_DIR = Path.home() / ".aria" / "undo"


def _session_dir() -> Path:
    # One dir per parent process (so each `aria` invocation has its own)
    d = UNDO_DIR / str(os.getppid())
    d.mkdir(parents=True, exist_ok=True)
    return d


def _next_seq(d: Path) -> int:
    existing = [int(p.stem) for p in d.glob("*.json") if p.stem.isdigit()]
    return (max(existing) + 1) if existing else 1


def record(action: str, path: str) -> None:
    """Snapshot a file BEFORE a mutation. action in {write, edit, delete}."""
    if not path:
        return
    try:
        p = Path(path).expanduser()
        d = _session_dir()
        seq = _next_seq(d)
        entry = {
            "action": action,
            "path": str(p),
            "ts": time.time(),
            "existed": p.exists(),
            "content": None,
        }
        if p.exists() and p.is_file():
            try:
                entry["content"] = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                entry["content"] = None  # binary — can't snapshot in this lightweight log
                entry["binary"] = True
        (d / f"{seq:04d}.json").write_text(json.dumps(entry))
    except Exception:
        pass  # best-effort


def list_entries(limit: int = 10) -> List[dict]:
    d = _session_dir()
    files = sorted(d.glob("*.json"), reverse=True)[:limit]
    out = []
    for f in files:
        try:
            entry = json.loads(f.read_text())
            entry["_file"] = str(f)
            out.append(entry)
        except Exception:
            continue
    return out


def undo_last() -> str:
    d = _session_dir()
    files = sorted(d.glob("*.json"), reverse=True)
    if not files:
        return "Nothing to undo in this session."
    latest = files[0]
    try:
        entry = json.loads(latest.read_text())
    except Exception as e:
        return f"ERROR: cannot read undo entry: {e}"

    p = Path(entry["path"])
    action = entry.get("action", "?")

    if entry.get("binary"):
        latest.unlink(missing_ok=True)
        return f"SKIPPED: '{p}' was binary; not snapshotted. Use git to recover."

    try:
        if entry["existed"]:
            # Restore previous content
            p.parent.mkdir(parents=True, exist_ok=True)
            if entry.get("content") is not None:
                p.write_text(entry["content"], encoding="utf-8")
                msg = f"Restored '{p}' to pre-{action} state."
            else:
                msg = f"Could not restore content for '{p}' (no snapshot)."
        else:
            # File did not exist before — delete the current file
            if p.exists() and p.is_file():
                p.unlink()
                msg = f"Removed '{p}' (it did not exist before {action})."
            else:
                msg = f"'{p}' is already absent."
        latest.unlink(missing_ok=True)
        return msg
    except Exception as e:
        return f"ERROR undoing: {e}"


def clear_session() -> str:
    d = _session_dir()
    count = 0
    for f in d.glob("*.json"):
        try:
            f.unlink(); count += 1
        except OSError:
            pass
    return f"Cleared {count} undo entries."
