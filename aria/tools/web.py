"""
General web search tool for ARIA.
Used when internal knowledge is insufficient.
"""
from typing import Optional


def search_web(query: str, max_results: int = 5) -> str:
    """Search the web for any query and return relevant results."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        SKIP = ["youtube.com", "facebook.com", "twitter.com", "instagram.com"]

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results * 2))

        filtered = [r for r in results if not any(s in r.get("href","") for s in SKIP)][:max_results]

        if not filtered:
            return f"No results found for: {query}"

        parts = [f"Web search results for: {query}\n"]
        for r in filtered:
            title = r.get("title", "")
            body  = r.get("body", "")[:400]
            url   = r.get("href", "")
            parts.append(f"--- {title} ---\n{body}\nSource: {url}\n")

        return "\n".join(parts)

    except Exception as e:
        return f"Search failed: {e}"
