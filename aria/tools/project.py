import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
from aria.memory.store import MEMORY_DIR, project_dir


def new_project(name: str, description: str, stack: str, path: str = None) -> str:
    workspace = Path(path or os.getcwd()) / name.replace(" ", "-").lower()
    workspace.mkdir(parents=True, exist_ok=True)

    subprocess.run("git init", shell=True, cwd=workspace, capture_output=True)

    (workspace / ".gitignore").write_text(
        ".venv/\n.env\n__pycache__/\n*.pyc\n.DS_Store\n"
        "node_modules/\ndist/\nbuild/\n*.egg-info/\n.aria/\n"
    )
    (workspace / ".env.example").write_text("# Environment variables\n")
    (workspace / "README.md").write_text(
        f"# {name}\n\n{description}\n\n## Stack\n{stack}\n\n## Setup\n```bash\n# Instructions\n```\n"
    )

    stack_lower = stack.lower()
    if any(x in stack_lower for x in ["python", "flask", "fastapi", "django"]):
        subprocess.run("python3 -m venv .venv", shell=True, cwd=workspace, capture_output=True)
        (workspace / "requirements.txt").write_text("")

    if any(x in stack_lower for x in ["node", "react", "next", "express", "typescript"]):
        subprocess.run("npm init -y", shell=True, cwd=workspace, capture_output=True)

    meta = {
        "name": name,
        "description": description,
        "stack": stack,
        "path": str(workspace),
        "created_at": datetime.now().isoformat(),
        "status": "in_progress"
    }
    pd = project_dir(name)
    (pd / "meta.json").write_text(json.dumps(meta, indent=2))
    (pd / "progress.md").write_text(f"# {name} — Progress\n\n")
    (pd / "decisions.md").write_text(f"# {name} — Key Decisions\n\n")
    (pd / "memory.json").write_text("{}")

    os.chdir(workspace)
    return f"Project '{name}' created at {workspace}. Git initialized. Workspace set."


def list_projects() -> str:
    proj_root = MEMORY_DIR / "projects"
    if not proj_root.exists():
        return "(no projects)"
    results = []
    for d in proj_root.iterdir():
        meta_f = d / "meta.json"
        if meta_f.exists():
            meta = json.loads(meta_f.read_text())
            results.append(f"[{meta.get('status','?')}] {meta['name']}  —  {meta.get('stack','')}  →  {meta.get('path','')}")
    return "\n".join(results) if results else "(no projects)"


def mark_milestone(project: str, milestone: str, status: str, notes: str = "") -> str:
    from aria.ui.console import console
    pd = project_dir(project)
    prog_file = pd / "progress.md"
    content = prog_file.read_text() if prog_file.exists() else f"# {project} — Progress\n\n"
    icon = {"done": "✅", "in_progress": "🔄", "blocked": "❌"}.get(status, "◉")
    entry = f"\n## {icon} {milestone}\n**Status:** {status}  |  **{datetime.now().strftime('%Y-%m-%d %H:%M')}**\n"
    if notes:
        entry += f"\n{notes}\n"
    prog_file.write_text(content + entry)
    console.print(f"\n  [aria.success]✅[/aria.success] [aria.dim]Milestone:[/aria.dim] {milestone}")
    return f"Milestone saved: {milestone}"
