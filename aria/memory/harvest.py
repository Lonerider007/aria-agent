"""Identity / preference auto-capture from user messages.

Detects common identity statements and persists them via save_memory.
Quiet by design — never interrupts the conversation, just records.

Captures:
  user_name      — "my name is X", "I'm X", "I am X", "call me X", "this is X"
  user_role      — "I'm a Y", "I work as Y", "I am a Y", "as a Y"
  user_company   — "I work at Z", "I'm from Z", "at company Z"
  user_pref      — "remember that ...", "please remember ..."
"""
import re
from typing import List, Tuple

NAME_PATTERNS = [
    re.compile(r"\b(?:my\s+name\s+is|i[''`]?m|i\s+am|call\s+me|this\s+is)\s+([A-Z][a-zA-Z]{1,30})\b", re.IGNORECASE),
]
ROLE_PATTERNS = [
    re.compile(r"\bi[''`]?m\s+a\s+([a-zA-Z][a-zA-Z\s-]{2,40}?)(?:\s+(?:at|from|in|and|but|\.|,|$))", re.IGNORECASE),
    re.compile(r"\bi\s+work\s+as\s+(?:a\s+|an\s+)?([a-zA-Z][a-zA-Z\s-]{2,40}?)(?:\s+(?:at|from|in|and|but|\.|,|$))", re.IGNORECASE),
    re.compile(r"\bas\s+a\s+([a-zA-Z][a-zA-Z\s-]{2,40}?)(?:\s+(?:i|we|at|from|in|and|but|\.|,|$))", re.IGNORECASE),
]
COMPANY_PATTERNS = [
    re.compile(r"\bi\s+work\s+at\s+([A-Z][\w&.-]{1,30})\b"),
    re.compile(r"\bi[''`]?m\s+from\s+([A-Z][\w&.-]{1,30})\b"),
]
REMEMBER_PATTERNS = [
    re.compile(r"\b(?:please\s+)?remember\s+(?:that\s+)?(.{6,120}?)(?:[.!?]|$)", re.IGNORECASE),
]

# Words that should never be captured as a "name"
NAME_BLOCKLIST = {
    "fine", "good", "great", "okay", "ok", "sure", "ready", "back",
    "doing", "going", "here", "there", "happy", "sad", "tired", "busy",
    "the", "an", "a", "your", "my", "his", "her", "their",
}


def harvest(user_message: str) -> List[Tuple[str, str]]:
    """Return list of (key, value) facts to persist. Empty if none found."""
    if not user_message:
        return []
    found: List[Tuple[str, str]] = []
    seen_keys = set()

    for pat in NAME_PATTERNS:
        for m in pat.finditer(user_message):
            name = m.group(1).strip()
            if name.lower() in NAME_BLOCKLIST or len(name) < 2:
                continue
            if "user_name" not in seen_keys:
                found.append(("user_name", name))
                seen_keys.add("user_name")
                break

    for pat in ROLE_PATTERNS:
        for m in pat.finditer(user_message):
            role = m.group(1).strip().rstrip(".,")
            if len(role) < 3 or role.lower() in NAME_BLOCKLIST:
                continue
            if "user_role" not in seen_keys:
                found.append(("user_role", role))
                seen_keys.add("user_role")
                break

    for pat in COMPANY_PATTERNS:
        for m in pat.finditer(user_message):
            company = m.group(1).strip().rstrip(".,")
            if "user_company" not in seen_keys:
                found.append(("user_company", company))
                seen_keys.add("user_company")
                break

    for pat in REMEMBER_PATTERNS:
        for m in pat.finditer(user_message):
            note = m.group(1).strip()
            if len(note) >= 6:
                key = f"user_note_{abs(hash(note)) % 10000:04d}"
                found.append((key, note))
                break

    return found


def apply(user_message: str) -> List[str]:
    """Harvest facts from a user message and persist them via save_memory.
    Returns list of captured keys (for caller to log/notify)."""
    facts = harvest(user_message)
    if not facts:
        return []
    from aria.memory.store import save_memory
    captured = []
    for k, v in facts:
        try:
            save_memory(k, v)
            captured.append(k)
        except Exception:
            pass
    return captured
