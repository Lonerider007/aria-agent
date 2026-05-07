import os
import subprocess
from pathlib import Path


def run_command(command: str, cwd: str = None, path: str = None) -> str:
    # Auto-add sudo for system package commands if not already present
    if any(cmd in command for cmd in ["apt-get", "apt ", "dpkg"]):
        if not command.strip().startswith("sudo"):
            command = "sudo " + command

    working_dir = cwd or path or os.getcwd()

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True,
            text=True, timeout=120, cwd=working_dir
        )
        out = (result.stdout + result.stderr).strip()
        return f"[CWD: {working_dir}]\n{out[:8000]}" if out else f"[CWD: {working_dir}]\n(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: command timed out (120s)"
    except Exception as e:
        return f"ERROR: {e}"


def run_tests(command: str = None, cwd: str = None) -> str:
    cmd = command or "pytest" if _has_pytest() else "python -m unittest discover"
    result = run_command(cmd, cwd=cwd)
    return result


def _has_pytest():
    import shutil
    return shutil.which("pytest") is not None
