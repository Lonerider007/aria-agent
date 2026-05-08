from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from .console import console

VERSION = "1.4.0"

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
