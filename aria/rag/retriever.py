"""
RAG Retriever — main interface.
Searches knowledge base and returns relevant context for LLM injection.
"""
from typing import List, Optional
from .bm25 import BM25
from .store import load_all


class RAGRetriever:
    def __init__(self, web_search: bool = True):
        self._bm25 = BM25()
        self._loaded = False
        self._web_search = web_search

    def _ensure_loaded(self):
        if not self._loaded:
            docs = load_all()
            self._bm25.index(docs)
            self._loaded = True

    def search(self, query: str, top_k: int = 3) -> List[dict]:
        self._ensure_loaded()
        return self._bm25.search(query, top_k=top_k)

    def format_for_llm(self, error: str, context: str = "", top_k: int = 3) -> Optional[str]:
        parts = []

        # 1. Local KB first (fast)
        local = self.search(error + " " + context, top_k=top_k)
        if local:
            kb_parts = ["RELEVANT DOCUMENTATION:"]
            for r in local:
                title    = r.get("title") or r.get("error") or r.get("id", "")
                solution = r.get("solution") or r.get("content", "")
                example  = r.get("example_fix") or r.get("example", "")
                kb_parts.append(f"\n--- {title} ---")
                kb_parts.append(solution)
                if example:
                    kb_parts.append(f"Example:\n{example}")
            parts.append("\n".join(kb_parts))

        # 2. Web search fallback
        if self._web_search:
            try:
                from .web_search import search_fix
                web_result = search_fix(error, context)
                if web_result:
                    parts.append(web_result)
            except Exception:
                pass  # Web search is best-effort

        return "\n\n".join(parts) if parts else None

    def reload(self):
        self._loaded = False
        self._ensure_loaded()
