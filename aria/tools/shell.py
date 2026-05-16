import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

# Track background processes with metadata
_BACKGROUND_PROCESSES: Dict[str, Tuple[subprocess.Popen, float]] = {}
_MAX_BACKGROUND_PROCESSES = 10
_LAST_CLEANUP_TIME = 0
_CLEANUP_INTERVAL = 30  # seconds


def _cleanup_background_processes():
    """Reap finished background processes and enforce limits."""
    global _LAST_CLEANUP_TIME
    current_time = time.time()
    
    # Only cleanup periodically to avoid overhead
    if current_time - _LAST_CLEANUP_TIME < _CLEANUP_INTERVAL:
        return
    
    to_remove = []
    for key, (proc, start_time) in list(_BACKGROUND_PROCESSES.items()):
        # Check if process has finished
        if proc.poll() is not None:
            to_remove.append(key)
        # Optional: enforce max age for safety (e.g., 24 hours)
        elif current_time - start_time > 86400:  # 24 hours
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            to_remove.append(key)
    
    # Remove finished/terminated processes
    for key in to_remove:
        del _BACKGROUND_PROCESSES[key]
    
    # Enforce limit: remove oldest if over limit
    if len(_BACKGROUND_PROCESSES) > _MAX_BACKGROUND_PROCESSES:
        # Sort by start time (oldest first)
        sorted_items = sorted(_BACKGROUND_PROCESSES.items(), key=lambda x: x[1][1])
        to_remove = sorted_items[:len(_BACKGROUND_PROCESSES) - _MAX_BACKGROUND_PROCESSES]
        for key, (proc, _) in to_remove:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            except Exception:
                pass  # Process might already be gone
            del _BACKGROUND_PROCESSES[key]
    
    _LAST_CLEANUP_TIME = current_time


def run_command(command: str, cwd: str = None, path: str = None, background: bool = False) -> str:
    # Auto-add sudo for system package commands if not already present
    if any(cmd in command for cmd in ["apt-get", "apt ", "dpkg"]):
        if not command.strip().startswith("sudo"):
            command = "sudo " + command

    working_dir = cwd or path or os.getcwd()

    # Cleanup background processes periodically
    _cleanup_background_processes()

    # Background mode — for servers, long-running processes
    if background or any(kw in command for kw in ["uvicorn", "gunicorn", "flask run", "python -m http", "python manage.py runserver"]):
        # Check if we're at limit
        if len(_BACKGROUND_PROCESSES) >= _MAX_BACKGROUND_PROCESSES:
            return f"ERROR: Maximum background processes ({_MAX_BACKGROUND_PROCESSES}) reached. Wait for some to finish or manually cleanup."
        
        try:
            proc = subprocess.Popen(
                command, shell=True, cwd=working_dir,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                start_new_session=True  # Better process isolation
            )
            # Use a more unique key including timestamp to avoid collisions
            key = f"{command[:30]}_{int(time.time())}"
            _BACKGROUND_PROCESSES[key] = (proc, time.time())
            return f"[CWD: {working_dir}]\nStarted in background (PID: {proc.pid}). Use 'ps aux | grep python' to verify. Key: {key}"
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


def cleanup_background_processes(force: bool = False) -> str:
    """Manually trigger cleanup of background processes.
    
    Args:
        force: If True, terminate all background processes
    
    Returns:
        Status message
    """
    global _LAST_CLEANUP_TIME
    _cleanup_background_processes()  # Regular cleanup
    
    if force:
        # Terminate all background processes
        terminated = 0
        for key, (proc, start_time) in list(_BACKGROUND_PROCESSES.items()):
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                terminated += 1
            except Exception:
                pass  # Process might already be gone
            del _BACKGROUND_PROCESSES[key]
        _LAST_CLEANUP_TIME = time.time()
        return f"Forcefully terminated {terminated} background processes."
    else:
        # Just return status
        active = len(_BACKGROUND_PROCESSES)
        return f"Background process cleanup completed. {active} active background processes running."


def get_background_processes() -> str:
    """Get information about currently running background processes."""
    _cleanup_background_processes()  # Update status
    
    if not _BACKGROUND_PROCESSES:
        return "No background processes running."
    
    lines = ["Background processes:"]
    for key, (proc, start_time) in _BACKGROUND_PROCESSES.items():
        status = "running" if proc.poll() is None else f"finished (exit code: {proc.poll()})"
        runtime = time.time() - start_time
        lines.append(f"- PID: {proc.pid} | Key: {key} | Status: {status} | Runtime: {runtime:.0f}s")
    
    return "\n".join(lines)


def run_tests(command: str = None, cwd: str = None) -> str:
    cmd = command or "pytest" if _has_pytest() else "python -m unittest discover"
    result = run_command(cmd, cwd=cwd)
    return result


def _has_pytest():
    import shutil
    return shutil.which("pytest") is not None