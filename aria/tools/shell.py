import os
import subprocess
from pathlib import Path

_BACKGROUND_PROCESSES = {}


def run_command(command: str, cwd: str = None, path: str = None, background: bool = False) -> str:
    # Auto-add sudo for system package commands if not already present
    if any(cmd in command for cmd in ["apt-get", "apt ", "dpkg"]):
        if not command.strip().startswith("sudo"):
            command = "sudo " + command

    working_dir = cwd or path or os.getcwd()

    # Background mode — for servers, long-running processes
    if background or any(kw in command for kw in ["uvicorn", "gunicorn", "flask run", "python -m http", "python manage.py runserver"]):
        try:
            proc = subprocess.Popen(
                command, shell=True, cwd=working_dir,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            _BACKGROUND_PROCESSES[command[:50]] = proc
            return f"[CWD: {working_dir}]\nStarted in background (PID: {proc.pid}). Use 'ps aux | grep python' to verify."
        except Exception as e:
            return f"ERROR starting background process: {e}"

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True,
            text=True, timeout=120, cwd=working_dir
        )
        out = (result.stdout + result.stderr).strip()
        return f"[CWD: {working_dir}]\n{out[:8000]}" if out else f"[CWD: {working_dir}]\n(no output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: command timed out (120s). Tip: for servers use background=true or append '&' to command."
    except Exception as e:
        return f"ERROR: {e}"


def run_tests(command: str = None, cwd: str = None) -> str:
    cmd = command or "pytest" if _has_pytest() else "python -m unittest discover"
    result = run_command(cmd, cwd=cwd)
    return result


def _has_pytest():
    import shutil
    return shutil.which("pytest") is not None
