"""
Human-readable, non-technical issue reporter.
"""
from typing import List


def format_issues(issues: list, filepath: str = "") -> str:
    if not issues:
        return ""

    lines = []
    if filepath:
        lines.append(f"AST Validation — {filepath}")
        lines.append("─" * 40)

    for issue in issues:
        lines.append(f"  Line {issue.line}: {issue.message}")
        lines.append(f"  Fix:  {issue.fix}")
        lines.append("")

    return "\n".join(lines).strip()


def format_for_llm(issues: list, filepath: str = "") -> str:
    """Compact format injected into LLM context."""
    if not issues:
        return ""
    parts = [f"AST_ISSUES in {filepath}:"]
    for issue in issues:
        parts.append(f"  [{issue.code}] Line {issue.line}: {issue.message}. Fix: {issue.fix}")
    return "\n".join(parts)
