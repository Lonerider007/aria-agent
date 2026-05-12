import json
from pathlib import Path
from datetime import datetime

CHECKPOINT_DIR = Path.home() / ".aria" / "checkpoints"


def save_checkpoint(project: str, task: str, completed_steps: list,
                    next_step: str, key_paths: list, summary: str) -> str:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "project": project,
        "task": task,
        "completed_steps": completed_steps,
        "next_step": next_step,
        "key_paths": key_paths,
        "summary": summary,
        "saved_at": datetime.now().isoformat(),
        "plan_shown": False,
    }
    path = CHECKPOINT_DIR / f"{project}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return f"Checkpoint saved → {path}"


def load_checkpoint(project: str) -> str:
    path = CHECKPOINT_DIR / f"{project}.json"
    if not path.exists():
        return "No checkpoint found."
    with open(path, "r") as f:
        data = json.load(f)
    lines = [
        f"CHECKPOINT FOUND — project: {data['project']}",
        f"Task: {data['task']}",
        f"Saved at: {data['saved_at']}",
        f"Completed steps: {', '.join(data['completed_steps']) if data['completed_steps'] else 'none'}",
        f"Next step: {data['next_step']}",
        f"Key paths: {', '.join(data['key_paths']) if data['key_paths'] else 'none'}",
        f"Summary: {data['summary']}",
    ]
    return "\n".join(lines)


def mark_plan_shown(project: str):
    path = CHECKPOINT_DIR / f"{project}.json"
    if path.exists():
        with open(path, "r") as f:
            data = json.load(f)
        data["plan_shown"] = True
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


def clear_checkpoint(project: str) -> str:
    path = CHECKPOINT_DIR / f"{project}.json"
    if path.exists():
        path.unlink()
        return f"Checkpoint cleared for {project}."
    return "No checkpoint to clear."


def get_checkpoint_data(project: str) -> dict | None:
    path = CHECKPOINT_DIR / f"{project}.json"
    if not path.exists():
        return None
    with open(path, "r") as f:
        return json.load(f)
