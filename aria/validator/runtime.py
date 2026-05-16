"""Runtime validator — Pillar F.

Catches LLM mistakes that the FSM and tool_guard miss:

  - Hallucinated file paths (LLM references a file that doesn't exist and
    isn't being created by this same call).
  - Contradictions with per-session no-go list ("don't touch X").
  - "Task complete" claims while last tool results contain ERROR / Traceback.
  - Stale-belief repetition (same factual claim repeated 3+ turns without
    re-verification).
"""
import os
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Files that, if referenced in a tool call, must exist.
PATH_ARG_KEYS = {"path", "filepath", "cwd"}


# Patterns indicating LLM is making a factual claim worth tracking.
CLAIM_PATTERNS = [
    re.compile(r"line\s+(\d+)[^\d]+(syntax error|error|missing|extra)", re.IGNORECASE),
    re.compile(r"(the\s+\w+\s+(?:tool|function|class|method)\s+\w+\s+is\s+(?:broken|incorrect|missing))", re.IGNORECASE),
]

NOGO_PATTERNS = [
    re.compile(r"(?:don[’'`]?t|do\s+not|never|please\s+don[’'`]?t)\s+(?:touch|modify|edit|change|delete)\s+([^\s.,!?]+)", re.IGNORECASE),
    re.compile(r"leave\s+([^\s.,!?]+)\s+alone", re.IGNORECASE),
]


class RuntimeValidator:
    def __init__(self):
        self.nogo: set[str] = set()
        self.claim_history: list[str] = []  # normalized claim signatures per turn

    def reset(self):
        self.nogo.clear()
        self.claim_history.clear()

    # --- User-message scan: harvest no-go list ---
    def scan_user_message(self, text: str):
        if not text:
            return
        for pat in NOGO_PATTERNS:
            for m in pat.finditer(text):
                token = m.group(1).strip().strip("\"'`")
                if token:
                    self.nogo.add(token)

    # --- Pre-tool-call check ---
    def check_tool_call(self, tool_name: str, args: Dict, being_created: bool = False) -> Tuple[bool, str]:
        """Return (allowed, reason). being_created=True for write_file/new_project where the path
        is the target being created."""
        # Contradiction with no-go list
        for k, v in (args or {}).items():
            if k in PATH_ARG_KEYS and v:
                vs = str(v)
                for nogo in self.nogo:
                    if nogo and nogo in vs:
                        return False, (
                            f"BLOCKED: user previously said not to touch '{nogo}', but this tool call "
                            f"targets `{vs}`. Honor the no-go list."
                        )

        # Hallucinated file path — only enforce on read-style tools
        if tool_name in {"read_file", "edit_file", "delete_file"} and not being_created:
            path = args.get("path", "")
            if path and not Path(str(path)).expanduser().exists():
                return False, (
                    f"BLOCKED: file `{path}` does not exist. Do not reference fabricated paths. "
                    "Use list_files or search_in_files to discover real paths first."
                )

        return True, ""

    # --- Post-response check (LLM said "done") ---
    def check_completion_claim(self, response_text: str, recent_tool_results: List[str]) -> Optional[str]:
        """If LLM claims completion but recent tool results show errors, return rejection message."""
        if not response_text:
            return None
        text = response_text.lower()
        completion_signals = ("task complete", "done.", "successfully", "completed.", "ready to run", "all set")
        if not any(s in text for s in completion_signals):
            return None
        # Check last few tool results for errors
        for r in recent_tool_results[-4:]:
            if not r:
                continue
            r_str = str(r)
            if "Traceback" in r_str or "ERROR" in r_str or "BLOCKED:" in r_str or "VERIFY_FAILED" in r_str or "ACCEPTANCE_FAILED" in r_str:
                return (
                    "REJECTED_COMPLETION_CLAIM: you said the task is complete, but one of the recent "
                    "tool results contained ERROR / Traceback / BLOCKED / VERIFY_FAILED / "
                    "ACCEPTANCE_FAILED. Re-examine the evidence — either fix the failure or report it "
                    "honestly. Do NOT claim success while failures are unresolved."
                )
        return None

    # --- Stale-belief detection ---
    def track_claims(self, response_text: str) -> Optional[str]:
        """Detect when the LLM repeats the same factual claim turn after turn without re-verifying."""
        if not response_text:
            return None
        new_claims = []
        for pat in CLAIM_PATTERNS:
            for m in pat.finditer(response_text):
                sig = m.group(0).lower()[:80]
                new_claims.append(sig)
        if not new_claims:
            self.claim_history.append("")  # turn separator
            if len(self.claim_history) > 8:
                self.claim_history.pop(0)
            return None
        # Record this turn's claims joined
        joined = " | ".join(sorted(set(new_claims)))
        self.claim_history.append(joined)
        if len(self.claim_history) > 8:
            self.claim_history.pop(0)
        # Same claim in 3+ recent turns?
        counter = Counter(c for c in self.claim_history if c)
        for claim, count in counter.items():
            if count >= 3 and joined == claim:
                return (
                    "STALE_BELIEF: you have repeated the same claim ('" + claim[:60] + "...') "
                    "across 3+ turns without re-verifying. Either prove it now with a concrete tool call "
                    "(read the file again, run the command) or drop the claim."
                )
        return None
