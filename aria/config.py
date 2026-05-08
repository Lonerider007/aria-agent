import json
import os
from pathlib import Path

CONFIG_FILE = Path.home() / ".aria" / "config.json"

DEFAULTS = {
    "default_model": "llama3.3",
    "base_url":      "http://localhost:11434/v1",
    "api_key":       "",
    "theme":         "purple",
    "stream":        True,
    "max_retries":   3,
    "auto_approve":  False,
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        stored = json.loads(CONFIG_FILE.read_text())
        return {**DEFAULTS, **stored}
    return dict(DEFAULTS)


def save_config(cfg: dict):
    CONFIG_FILE.parent.mkdir(exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def get(key: str, fallback=None):
    cfg = load_config()
    env_map = {
        "base_url":  "ARIA_BASE_URL",
        "api_key":   "ARIA_API_KEY",
        "default_model": "ARIA_MODEL",
    }
    if key in env_map:
        env_val = os.getenv(env_map[key]) or os.getenv("OLLAMA_" + key.upper())
        if env_val:
            return env_val
    return cfg.get(key, fallback)


def is_configured() -> bool:
    """Returns True if user has already agreed to TnC and set workspace."""
    cfg = load_config()
    return cfg.get("tnc_agreed", False) and bool(cfg.get("workspace", ""))


def mark_configured(api_key: str, workspace: str, model: str):
    """Save user's choices permanently."""
    from pathlib import Path
    # Validate workspace — must exist or be creatable
    ws = str(Path(workspace).expanduser().resolve())
    Path(ws).mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    cfg["tnc_agreed"]     = True
    cfg["api_key"]        = api_key
    cfg["workspace"]      = ws   # always save resolved path
    cfg["default_model"]  = model
    save_config(cfg)
