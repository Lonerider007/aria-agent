import json
from pathlib import Path
from datetime import datetime

MEMORY_DIR = Path.home() / ".aria"
MEMORY_DIR.mkdir(exist_ok=True)
(MEMORY_DIR / "projects").mkdir(exist_ok=True)


def project_dir(name: str) -> Path:
    d = MEMORY_DIR / "projects" / name.replace(" ", "_").lower()
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_memory(key: str, value: str, project: str = None) -> str:
    mem_file = (project_dir(project) if project else MEMORY_DIR) / "memory.json"
    try:
        data = json.loads(mem_file.read_text()) if mem_file.exists() else {}
    except (json.JSONDecodeError, OSError):
        data = {}
    data[key] = {"value": value, "updated_at": datetime.now().isoformat()}
    mem_file.write_text(json.dumps(data, indent=2))
    return f"Saved: {key}"


def read_memory(project: str = None) -> str:
    mem_file = (project_dir(project) if project else MEMORY_DIR) / "memory.json"
    if not mem_file.exists():
        return "(no memory)"
    try:
        data = json.loads(mem_file.read_text())
    except (json.JSONDecodeError, OSError):
        return "(memory corrupted — reset with /clear)"
    if not data:
        return "(empty)"
    return "\n".join(f"{k}: {v['value']}" for k, v in data.items())


def get_memory_value(key: str, project: str = None) -> str | None:
    mem_file = (project_dir(project) if project else MEMORY_DIR) / "memory.json"
    if not mem_file.exists():
        return None
    try:
        data = json.loads(mem_file.read_text())
        entry = data.get(key)
        return entry["value"] if isinstance(entry, dict) else None
    except (json.JSONDecodeError, OSError, KeyError):
        return None


def read_user_facts() -> str:
    """Return a compact, prompt-ready summary of stable user-identity facts.

    Pulls keys prefixed with `user_` (e.g., user_name, user_role) from the
    top-level memory.json. Excludes ephemeral keys like `last_session`.
    """
    mem_file = MEMORY_DIR / "memory.json"
    if not mem_file.exists():
        return ""
    try:
        data = json.loads(mem_file.read_text())
    except (json.JSONDecodeError, OSError):
        return ""
    facts = []
    for k, v in data.items():
        if not isinstance(v, dict):
            continue
        val = v.get("value")
        if not val:
            continue
        if k.startswith("user_") or k in {"name", "role", "company"}:
            facts.append(f"{k.replace('user_', '').replace('_', ' ')}: {val}")
    return "; ".join(facts) if facts else ""
