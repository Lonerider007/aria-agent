"""
Human-readable phrases for ARIA tool actions.
No raw tool names shown to user.
"""

def get_phrase(tool_name: str, args: dict) -> str:
    """Returns a natural language description of what ARIA is doing."""

    path     = args.get("path", args.get("filepath", ""))
    filename = path.split("/")[-1] if path else ""
    command  = args.get("command", "")
    query    = args.get("query", args.get("pattern", ""))
    name     = args.get("name", "")
    goal     = args.get("goal", "")

    phrases = {
        # File operations
        "read_file":         f"Reading {filename}..." if filename else "Reading file...",
        "write_file":        f"Writing {filename}..." if filename else "Writing file...",
        "edit_file":         f"Editing {filename}..." if filename else "Editing file...",
        "delete_file":       f"Removing {filename}..." if filename else "Removing file...",
        "list_files":        "Scanning project structure...",
        "search_in_files":   f"Searching codebase for '{query[:30]}'..." if query else "Searching codebase...",

        # Shell
        "run_command":       _format_command(command),
        "run_tests":         "Running the test suite...",

        # Git
        "git_status":        "Checking git status...",
        "git_diff":          "Reviewing changes...",
        "git_commit":        "Committing changes to git...",
        "git_create_branch": f"Creating branch '{args.get('name', '')}'...",
        "git_log":           "Reading commit history...",

        # Project
        "new_project":       f"Setting up project '{name}'..." if name else "Setting up project...",
        "list_projects":     "Looking up known projects...",
        "mark_milestone":    "Saving milestone...",
        "load_project_context": "Loading project context and history...",

        # Memory
        "save_memory":       "Saving to memory...",
        "read_memory":       "Loading from memory...",

        # Web
        "search_web":        f"Searching the web for '{query[:40]}'..." if query else "Searching the web...",

        # Plan / interaction (handled separately but just in case)
        "create_plan":       f"Planning: {goal[:50]}..." if goal else "Creating a plan...",
        "ask_clarification": "Asking a clarifying question...",
        "request_approval":  "Waiting for your approval...",
        "notify_user":       args.get("message", "")[:60],
    }

    return phrases.get(tool_name, f"Working on {tool_name.replace('_', ' ')}...")


def _format_command(cmd: str) -> str:
    cmd = cmd.strip()
    if not cmd:
        return "Running a command..."
    if "pytest" in cmd or "python -m pytest" in cmd:
        return "Running the tests..."
    if "pip install" in cmd:
        pkg = cmd.split("pip install")[-1].strip().split()[0][:25]
        return f"Installing {pkg}..."
    if "pip uninstall" in cmd:
        return "Removing a package..."
    if "pip list" in cmd or "pip show" in cmd:
        return "Checking installed packages..."
    if "git " in cmd:
        return "Running a git command..."
    if "mkdir" in cmd:
        return "Creating directories..."
    if "rm -rf" in cmd or "rm " in cmd:
        return "Cleaning up files..."
    if "curl" in cmd or "wget" in cmd:
        return "Fetching from the web..."
    if "uvicorn" in cmd or "gunicorn" in cmd:
        return "Starting the server..."
    if "chmod" in cmd:
        return "Setting file permissions..."
    if "cat " in cmd or "head " in cmd or "tail " in cmd:
        return "Reading file contents..."
    if "find " in cmd:
        return "Searching files..."
    if "ls " in cmd or "ls\n" in cmd:
        return "Listing files..."
    if "sleep" in cmd:
        return "Waiting..."
    return f"Running: {cmd[:45]}..."
