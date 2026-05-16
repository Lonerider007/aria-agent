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
    "/history":   "Show session timeline with timestamps",
    "/init":      "Initialize ARIA in an existing project",
    "/clear":     "Clear conversation history",
    "/reset":     "Full reset + workspace reload",
    "/model":     "Switch model  (/model name)",
    "/workspace": "Change workspace  (/workspace path)",
    "/apikey":    "Update API key",
    "/projects":  "List all ARIA projects",
    "/memory":    "Show memory  (/memory project-name)",
    "/tools":     "List agent tools",
    "/tokens":    "Show token usage this session",
    "/sandbox":   "Create or switch to sandbox workspace  (/sandbox new <name>)",
    "/undo":      "Undo last file write/edit/delete (/undo list to view recent)",
    "/whatsnew":  "Show what changed in this version of ARIA",
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

    elif cmd == "/sandbox":
        from aria.tools.sandbox import create_sandbox, list_sandboxes, get_sandbox_path
        sub = arg.split() if arg else []
        if sub and sub[0] == "new":
            sname = sub[1] if len(sub) > 1 else "default"
            path = create_sandbox(sname)
            os.chdir(path)
            state["workspace"] = path
            console.print(f"[aria.success]✓[/aria.success] Sandbox '[aria.cyan]{sname}[/aria.cyan]' ready at {path}")
        elif sub and sub[0] == "list":
            console.print(list_sandboxes())
        else:
            path = create_sandbox("default")
            os.chdir(path)
            state["workspace"] = path
            console.print(f"[aria.success]✓[/aria.success] Sandbox ready: [aria.cyan]{path}[/aria.cyan]")

    elif cmd == "/history":
        if not hasattr(agent, '_timeline') or not agent._timeline:
            console.print("[aria.dim]No history yet.[/aria.dim]")
        else:
            console.print()
            for entry in agent._timeline:
                console.print(f"  [aria.dim]{entry['time']}[/aria.dim]  [aria.cyan]{entry['event']}[/aria.cyan]")

    elif cmd == "/tokens":
        usage = agent.token_usage
        t = Table(box=box.SIMPLE, show_header=False)
        t.add_column("", style="aria.dim")
        t.add_column("", style="aria.cyan")
        t.add_row("Context tokens (est.)", f"~{usage['prompt']:,}")
        t.add_row("Messages in context",   str(len(agent.messages)))
        t.add_row("Turns this session",    str(agent.turn))
        console.print(t)

    elif cmd == "/init":
        ws = arg or os.getcwd()
        ws = str(Path(ws).expanduser().resolve())
        if not Path(ws).exists():
            console.print(f"[aria.error]Not found:[/aria.error] {ws}")
        else:
            import subprocess, json
            from aria.memory.store import MEMORY_DIR, project_dir
            name = Path(ws).name
            pd = project_dir(name)
            meta = {"name": name, "path": ws, "status": "in_progress",
                    "stack": "existing", "description": "Initialized by aria init",
                    "created_at": datetime.now().isoformat()}
            (pd / "meta.json").write_text(json.dumps(meta, indent=2))
            (pd / "memory.json").write_text("{}")
            (pd / "progress.md").write_text(f"# {name} — Progress\n\n")
            gitignore = Path(ws) / ".gitignore"
            if gitignore.exists():
                content = gitignore.read_text()
                if ".aria/" not in content:
                    gitignore.write_text(content + "\n.aria/\n")
            os.chdir(ws)
            state["workspace"] = ws
            console.print(f"[aria.success]✓[/aria.success] ARIA initialized in [aria.cyan]{ws}[/aria.cyan]")

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
        if hasattr(agent, "fsm"):        agent.fsm.reset()
        if hasattr(agent, "loop_guard"): agent.loop_guard.reset()
        if hasattr(agent, "validator"):  agent.validator.reset()
        if hasattr(agent, "budget"):     agent.budget._cache.clear()
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

    elif cmd == "/whatsnew":
        from aria.ui.banner import VERSION
        console.print(f"\n  [aria.primary]◉ ARIA v{VERSION} — The Comeback Release[/aria.primary]\n")
        console.print(
            "  [aria.cyan]Verified end-to-end:[/aria.cyan] every task now passes three gates before 'done' —\n"
            "    1. [aria.warning]fetch_api_spec[/aria.warning] — read API docs before integration\n"
            "    2. [aria.warning]verify_goal[/aria.warning]    — evidence (files/commands/output) backs every claim\n"
            "    3. [aria.warning]acceptance_test[/aria.warning] — runnable proof script must pass\n"
        )
        console.print(
            "  [aria.cyan]Architecture:[/aria.cyan]\n"
            "    • Mode router (conversational vs task)\n"
            "    • Plan/Approval FSM (mutating tools blocked until APPROVED)\n"
            "    • Tool guards (no bare pip, no rm -rf /, etc.)\n"
            "    • Delta context + TF-IDF recall + relation graph\n"
            "    • Runtime validator (hallucination, no-go list, stale-belief)\n"
            "    • Time awareness (live wall-clock each turn)\n"
            "    • Identity memory (auto-captures your name/role)\n"
        )
        console.print(
            "  [aria.cyan]New commands:[/aria.cyan] [aria.warning]/undo[/aria.warning], [aria.warning]/whatsnew[/aria.warning]\n"
            "  [aria.cyan]Prompt size:[/aria.cyan] 153 → 77 lines (behaviors moved to code)\n"
        )

    elif cmd == "/undo":
        from aria.tools.undo_log import undo_last, list_entries
        if arg.strip() == "list":
            entries = list_entries(limit=15)
            if not entries:
                console.print("[aria.dim](no undo entries)[/aria.dim]")
            else:
                for e in entries:
                    ts = datetime.fromtimestamp(e.get("ts", 0)).strftime("%H:%M:%S")
                    console.print(f"  [aria.dim]{ts}[/aria.dim]  [aria.warning]{e.get('action','?'):6}[/aria.warning]  {e.get('path','')}")
        else:
            msg = undo_last()
            if msg.startswith(("Restored","Removed","SKIPPED")):
                console.print(f"[aria.success]✓[/aria.success] {msg}")
            else:
                console.print(f"[aria.dim]{msg}[/aria.dim]")

    elif cmd in ("/exit", "/quit"):
        console.print("[aria.dim]Goodbye.[/aria.dim]")
        sys.exit(0)

    else:
        console.print(f"[aria.error]Unknown:[/aria.error] {cmd}  (type [aria.warning]/help[/aria.warning])")

    return True
