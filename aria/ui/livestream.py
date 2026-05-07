"""
Live Stream Bar — real-time status ticker at the bottom of the terminal.
Like a news channel's breaking news bar. Always honest. Always visible.
"""
import time
import threading
from prompt_toolkit.formatted_text import HTML

_state = {
    "message":     "Ready",
    "step":        0,
    "last_update": time.time(),
}
_lock = threading.Lock()

TOOL_MESSAGES = {
    "write_file":           lambda a: f"Writing {_basename(a.get('path',''))}...",
    "edit_file":            lambda a: f"Editing {_basename(a.get('path',''))}...",
    "read_file":            lambda a: f"Reading {_basename(a.get('path',''))}...",
    "delete_file":          lambda a: f"Deleting {_basename(a.get('path',''))}...",
    "list_files":           lambda a: "Scanning project files...",
    "search_in_files":      lambda a: f"Searching '{a.get('pattern','')[:30]}'...",
    "run_command":          lambda a: _format_command(a.get("command", "")),
    "run_tests":            lambda a: "Running tests...",
    "git_status":           lambda a: "Checking git status...",
    "git_diff":             lambda a: "Reviewing changes...",
    "git_commit":           lambda a: "Committing changes...",
    "git_create_branch":    lambda a: f"Creating branch '{a.get('name','')}'...",
    "new_project":          lambda a: f"Scaffolding '{a.get('name','')}'...",
    "save_memory":          lambda a: "Saving to memory...",
    "read_memory":          lambda a: "Loading memory...",
    "load_project_context": lambda a: "Loading project context...",
    "create_plan":          lambda a: f"Planning: {a.get('goal','')[:50]}",
    "ask_clarification":    lambda a: "Asking for clarification...",
    "request_approval":     lambda a: "Waiting for your approval...",
    "notify_user":          lambda a: a.get("message", "")[:60],
}


def _basename(path: str) -> str:
    return path.split("/")[-1] if path else "file"


def _format_command(cmd: str) -> str:
    cmd = cmd.strip()
    if "pytest" in cmd:      return "Running tests..."
    if "pip install" in cmd: return f"Installing {cmd.split('pip install')[-1].strip()[:25]}..."
    if "pip uninstall" in cmd: return "Removing package..."
    if "pip list" in cmd:    return "Checking packages..."
    if "mkdir" in cmd:       return "Creating directories..."
    if "rm " in cmd:         return "Cleaning up..."
    if "git " in cmd:        return "Running git command..."
    if cmd:                  return f"Running: {cmd[:40]}..."
    return "Executing command..."


def update(tool_name: str, args: dict, step: int = 0):
    fn  = TOOL_MESSAGES.get(tool_name)
    msg = fn(args) if fn else f"Processing {tool_name}..."
    with _lock:
        _state["message"]     = msg
        _state["step"]        = step
        _state["last_update"] = time.time()


def set_thinking():
    with _lock:
        _state["message"]     = "Thinking..."
        _state["last_update"] = time.time()


def set_ready():
    with _lock:
        _state["message"]     = "Ready"
        _state["step"]        = 0
        _state["last_update"] = time.time()


def set_done(summary: str = "Task complete"):
    with _lock:
        _state["message"]     = summary[:60]
        _state["last_update"] = time.time()


def print_bar():
    """Print a one-line status bar inline — visible during execution."""
    from aria.ui.console import console
    with _lock:
        msg  = _state["message"]
        step = _state["step"]

    step_part = f"  [dim]step {step}[/dim]" if step > 0 else ""

    if any(w in msg.lower() for w in ["error", "fail"]):
        icon, style = "✗", "aria.error"
    elif any(w in msg.lower() for w in ["complete", "done", "pass"]):
        icon, style = "✓", "aria.success"
    elif "thinking" in msg.lower():
        icon, style = "◉", "aria.primary"
    else:
        icon, style = "◉", "aria.cyan"

    console.print(
        f"  [{style}]{icon}[/{style}] [dim]{msg}[/dim]{step_part}",
        highlight=False
    )


def get_toolbar():
    with _lock:
        msg     = _state["message"]
        step    = _state["step"]
        elapsed = time.time() - _state["last_update"]

    # Watchdog
    if elapsed > 30 and msg != "Ready":
        suffix = f" ({int(elapsed)}s)"
        icon   = "⚠"
        color  = "ansiyellow"
    else:
        suffix = f"  step {step}" if step > 0 else ""
        if msg == "Ready":
            icon, color = "◉", "ansibrightblack"
        elif any(w in msg.lower() for w in ["error", "fail"]):
            icon, color = "✗", "ansired"
        elif any(w in msg.lower() for w in ["test", "running"]):
            icon, color = "◉", "ansicyan"
        elif any(w in msg.lower() for w in ["complete", "done", "pass"]):
            icon, color = "✓", "ansigreen"
        elif "thinking" in msg.lower():
            icon, color = "◉", "ansimagenta"
        else:
            icon, color = "◉", "ansibrightmagenta"

    return HTML(
        f'<style bg="ansiblack" fg="{color}"> {icon} ARIA  {msg}{suffix} </style>'
    )
