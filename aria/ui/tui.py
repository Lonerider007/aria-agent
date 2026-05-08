"""
ARIA TUI — Frozen header using terminal scrolling region.
Header stays fixed at top. Content scrolls below.
No screen clear, no conversation history loss.
"""
import os
import sys
from aria.ui.console import console

_HEADER_ROWS = 6   # lines reserved for header
_initialized  = False


def _wr(s: str):
    sys.stdout.write(s)
    sys.stdout.flush()


def _terminal_size():
    try:
        sz = os.get_terminal_size()
        return sz.lines, sz.columns
    except Exception:
        return 40, 120


def init_frozen_header(model: str, workspace: str, version: str, mem_status: str = ""):
    """
    Draw header at startup. No scroll region — content flows naturally.
    Terminal scrollback (Shift+PageUp) works for history.
    """
    global _initialized, _HEADER_ROWS
    rows, cols = _terminal_size()

    mem_line = f"\033[90m ◉ Memory: \033[36m{mem_status}\033[0m" if mem_status else ""
    sep      = f"\033[90m{'─' * min(cols, 78)}\033[0m"

    lines = [
        "",
        f"\033[35;1m    ◉  A R I A\033[0m",
        f"\033[90m    Autonomous Reasoning and Intelligent Agent\033[0m",
        "",
        f" \033[35mv{version}\033[0m  \033[90m|\033[0m  Model: \033[36m{model}\033[0m"
        f"  \033[90m|\033[0m  Workspace: \033[36m{workspace}\033[0m",
        mem_line,
        sep,
    ]

    _HEADER_ROWS = len(lines)

    # Clear screen and draw header — NO scroll region set
    _wr("\033[2J\033[H")
    for line in lines:
        _wr(line + "\n")

    _initialized = True


def update_header_model(model: str, workspace: str, version: str):
    """Refresh info line in header without disturbing scroll region."""
    rows, cols = _terminal_size()
    info = (f" \033[35mv{version}\033[0m  \033[90m|\033[0m  Model: \033[36m{model}\033[0m"
            f"  \033[90m|\033[0m  Workspace: \033[36m{workspace}\033[0m")
    # Save cursor, jump to header line 5, write, restore
    _wr(f"\033[s\033[5;1H\033[2K{info}\033[u")


def restore_terminal():
    """Reset scroll region to full screen on exit."""
    _wr("\033[r")      # reset scroll region
    _wr("\033[?25h")   # ensure cursor visible
