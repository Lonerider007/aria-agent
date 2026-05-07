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
from aria.config import get, load_config, save_config
from aria.agent import Agent
from aria.ui.commands import handle

PT_STYLE = PTStyle.from_dict({
    "prompt":      "#7C3AED bold",
    "prompt.arg":  "#6B7280",
})


def onboarding(args) -> tuple:
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

    return api_key, workspace, model


def main():
    parser = argparse.ArgumentParser(description="ARIA — Autonomous Reasoning and Intelligent Agent")
    parser.add_argument("--model",    default=get("default_model", "llama3.3"))
    parser.add_argument("--base-url", default=get("base_url", "http://localhost:11434/v1"))
    parser.add_argument("--api-key",  default=get("api_key", ""))
    args = parser.parse_args()

    api_key, workspace, model = onboarding(args)

    client = OpenAI(base_url=args.base_url, api_key=api_key)
    agent  = Agent(client, model)
    state  = {
        "model":     model,
        "workspace": workspace,
        "api_key":   api_key,
        "base_url":  args.base_url,
    }

    show_banner(model, workspace)

    from aria.ui.livestream import get_toolbar, set_ready, set_done

    session = PromptSession(
        history=InMemoryHistory(),
        bottom_toolbar=get_toolbar,
        refresh_interval=0.5,
    )

    while True:
        try:
            set_ready()
            cwd_short = Path(os.getcwd()).name
            prompt_text = f"\n◉ aria({cwd_short}) › "
            user_input = session.prompt(prompt_text, style=PT_STYLE).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[aria.dim]Session ended.[/aria.dim]")
            break

        if not user_input:
            continue
        if user_input.startswith("/"):
            handle(user_input, agent, state)
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            console.print("[aria.dim]Session ended.[/aria.dim]")
            break

        agent.run(user_input)


if __name__ == "__main__":
    main()
