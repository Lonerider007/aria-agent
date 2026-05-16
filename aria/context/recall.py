"""Adaptive recall — semantic relevance scoring for context messages.

Pure-Python TF-IDF (no sklearn dependency). Used by budget.enforce() to decide
which old messages to drop when over budget: irrelevant first, relevant last.

v1: TF-IDF cosine similarity.
v2 (future, behind flag): sentence-transformers embeddings.
"""
import math
import re
from collections import Counter
from typing import List, Dict, Optional

TOKEN_RE = re.compile(r"[A-Za-z_]{2,}")

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "to", "of", "in", "on", "at", "for", "with",
    "by", "from", "as", "this", "that", "it", "you", "your", "i", "we",
    "they", "he", "she", "him", "her", "his", "hers", "its", "our",
    "their", "if", "then", "else", "so", "do", "does", "did", "done",
    "have", "has", "had", "will", "would", "could", "should", "may",
    "might", "can", "not", "no", "yes", "all", "any", "some", "what",
    "which", "who", "whom", "when", "where", "why", "how", "than",
}


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "") if t.lower() not in STOPWORDS]


def _msg_text(msg: Dict) -> str:
    """Extract searchable text from a message (content + tool args)."""
    parts = [str(msg.get("content", ""))]
    for tc in msg.get("tool_calls", []) or []:
        fn = tc.get("function", {})
        parts.append(fn.get("name", ""))
        parts.append(str(fn.get("arguments", "")))
    return " ".join(parts)


class TfIdfRecall:
    """Score message relevance to a query via TF-IDF cosine similarity."""

    def __init__(self, messages: List[Dict]):
        self.docs = [_tokenize(_msg_text(m)) for m in messages]
        self.n = len(self.docs)
        # Document frequency
        df: Counter = Counter()
        for doc in self.docs:
            for tok in set(doc):
                df[tok] += 1
        # IDF
        self.idf = {tok: math.log((self.n + 1) / (cnt + 1)) + 1 for tok, cnt in df.items()}
        # Pre-compute TF-IDF vectors (sparse: dict per doc)
        self.vecs = []
        for doc in self.docs:
            tf = Counter(doc)
            length = len(doc) or 1
            v = {tok: (cnt / length) * self.idf.get(tok, 0) for tok, cnt in tf.items()}
            self.vecs.append(v)

    def score(self, query: str, use_relations: bool = True) -> List[float]:
        """Return per-message similarity score (0..1ish) to the query.

        When use_relations=True, also boost messages that mention any entity related
        to query terms in the relation graph (Step 9 hook).
        """
        q_tokens = _tokenize(query)
        if not q_tokens:
            return [0.0] * self.n
        q_tf = Counter(q_tokens)
        q_len = len(q_tokens)
        q_vec = {tok: (cnt / q_len) * self.idf.get(tok, 0) for tok, cnt in q_tf.items()}
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

        # Relation-graph boost set: entities related to any query token
        related: set[str] = set()
        if use_relations:
            try:
                from aria.context import relation as _rel
                for tok in q_tokens[:5]:  # cap lookups
                    for n in _rel.neighbors(tok, depth=1, limit=10):
                        related.update(_tokenize(n))
            except Exception:
                pass

        scores = []
        for v in self.vecs:
            if not v:
                scores.append(0.0)
                continue
            dot = sum(q_vec.get(t, 0) * v.get(t, 0) for t in q_vec)
            d_norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
            base = dot / (q_norm * d_norm)
            # Add small boost for related entities present in the doc
            if related:
                overlap = sum(1 for t in related if t in v)
                base += 0.05 * min(overlap, 4)  # cap boost
            scores.append(base)
        return scores


def prune_by_relevance(
    messages: List[Dict],
    query: str,
    target_tokens: int,
    estimate_fn,
    keep_last_n: int = 6,
    min_keep_score: float = 0.02,
) -> Optional[List[Dict]]:
    """Drop lowest-scoring messages until under target_tokens.

    Never drops:
      - system message (index 0)
      - last `keep_last_n` messages
      - tool messages whose paired assistant tool_call is being kept

    Returns new message list, or None if no pruning needed / possible.
    """
    if estimate_fn(messages) <= target_tokens:
        return None
    if len(messages) <= keep_last_n + 2:
        return None

    recall = TfIdfRecall(messages)
    scores = recall.score(query)

    # Protected indices
    protected = {0}  # system
    for i in range(max(1, len(messages) - keep_last_n), len(messages)):
        protected.add(i)

    # Score message indices, lowest first (most droppable)
    candidates = sorted(
        [(i, scores[i]) for i in range(len(messages)) if i not in protected],
        key=lambda x: x[1],
    )

    drop_idx = set()
    current_tokens = estimate_fn(messages)
    for i, sc in candidates:
        if current_tokens <= target_tokens:
            break
        if sc > min_keep_score and current_tokens - estimate_fn([messages[i]]) > target_tokens * 0.7:
            # message is relevant; only drop if dropping it is clearly needed
            continue
        drop_idx.add(i)
        # also drop matching tool messages if dropping an assistant w/ tool_calls
        msg = messages[i]
        if "tool_calls" in msg:
            tc_ids = {tc.get("id") for tc in msg["tool_calls"]}
            for j in range(i + 1, len(messages)):
                if j in protected:
                    continue
                if messages[j].get("role") == "tool" and messages[j].get("tool_call_id") in tc_ids:
                    drop_idx.add(j)
        current_tokens -= estimate_fn([msg])

    if not drop_idx:
        return None

    return [m for i, m in enumerate(messages) if i not in drop_idx]
