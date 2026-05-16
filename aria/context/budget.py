"""Token budget enforcer.

Replaces the old dumb FIFO _trim_context. Strategy in order:
  1. Dedup (delta.compress) — free wins on duplicate tool outputs.
  2. Recall pruning (Step 3 — placeholder hook here; falls through if not wired).
  3. FIFO trim — drop oldest non-system, non-last-N messages.

Caches estimated tokens by id(msg) so repeated re-estimation is O(new messages).
"""
from typing import List, Dict, Callable, Optional
from aria.context import delta

# Rough chars-per-token estimate (matches existing codebase convention).
CHARS_PER_TOKEN = 4

DEFAULT_LIMIT = 24000   # soft target after enforce()
HARD_LIMIT    = 32000   # never let messages exceed this
KEEP_LAST_N   = 6       # never drop the most recent N messages
MAX_SINGLE_MSG_TOKENS = 6000  # any single message larger than this gets truncated


def _truncate_message(msg: Dict, max_chars: int) -> Dict:
    """Hard-truncate a single message's content. Mutating-safe (returns copy)."""
    new = dict(msg)
    c = str(msg.get("content", ""))
    if len(c) > max_chars:
        omitted = len(c) - max_chars
        new["content"] = (
            c[:max_chars]
            + f"\n\n[TRUNCATED: {omitted:,} chars omitted — message too large for context budget]"
        )
    return new


class TokenBudget:
    def __init__(self):
        self._cache: dict[int, int] = {}  # id(msg) → token estimate

    def _msg_tokens(self, msg: Dict) -> int:
        key = id(msg)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        chars = len(str(msg.get("content", "")))
        # Account for tool_calls JSON if present
        if "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                args = tc.get("function", {}).get("arguments", "")
                chars += len(str(args))
        est = max(1, chars // CHARS_PER_TOKEN)
        self._cache[key] = est
        return est

    def estimate(self, messages: List[Dict]) -> int:
        return sum(self._msg_tokens(m) for m in messages)

    def fits(self, messages: List[Dict], limit: int = DEFAULT_LIMIT) -> bool:
        return self.estimate(messages) <= limit

    def enforce(
        self,
        messages: List[Dict],
        limit: int = DEFAULT_LIMIT,
        hard: int = HARD_LIMIT,
        recall_fn: Optional[Callable[[List[Dict]], List[Dict]]] = None,
        recall_query: Optional[str] = None,
    ) -> tuple[List[Dict], Dict]:
        """Return (trimmed_messages, stats).

        recall_fn (optional): callable that takes messages and returns a pruned list
        based on semantic relevance. Used after dedup, before FIFO. Step 3 wires this in.
        """
        stats = {"start_tokens": self.estimate(messages), "dedup": None, "recalled": False, "recall_dropped": 0, "fifo_dropped": 0, "truncated": 0}

        # 0. Truncate any single oversized message (catches one huge tool output)
        max_chars = MAX_SINGLE_MSG_TOKENS * CHARS_PER_TOKEN
        truncated_msgs = []
        for m in messages:
            if self._msg_tokens(m) > MAX_SINGLE_MSG_TOKENS:
                truncated_msgs.append(_truncate_message(m, max_chars))
                stats["truncated"] += 1
            else:
                truncated_msgs.append(m)
        if stats["truncated"]:
            self._cache.clear()
        messages = truncated_msgs

        # 1. Dedup
        new_msgs, dedup_stats = delta.compress(messages)
        if dedup_stats["dedup_count"]:
            # Reset cache for changed messages
            self._cache.clear()
        stats["dedup"] = dedup_stats
        messages = new_msgs

        # 2. Recall pruning — TF-IDF relevance to current query.
        if recall_query and self.estimate(messages) > limit:
            from aria.context.recall import prune_by_relevance
            pruned = prune_by_relevance(
                messages,
                query=recall_query,
                target_tokens=limit,
                estimate_fn=self.estimate,
            )
            if pruned is not None and len(pruned) < len(messages):
                stats["recall_dropped"] = len(messages) - len(pruned)
                messages = pruned
                stats["recalled"] = True
                self._cache.clear()

        # 3. FIFO trim — drop oldest non-system, never touch last N
        while self.estimate(messages) > limit and len(messages) > KEEP_LAST_N + 1:
            # index 0 is system; drop from index 1, but never within last KEEP_LAST_N
            drop_idx = 1
            if drop_idx >= len(messages) - KEEP_LAST_N:
                break
            # If dropping an assistant message with tool_calls, also drop matching tool replies
            dropped = messages.pop(drop_idx)
            stats["fifo_dropped"] += 1
            if "tool_calls" in dropped:
                tc_ids = {tc.get("id") for tc in dropped["tool_calls"]}
                # Remove subsequent tool messages that reference these ids
                i = drop_idx
                while i < len(messages) - KEEP_LAST_N:
                    if messages[i].get("role") == "tool" and messages[i].get("tool_call_id") in tc_ids:
                        messages.pop(i)
                        stats["fifo_dropped"] += 1
                    else:
                        break
            self._cache.clear()

        stats["end_tokens"] = self.estimate(messages)
        stats["over_hard_limit"] = stats["end_tokens"] > hard
        return messages, stats
