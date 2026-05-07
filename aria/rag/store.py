"""
Knowledge store — loads all knowledge base JSON files.
"""
import json
from pathlib import Path
from typing import List, Dict

KB_DIR = Path(__file__).parent / "knowledge_base"


def load_all() -> List[Dict]:
    docs = []
    for path in KB_DIR.rglob("*.json"):
        try:
            data = json.loads(path.read_text())
            if isinstance(data, list):
                docs.extend(data)
        except Exception:
            pass
    return docs


def save_learned_fix(error: str, fix: str, tags: list = None):
    learned_dir = KB_DIR / "learned"
    learned_dir.mkdir(exist_ok=True)
    learned_file = learned_dir / "fixes.json"

    existing = []
    if learned_file.exists():
        existing = json.loads(learned_file.read_text())

    existing.append({
        "id": f"learned_{len(existing)+1:04d}",
        "tags": tags or [],
        "error": error[:200],
        "solution": fix[:500],
        "source": "aria_learned"
    })
    learned_file.write_text(json.dumps(existing, indent=2))
