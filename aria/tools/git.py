import os
import shlex
import subprocess
from aria.tools.shell import run_command


def git_status(cwd: str = None, path: str = None) -> str:
    return run_command("git status --short", cwd=cwd or path)


def git_diff(cwd: str = None, path: str = None) -> str:
    return run_command("git diff", cwd=cwd or path)


def git_commit(message: str, cwd: str = None, path: str = None) -> str:
    """Commit safely — uses subprocess list form to avoid shell injection via message."""
    wd = cwd or path or os.getcwd()
    try:
        add = subprocess.run(["git", "add", "-A"], cwd=wd, capture_output=True, text=True, timeout=30)
        if add.returncode != 0:
            return f"ERROR: git add failed: {add.stderr.strip()}"
        commit = subprocess.run(
            ["git", "commit", "-m", message or "update"],
            cwd=wd, capture_output=True, text=True, timeout=30,
        )
        out = (commit.stdout + commit.stderr).strip()
        return f"[CWD: {wd}]\n{out[:2000]}"
    except subprocess.TimeoutExpired:
        return "ERROR: git commit timed out (30s)."
    except Exception as e:
        return f"ERROR: {e}"


def git_create_branch(name: str, cwd: str = None, path: str = None) -> str:
    if not name or any(c in name for c in (" ", ";", "&", "|", "$", "`", "\n")):
        return f"ERROR: invalid branch name '{name}'"
    return run_command(f"git checkout -b {shlex.quote(name)}", cwd=cwd or path)


def git_log(n: int = 5, cwd: str = None, path: str = None) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 5
    return run_command(f"git log --oneline -{n}", cwd=cwd or path)
