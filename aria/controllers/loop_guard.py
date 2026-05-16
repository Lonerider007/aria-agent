"""Loop detection + pivot controller.

Extracted from agent.py inline logic. Tracks error fingerprints across tool
results and triggers pivots when the same error repeats. After exhausting
pivots, asks the LLM to give an honest "I can't" report.
"""
import hashlib
import re
from typing import Optional

# Normalize error text before fingerprinting (strip line numbers, paths, timestamps).
_NORM_LINENO = re.compile(r":\d+:")
_NORM_PATH   = re.compile(r"/[\w./_-]+")
_NORM_HEX    = re.compile(r"0x[0-9a-fA-F]+")
_NORM_TIME   = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\.?\d*")
_NORM_PID    = re.compile(r"\bpid[=: ]?\d+\b", re.IGNORECASE)


def _fingerprint(error: str, max_len: int = 200) -> str:
    norm = _NORM_LINENO.sub(":N:", error)
    norm = _NORM_PATH.sub("/PATH", norm)
    norm = _NORM_HEX.sub("0xHEX", norm)
    norm = _NORM_TIME.sub("TIME", norm)
    norm = _NORM_PID.sub("PID", norm)
    norm = norm[:max_len].strip()
    return hashlib.md5(norm.encode("utf-8", errors="replace")).hexdigest()[:12]


MAX_PIVOTS = 2
WINDOW = 5      # last N errors tracked
TRIGGER = 3     # same fingerprint this many times → pivot


class LoopGuard:
    def __init__(self):
        self.recent: list[str] = []
        self.pivot_count = 0
        self.exhausted = False
        # For Phase C — capture the last error + the next command that resolved it
        self.last_error_text: str = ""
        self.pending_capture: bool = False

    def reset(self):
        self.recent.clear()
        self.pivot_count = 0
        self.exhausted = False
        self.last_error_text = ""
        self.pending_capture = False

    def maybe_capture_fix(self, tool_name: str, args: dict, result: str) -> None:
        """If a previous error was resolved by this successful tool call, persist as a learned fix."""
        if not self.pending_capture or not self.last_error_text:
            return
        if "ERROR" in str(result) or "Traceback" in str(result) or "BLOCKED:" in str(result):
            return  # still failing — don't capture
        try:
            from aria.rag.store import save_learned_fix
            tags = [tool_name]
            cmd = args.get("command") or args.get("path") or ""
            save_learned_fix(
                error=self.last_error_text[:200],
                fix=f"{tool_name}: {str(cmd)[:200]}",
                tags=tags,
            )
        except Exception:
            pass
        finally:
            self.pending_capture = False
            self.last_error_text = ""

    def observe(self, tool_name: str, result: str) -> Optional[str]:
        """Inspect a tool result. If we're stuck in a loop, return a pivot
        instruction (to be appended as a user message). Otherwise None.

        Returns one of:
          - None: keep going
          - 'PIVOT': inject "try different approach" message
          - 'EXHAUSTED': inject "report honestly to user" message
        """
        if "ERROR" not in result and "Traceback" not in result and "BLOCKED:" not in result:
            return None
        # Remember last error for Phase C — if a later call succeeds we'll save it as a learned fix
        self.last_error_text = result
        self.pending_capture = True
        fp = _fingerprint(result)
        self.recent.append(fp)
        if len(self.recent) > WINDOW:
            self.recent.pop(0)

        # Same error 3 times in the last window?
        if self.recent[-TRIGGER:].count(fp) < TRIGGER:
            return None

        # Stuck.
        if self.pivot_count < MAX_PIVOTS:
            self.pivot_count += 1
            self.recent.clear()
            return "PIVOT"

        self.exhausted = True
        return "EXHAUSTED"


PIVOT_MESSAGE = (
    "You are stuck in a loop — the same error has repeated 3 times. "
    "STOP retrying the current approach. Analyze the root cause from the error message. "
    "Try a completely different strategy: different library, different command syntax, "
    "different file structure. Do NOT repeat what you just tried. Think from scratch."
)

EXHAUSTED_MESSAGE = (
    "All approaches have failed after 2 pivots. Give the user an HONEST, plain-English report:\n"
    "  1) What you were trying to do.\n"
    "  2) What approaches you tried (briefly).\n"
    "  3) The exact blocker (specific error or missing resource).\n"
    "  4) The simplest next step they can take — even if it means a different tool entirely.\n"
    "Do NOT claim partial success. Do NOT propose another retry. Just report and stop."
)
