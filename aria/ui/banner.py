from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from .console import console

VERSION = "1.5.0"

LOGO = """[aria.primary]
    ◉  A R I A[/aria.primary]
[aria.dim]    Autonomous Reasoning and Intelligent Agent[/aria.dim]
"""

TNC = (
    "1. ARIA executes real shell commands and modifies files on your machine.\n"
    "2. You are solely responsible for all actions in your workspace.\n"
    "3. API calls go directly to your configured model provider.\n"
    "4. The author holds no liability for unintended changes or data loss."
)

def show_welcome_context(last_session: str | None) -> None:
    if not last_session:
        return
    entries = [e.strip() for e in last_session.split("|")]
    last_task = next(
        (e for e in reversed(entries) if "Task:" in e and "complete" not in e.lower()),
        None
    )
    if not last_task:
        return
    parts = last_task.split("Task:", 1)
    time_str = parts[0].strip() if len(parts) > 1 else ""
    task_str = parts[1].strip() if len(parts) > 1 else last_task
    if len(task_str) > 64:
        task_str = task_str[:61] + "..."
    time_part = f"  [aria.dim]({time_str})[/aria.dim]" if time_str else ""
    console.print(f"[aria.dim]◉ Last:[/aria.dim] [aria.cyan]{task_str}[/aria.cyan]{time_part}\n")


def show_banner(model: str, workspace: str):
    console.print(LOGO)
    console.print(Panel(
        f"[aria.dim]v{VERSION}[/aria.dim]  |  "
        f"[aria.dim]Model:[/aria.dim] [aria.cyan]{model}[/aria.cyan]  |  "
        f"[aria.dim]Workspace:[/aria.dim] [aria.cyan]{workspace}[/aria.cyan]\n"
        f"[aria.dim]Type [/aria.dim][aria.warning]/help[/aria.warning][aria.dim] for commands[/aria.dim]",
        border_style="#7C3AED",
        expand=False
    ))

def show_intro():
    console.print(Panel(
        "[bold]ARIA[/bold] — Professional AI engineering agent.\n\n"
        "  [aria.cyan]◉[/aria.cyan] Plan → Execute → Validate workflow\n"
        "  [aria.cyan]◉[/aria.cyan] Persistent project memory\n"
        "  [aria.cyan]◉[/aria.cyan] Project isolation: git, venv, .env\n"
        "  [aria.cyan]◉[/aria.cyan] Production-readiness checks\n"
        "  [aria.cyan]◉[/aria.cyan] Approval before dangerous actions\n\n"
        f"[aria.dim]v{VERSION}  |  /help for commands[/aria.dim]",
        title="[aria.primary]What is ARIA?[/aria.primary]",
        border_style="#7C3AED",
        expand=False
    ))

def show_tnc():
    console.print(Panel(
        TNC + "\n\n[aria.dim]Type [bold]agree[/bold] to continue or [bold]disagree[/bold] to exit.[/aria.dim]",
        title="[aria.warning]Terms & Conditions[/aria.warning]",
        border_style="#EAB308",
        expand=False
    ))
