import os
import sys
from pathlib import Path
from rich.table import Table
from rich.prompt import Prompt
from rich import box

from aria.ui.console import console
from aria.memory.store import read_memory
from aria.tools.project import list_projects
from aria.tools.interaction import masked_input
from aria.agent import TOOLS

COMMANDS = {
    "/help":      "Show all commands",
    "/fix":       "Fix a bug or error  (/fix or /fix <description>)",
    "/test":      "Run tests and fix failures",
    "/explain":   "Explain code or file  (/explain <file or topic>)",
    "/commit":    "Stage and commit current changes with smart message",
    "/review":    "Review current code for issues and improvements",
    "/status":    "Session info",
    "/clear":     "Clear conversation history",
    "/reset":     "Full reset + workspace reload",
    "/model":     "Switch model  (/model name)",
    "/workspace": "Change workspace  (/workspace path)",
    "/apikey":    "Update API key",
    "/projects":  "List all ARIA projects",
    "/memory":    "Show memory  (/memory project-name)",
    "/tools":     "List agent tools",
    "/exit":      "Exit ARIA",
}


def handle(inp: str, agent, state: dict) -> bool:
    from datetime import datetime
    from openai import OpenAI

    parts = inp.strip().split(None, 1)
    cmd   = parts[0].lower()
    arg   = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/fix":
        desc = arg or "Fix any bugs, errors, or issues in the current codebase."
        agent.run(f"/fix command triggered. Task: {desc}. Inspect the codebase, identify issues, fix them, validate the fix works.")

    elif cmd == "/test":
        agent.run("Run the test suite. If tests fail, analyze the failures, fix the code, and run tests again. Report final results.")

    elif cmd == "/explain":
        target = arg or "the current project structure and main files"
        agent.run(f"Explain {target}. Read relevant files and give a clear, concise technical explanation.")

    elif cmd == "/commit":
        agent.run("Check git status and diff. Write a concise, meaningful commit message based on the actual changes. Stage all changes and commit.")

    elif cmd == "/review":
        agent.run("Review the current codebase. Check for: bugs, security issues, bad practices, missing error handling, and improvement opportunities. Be specific and actionable.")

    elif cmd == "/help":
        t = Table(box=box.SIMPLE, show_header=True, header_style="aria.primary")
        t.add_column("Command",     style="aria.warning", no_wrap=True)
        t.add_column("Description", style="white")
        for c, d in COMMANDS.items():
            t.add_row(c, d)
        console.print(t)

    elif cmd == "/status":
        t = Table(box=box.SIMPLE, show_header=False)
        t.add_column("", style="aria.dim")
        t.add_column("", style="aria.cyan")
        t.add_row("Model",    agent.model)
        t.add_row("Workspace", state["workspace"])
        t.add_row("CWD",       os.getcwd())
        t.add_row("Turns",     str(agent.turn))
        t.add_row("Messages",  str(len(agent.messages)))
        t.add_row("Time",      datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        console.print(t)

    elif cmd == "/clear":
        agent.reset_messages()
        agent.turn = 0
        console.print("[aria.success]✓[/aria.success] Cleared.")

    elif cmd == "/reset":
        ws = Prompt.ask("[aria.warning]Workspace[/aria.warning]", default=state["workspace"])
        ws = str(Path(ws).expanduser().resolve())
        if Path(ws).exists():
            os.chdir(ws)
            state["workspace"] = ws
        agent.reset_messages()
        agent.turn = 0
        console.print(f"[aria.success]✓[/aria.success] Reset. Workspace: {state['workspace']}")

    elif cmd == "/model":
        if arg:
            agent.model = arg
            state["model"] = arg
            console.print(f"[aria.success]✓[/aria.success] Model: [aria.cyan]{arg}[/aria.cyan]")
        else:
            console.print(f"Current: [aria.cyan]{agent.model}[/aria.cyan]")

    elif cmd == "/workspace":
        if arg:
            ws = str(Path(arg).expanduser().resolve())
            if Path(ws).exists():
                os.chdir(ws)
                state["workspace"] = ws
                console.print(f"[aria.success]✓[/aria.success] Workspace: [aria.cyan]{ws}[/aria.cyan]")
            else:
                console.print(f"[aria.error]Not found:[/aria.error] {ws}")
        else:
            console.print(f"[aria.cyan]{state['workspace']}[/aria.cyan]")

    elif cmd == "/apikey":
        console.print("[aria.dim]New API key:[/aria.dim]")
        new_key = masked_input("Key: ").strip()
        if new_key:
            state["api_key"] = new_key
            agent.client = OpenAI(base_url=state["base_url"], api_key=new_key)
            console.print("[aria.success]✓[/aria.success] Updated.")
        else:
            console.print("[aria.dim]Cancelled.[/aria.dim]")

    elif cmd == "/projects":
        console.print(list_projects())

    elif cmd == "/memory":
        console.print(read_memory(arg or None))

    elif cmd == "/tools":
        t = Table(box=box.SIMPLE, show_header=True, header_style="aria.primary")
        t.add_column("Tool",        style="aria.warning")
        t.add_column("Description", style="white")
        for tool in TOOLS:
            fn = tool["function"]
            t.add_row(fn["name"], fn["description"][:65])
        console.print(t)

    elif cmd in ("/exit", "/quit"):
        console.print("[aria.dim]Goodbye.[/aria.dim]")
        sys.exit(0)

    else:
        console.print(f"[aria.error]Unknown:[/aria.error] {cmd}  (type [aria.warning]/help[/aria.warning])")

    return True
