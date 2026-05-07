"""
BM25 keyword search — zero ML dependency fallback.
Always works, no model needed.
"""
import math
import json
import re
from pathlib import Path
from typing import List, Dict


class BM25:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1   = k1
        self.b    = b
        self.docs : List[Dict] = []
        self.idf  : Dict[str, float] = {}
        self.avgdl: float = 0.0

    def index(self, documents: List[Dict]):
        self.docs = documents
        corpus = [self._tokenize(self._doc_text(d)) for d in documents]
        self.avgdl = sum(len(c) for c in corpus) / max(len(corpus), 1)

        # IDF
        N = len(corpus)
        df: Dict[str, int] = {}
        for tokens in corpus:
            for t in set(tokens):
                df[t] = df.get(t, 0) + 1
        self.idf = {
            t: math.log((N - freq + 0.5) / (freq + 0.5) + 1)
            for t, freq in df.items()
        }
        self._corpus = corpus

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        q_tokens = self._tokenize(query)
        scores = []

        for i, tokens in enumerate(self._corpus):
            tf_map: Dict[str, int] = {}
            for t in tokens:
                tf_map[t] = tf_map.get(t, 0) + 1

            score = 0.0
            dl = len(tokens)
            for t in q_tokens:
                if t not in self.idf:
                    continue
                tf = tf_map.get(t, 0)
                numerator   = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                score += self.idf[t] * numerator / denominator

            scores.append((score, i))

        scores.sort(reverse=True)
        return [self.docs[i] for score, i in scores[:top_k] if score > 0]

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r'[a-z0-9_]+', text.lower())

    def _doc_text(self, doc: Dict) -> str:
        parts = []
        for key in ("tags", "error", "context", "solution", "content", "title"):
            val = doc.get(key, "")
            if isinstance(val, list):
                parts.append(" ".join(val))
            elif val:
                parts.append(str(val))
        return " ".join(parts)
