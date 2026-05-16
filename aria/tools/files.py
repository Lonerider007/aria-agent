import os
from pathlib import Path
from aria.ui.diff import show_diff


MAX_OUTPUT_CHARS = 16000  # cap any single tool output to ~4k tokens


def _cap(text: str, label: str = "output") -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    head = text[:MAX_OUTPUT_CHARS]
    omitted = len(text) - MAX_OUTPUT_CHARS
    return f"{head}\n\n[TRUNCATED: {omitted:,} chars omitted — {label} too large; narrow your query]"


def read_file(path: str) -> str:
    try:
        return _cap(Path(path).read_text(encoding="utf-8"), label=f"file {path}")
    except Exception as e:
        return f"ERROR: {e}"


def write_file(path: str, content: str) -> str:
    try:
        from aria.tools.undo_log import record as _undo_record
        _undo_record("write", path)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written: {path}"
    except Exception as e:
        return f"ERROR: {e}"


def edit_file(path: str, old_str: str, new_str: str) -> str:
    try:
        from aria.tools.undo_log import record as _undo_record
        _undo_record("edit", path)
        p = Path(path)
        original = p.read_text(encoding="utf-8")
        if old_str not in original:
            return f"ERROR: string not found in {path}"
        updated = original.replace(old_str, new_str, 1)
        p.write_text(updated, encoding="utf-8")
        show_diff(path, old_str, new_str)
        return f"Edited: {path}"
    except Exception as e:
        return f"ERROR: {e}"


def delete_file(path: str) -> str:
    try:
        from aria.tools.undo_log import record as _undo_record
        _undo_record("delete", path)
        Path(path).unlink()
        return f"Deleted: {path}"
    except Exception as e:
        return f"ERROR: {e}"


MAX_LIST_ENTRIES = 500  # never return more file paths than this


def list_files(path: str = ".", recursive: bool = False) -> str:
    try:
        p = Path(path)
        if recursive:
            # Skip well-known noise dirs and cap entries
            SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv",
                    "dist", "build", ".mypy_cache", ".pytest_cache", ".tox"}
            files = []
            for f in p.rglob("*"):
                if any(part in SKIP for part in f.parts):
                    continue
                if f.is_file():
                    files.append(str(f.relative_to(p)))
                    if len(files) >= MAX_LIST_ENTRIES:
                        files.append(f"[TRUNCATED: stopped at {MAX_LIST_ENTRIES} entries — narrow path or use search_in_files]")
                        break
        else:
            files = [f.name for f in sorted(p.iterdir())]
        return _cap("\n".join(files) or "(empty)", label=f"listing of {path}")
    except Exception as e:
        return f"ERROR: {e}"


def search_in_files(pattern: str, path: str = ".", file_pattern: str = None) -> str:
    from aria.tools.shell import run_command
    import shlex
    safe_pattern = shlex.quote(pattern)
    safe_path    = shlex.quote(str(Path(path).resolve()))
    # Cap matches early: -m 200 per file, exclude common noise dirs
    cmd = (
        f"grep -rn -m 200 "
        f"--exclude-dir=.git --exclude-dir=node_modules --exclude-dir=__pycache__ "
        f"--exclude-dir=.venv --exclude-dir=venv --exclude-dir=dist --exclude-dir=build "
        f"{safe_pattern} {safe_path}"
    )
    if file_pattern:
        safe_fp = shlex.quote(file_pattern)
        cmd += f' --include={safe_fp}'
    raw = run_command(cmd)
    return _cap(raw, label=f"grep results for '{pattern[:40]}'")
