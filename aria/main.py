import os
import sys
import argparse
from pathlib import Path

from openai import OpenAI
from rich.panel import Panel
from rich.prompt import Prompt
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style as PTStyle

from aria.ui.console import console
from aria.ui.banner import show_intro, show_tnc, show_banner, VERSION
from aria.tools.interaction import masked_input
from aria.memory.store import read_memory
from aria.config import get, load_config, save_config, is_configured, mark_configured
from aria.agent import Agent
from aria.ui.commands import handle

PT_STYLE = PTStyle.from_dict({
    "prompt":      "#7C3AED bold",
    "prompt.arg":  "#6B7280",
})


def onboarding(args) -> tuple:
    try:
        # Fast path — already configured, skip TnC and prompts
        if is_configured() and not args.api_key:
            api_key  = get("api_key") or "aria"
            workspace = get("workspace") or os.getcwd()
            model    = args.model or get("default_model", "llama3.3")
            workspace = str(Path(workspace).expanduser().resolve())
            if not Path(workspace).exists():
                Path(workspace).mkdir(parents=True, exist_ok=True)
            os.chdir(workspace)
            show_intro()
            console.print(f"[aria.dim]◉ Welcome back — config loaded[/aria.dim]")
            console.print(f"[aria.success]✓[/aria.success] Workspace: [aria.cyan]{workspace}[/aria.cyan]")
            console.print(f"[aria.success]✓[/aria.success] Model:     [aria.cyan]{model}[/aria.cyan]\n")
            return api_key, workspace, model

        # First time — full onboarding
        show_intro()
        console.print()
        show_tnc()
        console.print()

        while True:
            choice = Prompt.ask("[bold]agree / disagree[/bold]").strip().lower()
            if choice == "agree":
                console.print("[aria.success]✓[/aria.success] Accepted.\n")
                break
            elif choice == "disagree":
                console.print("[aria.error]Exiting.[/aria.error]")
                sys.exit(0)
            else:
                console.print("[aria.dim]Type 'agree' or 'disagree'.[/aria.dim]")

        existing = args.api_key or get("api_key") or ""
        hint = " (Enter to skip — not needed for local Ollama)" if not existing else " (Enter to use saved key)"
        console.print(f"[aria.warning]API Key[/aria.warning][aria.dim]{hint}[/aria.dim]")
        api_key = masked_input("Key: ").strip() or existing or "aria"

        ws_input = Prompt.ask("[aria.warning]Workspace[/aria.warning]", default=os.getcwd()).strip()
        workspace = str(Path(ws_input or os.getcwd()).expanduser().resolve())
        if not Path(workspace).exists():
            Path(workspace).mkdir(parents=True, exist_ok=True)
            console.print(f"[aria.dim]Created:[/aria.dim] {workspace}")
        os.chdir(workspace)
        console.print(f"[aria.success]✓[/aria.success] Workspace: [aria.cyan]{workspace}[/aria.cyan]")

        model_input = Prompt.ask("[aria.warning]Model[/aria.warning]", default=args.model).strip()
        model = model_input or args.model
        console.print(f"[aria.success]✓[/aria.success] Model:     [aria.cyan]{model}[/aria.cyan]\n")

        # Save config permanently
        mark_configured(api_key, workspace, model)
        console.print("[aria.dim]◉ Config saved — next run will be instant.[/aria.dim]\n")

        return api_key, workspace, model

    except (KeyboardInterrupt, EOFError):
        console.print("\n[aria.dim]Goodbye.[/aria.dim]")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="ARIA — Autonomous Reasoning and Intelligent Agent")
    parser.add_argument("--model",    default=get("default_model", "llama3.3"))
    parser.add_argument("--base-url", default=get("base_url", "http://localhost:11434/v1"))
    parser.add_argument("--api-key",  default=get("api_key", ""))
    parser.add_argument("--quiet",    action="store_true", help="Hide tool execution details")
    args = parser.parse_args()

    api_key, workspace, model = onboarding(args)

    client = OpenAI(base_url=args.base_url, api_key=api_key)
    agent  = Agent(client, model, quiet=getattr(args, "quiet", False))
    state  = {
        "model":     model,
        "workspace": workspace,
        "api_key":   api_key,
        "base_url":  args.base_url,
    }

    from aria.ui.tui import init_frozen_header, restore_terminal
    import atexit

    from aria.ui.livestream import get_toolbar, set_ready, set_done

    # Load memory BEFORE header so we can show status in header
    user_mem  = read_memory()
    mem_lines = [l for l in user_mem.strip().split("\n") if l.strip()] if user_mem not in ("(no memory)", "(empty)") else []
    mem_status = f"{len(mem_lines)} block(s) loaded" if mem_lines else "empty"

    # Initialize frozen header with memory status
    init_frozen_header(model, workspace, VERSION, mem_status=mem_status)
    atexit.register(restore_terminal)

    session = PromptSession(
        history=InMemoryHistory(),
        bottom_toolbar=get_toolbar,
        refresh_interval=0.5,
    )

    _saved = [False]  # prevent double save

    def _auto_save():
        """Auto-save session timeline on exit — show what was saved."""
        if _saved[0] or not agent._timeline:
            return
        _saved[0] = True
        from aria.memory.store import save_memory, MEMORY_DIR
        timeline_str = " | ".join(f"{e['time']} {e['event']}" for e in agent._timeline[-10:])
        save_memory("last_session", timeline_str)
        mem_path = MEMORY_DIR / "memory.json"
        console.print(
            f"\n[aria.cyan]╔══ Memory Saved ══╗[/aria.cyan]\n"
            f"[aria.dim]  Location : [/aria.dim][aria.cyan]{mem_path}[/aria.cyan]\n"
            f"[aria.dim]  Blocks   : [/aria.dim][aria.cyan]{len(agent._timeline)} events[/aria.cyan]\n"
            f"[aria.dim]  Last     : [/aria.dim][aria.cyan]{agent._timeline[-1]['event'][:50]}[/aria.cyan]\n"
            f"[aria.cyan]╚═══════════════════╝[/aria.cyan]"
        )

    import atexit, signal

    atexit.register(_auto_save)

    def _signal_handler(sig, frame):
        _auto_save()
        console.print("\n[aria.dim]Session saved. Goodbye.[/aria.dim]")
        import sys; sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    while True:
        try:
            set_ready()
            cwd_short = Path(os.getcwd()).name
            prompt_text = f"\n◉ aria({cwd_short}) › "
            user_input = session.prompt(prompt_text, style=PT_STYLE).strip()
        except (KeyboardInterrupt, EOFError):
            _auto_save()
            console.print("\n[aria.dim]Session saved. Goodbye.[/aria.dim]")
            break

        if not user_input:
            continue
        if user_input.startswith("/"):
            handle(user_input, agent, state)
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            _auto_save()
            console.print("[aria.dim]Session saved. Goodbye.[/aria.dim]")
            break

        agent.run(user_input)


if __name__ == "__main__":
    main()
