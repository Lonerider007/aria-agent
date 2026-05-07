import json
from aria.memory.store import project_dir


def load_project_context(project: str) -> str:
    pd = project_dir(project)
    parts = []

    meta_f = pd / "meta.json"
    if meta_f.exists():
        meta = json.loads(meta_f.read_text())
        parts.append(
            f"Project: {meta.get('name')}  |  Stack: {meta.get('stack')}  "
            f"|  Status: {meta.get('status')}  |  Path: {meta.get('path')}"
        )

    mem_f = pd / "memory.json"
    if mem_f.exists():
        data = json.loads(mem_f.read_text())
        if data:
            parts.append("Memory:\n" + "\n".join(f"  {k}: {v['value']}" for k, v in data.items()))

    prog_f = pd / "progress.md"
    if prog_f.exists():
        content = prog_f.read_text().strip()
        if content:
            parts.append("Progress (recent):\n" + content[-600:])

    return "\n\n".join(parts) if parts else "(no project context found)"
