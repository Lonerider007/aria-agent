import sys
import threading
from rich.prompt import Prompt

_web_ctx = threading.local()  # holds .session when running in web mode

try:
    import tty
    import termios
    _HAS_TERMIOS = True
except ImportError:
    _HAS_TERMIOS = False  # Windows
from rich.rule import Rule
from aria.ui.console import console


def masked_input(prompt: str = "") -> str:
    if not _HAS_TERMIOS:
        # Windows fallback — use getpass
        import getpass
        return getpass.getpass(prompt)

    sys.stdout.write(prompt)
    sys.stdout.flush()
    chars = []
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch in ('\r', '\n'):
                sys.stdout.write('\n')
                sys.stdout.flush()
                break
            elif ch == '\x7f':
                if chars:
                    chars.pop()
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
            elif ch == '\x03':
                sys.stdout.write('\n')
                raise KeyboardInterrupt
            else:
                chars.append(ch)
                sys.stdout.write('*')
                sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ''.join(chars)


def create_plan(steps, goal: str = "") -> str:
    if isinstance(steps, str):
        steps = [s.strip() for s in steps.split("\n") if s.strip()]

    sess = getattr(_web_ctx, 'session', None)
    if sess:
        return sess.ask_plan(steps, goal)

    console.print()
    console.print(Rule("[aria.plan]◉ Plan[/aria.plan]", style="#7C3AED"))
    if goal:
        console.print(f"  [aria.dim]Goal:[/aria.dim] {goal}\n")
    for i, step in enumerate(steps, 1):
        console.print(f"  [aria.step]{i}.[/aria.step] {step}")
    console.print()
    ans = Prompt.ask(
        "[aria.warning]Proceed?[/aria.warning] [aria.dim](yes / no / modify)[/aria.dim]",
        default="yes"
    ).strip().lower()
    if ans in ("no", "n"):
        return "USER_REJECTED: user declined. Stop execution."
    if ans in ("modify", "m"):
        feedback = Prompt.ask("[aria.warning]Your changes[/aria.warning]").strip()
        return f"USER_MODIFIED: revise plan — {feedback}"
    return "APPROVED"


def ask_clarification(question: str) -> str:
    sess = getattr(_web_ctx, 'session', None)
    if sess:
        return sess.ask_question(question)
    console.print(f"\n  [aria.warning]?[/aria.warning] {question}")
    answer = Prompt.ask("  [aria.dim]Answer[/aria.dim]").strip()
    return answer or "(no answer)"


def request_approval(action: str) -> str:
    sess = getattr(_web_ctx, 'session', None)
    if sess:
        return sess.ask_approval(action)
    console.print(f"\n  [aria.warning]⚠[/aria.warning]  About to run:\n  [aria.dim]{action}[/aria.dim]\n")
    ans = Prompt.ask(
        "  [aria.dim][[/aria.dim][aria.success]y[/aria.success][aria.dim]] yes  [[/aria.dim][aria.error]n[/aria.error][aria.dim]] no[/aria.dim]",
        default="y"
    ).strip().lower()
    if ans in ("n", "no"):
        return "DENIED: user cancelled this action."
    return "APPROVED"


def notify_user(message: str, level: str = "info") -> str:
    icons   = {"info": "◉", "success": "✅", "warning": "⚠", "error": "✗"}
    styles  = {"info": "aria.cyan", "success": "aria.success", "warning": "aria.warning", "error": "aria.error"}
    icon    = icons.get(level, "◉")
    style   = styles.get(level, "aria.cyan")
    console.print(f"\n  [{style}]{icon}[/{style}] {message}")
    return "notified"
