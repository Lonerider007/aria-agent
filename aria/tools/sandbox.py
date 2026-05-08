"""
ARIA Sandbox — isolated workspace for experiments.
Safe area where ARIA can work without touching real projects.
"""
import os
import subprocess
from pathlib import Path
from datetime import datetime

SANDBOX_DIR = Path.home() / ".aria" / "sandboxes"


def create_sandbox(name: str = "default") -> str:
    """Create an isolated sandbox workspace."""
    sandbox = SANDBOX_DIR / name
    sandbox.mkdir(parents=True, exist_ok=True)

    # Git init if not exists
    if not (sandbox / ".git").exists():
        subprocess.run("git init", shell=True, cwd=sandbox, capture_output=True)

    # venv if not exists
    venv = sandbox / ".venv"
    if not venv.exists():
        subprocess.run("python3 -m venv .venv", shell=True, cwd=sandbox, capture_output=True)

    # .gitignore
    gi = sandbox / ".gitignore"
    if not gi.exists():
        gi.write_text(".venv/\n__pycache__/\n*.pyc\n.env\n")

    # meta
    meta = sandbox / ".aria_sandbox.json"
    import json
    info = {
        "name": name,
        "created": datetime.now().isoformat(),
        "path": str(sandbox)
    }
    meta.write_text(json.dumps(info, indent=2))

    return str(sandbox)


def list_sandboxes() -> str:
    if not SANDBOX_DIR.exists():
        return "(no sandboxes)"
    boxes = [d.name for d in SANDBOX_DIR.iterdir() if d.is_dir()]
    return "\n".join(boxes) if boxes else "(no sandboxes)"


def get_sandbox_path(name: str = "default") -> str:
    return str(SANDBOX_DIR / name)
