"""
Real-world web search for error fixes.
Searches DuckDuckGo and extracts relevant content.
"""
import re
from typing import Optional, List
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS


SEARCH_SITES = [
    "site:stackoverflow.com",
    "site:github.com",
    "site:docs.python.org",
]


def search_fix(error: str, context: str = "", max_results: int = 3) -> Optional[str]:
    """
    Search web for a fix. Returns formatted context for LLM injection.
    Returns None if search fails or nothing useful found.
    """
    query = _build_query(error, context)
    results = _search(query, max_results)

    if not results:
        return None

    return _format(results, query)


def _build_query(error: str, context: str) -> str:
    # Extract key error phrase
    error_clean = _extract_key_phrase(error)
    base = f"python fix {error_clean}"
    if context:
        base += f" {context[:60]}"
    return base.strip()


def _extract_key_phrase(error: str) -> str:
    # Pull most meaningful line from error/traceback
    lines = [l.strip() for l in error.splitlines() if l.strip()]
    for line in reversed(lines):
        if any(x in line for x in ["Error:", "Exception:", "error:", "Failed"]):
            return line[:120]
    return lines[-1][:120] if lines else error[:120]


def _search(query: str, max_results: int) -> List[dict]:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, timelimit="y"))
        return results
    except Exception:
        # Fallback without site filter
        try:
            with DDGS() as ddgs:
                return list(DDGS().text(query, max_results=max_results))
        except Exception:
            return []


SKIP_DOMAINS = ["youtube.com", "facebook.com", "twitter.com", "instagram.com", "reddit.com/r/memes"]
PREFER_DOMAINS = ["stackoverflow.com", "github.com", "docs.python.org", "pypi.org", "readthedocs.io"]


def _format(results: List[dict], query: str) -> str:
    # Filter irrelevant results
    filtered = []
    for r in results:
        url = r.get("href", "")
        body = r.get("body", "")
        if any(d in url for d in SKIP_DOMAINS):
            continue
        if len(body) < 50:
            continue
        filtered.append(r)

    if not filtered:
        return ""

    # Sort — prefer technical domains
    filtered.sort(key=lambda r: any(d in r.get("href","") for d in PREFER_DOMAINS), reverse=True)

    parts = [f"WEB SEARCH RESULTS for: {query}\n"]
    for r in filtered[:3]:
        title = r.get("title", "")
        body  = r.get("body", "")[:400]
        url   = r.get("href", "")
        parts.append(f"--- {title} ---")
        parts.append(body)
        parts.append(f"Source: {url}\n")
    return "\n".join(parts)
