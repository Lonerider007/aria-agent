import os
from pathlib import Path
from aria.ui.diff import show_diff


def read_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception as e:
        return f"ERROR: {e}"


def write_file(path: str, content: str) -> str:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written: {path}"
    except Exception as e:
        return f"ERROR: {e}"


def edit_file(path: str, old_str: str, new_str: str) -> str:
    try:
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
        Path(path).unlink()
        return f"Deleted: {path}"
    except Exception as e:
        return f"ERROR: {e}"


def list_files(path: str = ".", recursive: bool = False) -> str:
    try:
        p = Path(path)
        if recursive:
            files = [str(f.relative_to(p)) for f in p.rglob("*") if f.is_file()]
        else:
            files = [f.name for f in sorted(p.iterdir())]
        return "\n".join(files) or "(empty)"
    except Exception as e:
        return f"ERROR: {e}"


def search_in_files(pattern: str, path: str = ".", file_pattern: str = None) -> str:
    from aria.tools.shell import run_command
    import shlex
    safe_pattern = shlex.quote(pattern)
    safe_path    = shlex.quote(str(Path(path).resolve()))
    cmd = f'grep -rn {safe_pattern} {safe_path}'
    if file_pattern:
        safe_fp = shlex.quote(file_pattern)
        cmd += f' --include={safe_fp}'
    return run_command(cmd)
