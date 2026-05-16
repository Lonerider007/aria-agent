"""fetch_api_spec tool — Pillar D of v1.6: read docs before integrating.

When ARIA is about to write HTTP integration code (requests/httpx/aiohttp),
the tool_guard requires that fetch_api_spec was called for the target domain
in this task. Otherwise: BLOCKED.

The tool fetches the page (OpenAPI/Swagger/HTML docs) and caches it. Returns
a digest the LLM can use to write spec-correct code.
"""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

CACHE_DIR = Path.home() / ".aria" / "spec_cache"
MAX_RETURN_CHARS = 12000


def _cache_path(url: str) -> Path:
    h = hashlib.sha1(url.encode()).hexdigest()[:16]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{h}.json"


def _extract_text(html_or_json: str) -> str:
    s = html_or_json.strip()
    # JSON / OpenAPI? Pretty-print key fields
    if s.startswith("{") or s.startswith("["):
        try:
            data = json.loads(s)
            if isinstance(data, dict) and "paths" in data:
                # OpenAPI — return endpoint summary
                lines = []
                info = data.get("info", {})
                lines.append(f"API: {info.get('title','?')} v{info.get('version','?')}")
                for path, methods in (data.get("paths") or {}).items():
                    for method, op in (methods or {}).items():
                        if method.upper() in ("GET","POST","PUT","DELETE","PATCH"):
                            summary = (op.get("summary") or op.get("description") or "")[:120] if isinstance(op, dict) else ""
                            params = [p.get("name") for p in (op.get("parameters") or []) if isinstance(p, dict)]
                            lines.append(f"  {method.upper():6} {path}  — {summary}  params={params}")
                return "\n".join(lines)
            return json.dumps(data, indent=2)[:MAX_RETURN_CHARS]
        except Exception:
            pass

    # HTML — strip tags, collapse whitespace
    text = re.sub(r"<script[\s\S]*?</script>", " ", s, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_api_spec(url_or_name: str) -> str:
    """Fetch and digest an API spec. Returns text to anchor the LLM's integration.

    url_or_name: either a full URL (https://api.example.com/openapi.json) or
    a name we'll search the web for ("delta exchange api docs").
    """
    if not url_or_name:
        return "ERROR: provide a URL or API name."

    target = url_or_name.strip()

    # If it's not a URL, do a web search for the docs
    if not target.startswith(("http://", "https://")):
        from aria.tools.web import search_web
        results = search_web(f"{target} API documentation OpenAPI spec", max_results=3)
        return (
            f"API_SPEC_SEARCH: '{target}'\n"
            "Pick the most authoritative result and call fetch_api_spec again with the URL.\n\n"
            + results[:MAX_RETURN_CHARS]
        )

    # Check cache
    cp = _cache_path(target)
    if cp.exists():
        try:
            cached = json.loads(cp.read_text())
            domain = urlparse(target).netloc
            return (
                f"API_SPEC: cached for domain '{domain}' (url={target})\n"
                f"Fetched at: {cached.get('fetched_at','?')}\n"
                "---\n"
                + cached.get("digest", "")[:MAX_RETURN_CHARS]
            )
        except Exception:
            pass

    # Fetch
    try:
        import urllib.request
        from datetime import datetime
        req = urllib.request.Request(target, headers={"User-Agent": "ARIA/1.6 (spec-fetch)"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")[:200_000]
    except Exception as e:
        return f"ERROR fetching {target}: {e}"

    digest = _extract_text(raw)[:MAX_RETURN_CHARS]
    domain = urlparse(target).netloc
    try:
        cp.write_text(json.dumps({
            "url": target,
            "domain": domain,
            "fetched_at": __import__("datetime").datetime.now().isoformat(),
            "digest": digest,
        }, indent=2))
    except Exception:
        pass

    return (
        f"API_SPEC: fetched for domain '{domain}'\n"
        f"URL: {target}\n"
        "---\n"
        + digest
    )
