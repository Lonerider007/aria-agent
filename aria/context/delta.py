"""Delta context store — eliminate duplicate content from message history.

Strategy: tool outputs and large messages frequently repeat (re-reads of the same file,
re-runs of the same command). Instead of resending full bytes every turn, replace later
occurrences with a short human-readable reference like:

    [DEDUP: identical to message #4 — 1432 chars saved]

The LLM understands plain English references, so no special protocol is needed.

Only acts on:
  - role == "tool" messages, AND
  - content length >= MIN_CONTENT_LEN

Keeps the FIRST occurrence intact (so the model still has the actual data).
"""
import hashlib
from typing import List, Dict, Tuple

MIN_CONTENT_LEN = 400  # chars — don't bother dedup'ing small outputs


def _hash(content: str) -> str:
    return hashlib.sha1(content.encode("utf-8", errors="replace")).hexdigest()[:10]


def compress(messages: List[Dict]) -> Tuple[List[Dict], Dict]:
    """Return (new_messages, stats).

    Replaces duplicate tool-message contents (after the first occurrence) with a short
    reference marker. Other messages are passed through unchanged.

    Idempotent: running on already-compressed list is a no-op.
    """
    seen: Dict[str, int] = {}  # hash → index of first occurrence
    new_messages: List[Dict] = []
    dedup_count = 0
    chars_saved = 0

    for idx, msg in enumerate(messages):
        if msg.get("role") != "tool":
            new_messages.append(msg)
            continue

        content = str(msg.get("content", ""))
        if len(content) < MIN_CONTENT_LEN:
            new_messages.append(msg)
            continue

        # Skip if already a dedup marker
        if content.startswith("[DEDUP:"):
            new_messages.append(msg)
            continue

        h = _hash(content)
        if h in seen:
            first_idx = seen[h]
            chars_saved += len(content)
            dedup_count += 1
            new_msg = dict(msg)
            new_msg["content"] = (
                f"[DEDUP: identical to earlier tool result at message #{first_idx} — "
                f"{len(content)} chars omitted]"
            )
            new_messages.append(new_msg)
        else:
            seen[h] = idx
            new_messages.append(msg)

    return new_messages, {
        "dedup_count": dedup_count,
        "chars_saved": chars_saved,
        "unique_chunks": len(seen),
    }
