# Copyright © 2026 Sumit (Lonerider007). All rights reserved.
# ARIA — Autonomous Reasoning and Intelligent Agent
# License: ARIA Source License v1.0 — see LICENSE file
import os
import json
from datetime import datetime

from openai import OpenAI
from aria.ui.console import console
from aria.ui.streaming import stream_response, print_response
from aria.memory.store import read_memory
from aria.prompts import SYSTEM_PROMPT
from pathlib import Path
from aria.ast_validator import ASTValidator
from aria.rag import RAGRetriever
from aria.ui import livestream
from aria.ui.livestream import update_tokens
from aria.ui.tool_phrases import get_phrase

_ast_validator = ASTValidator()
_rag = RAGRetriever()

from aria.tools.web import search_web
from aria.tools.files import (
    read_file, write_file, edit_file,
    delete_file, list_files, search_in_files
)
from aria.tools.shell import run_command, run_tests
from aria.tools.git import git_status, git_diff, git_commit, git_create_branch, git_log
from aria.tools.project import new_project, list_projects, mark_milestone
from aria.tools.interaction import (
    create_plan, ask_clarification,
    request_approval, notify_user
)
from aria.memory.store import save_memory, read_memory
from aria.memory.context import load_project_context

TOOL_MAP = {
    "search_web":          search_web,
    "read_file":           read_file,
    "write_file":          write_file,
    "edit_file":           edit_file,
    "delete_file":         delete_file,
    "list_files":          list_files,
    "search_in_files":     search_in_files,
    "run_command":         run_command,
    "run_tests":           run_tests,
    "git_status":          git_status,
    "git_diff":            git_diff,
    "git_commit":          git_commit,
    "git_create_branch":   git_create_branch,
    "git_log":             git_log,
    "new_project":         new_project,
    "list_projects":       list_projects,
    "mark_milestone":      mark_milestone,
    "create_plan":         create_plan,
    "ask_clarification":   ask_clarification,
    "request_approval":    request_approval,
    "notify_user":         notify_user,
    "save_memory":         save_memory,
    "read_memory":         read_memory,
    "load_project_context": load_project_context,
}

TOOLS = [
    {"type":"function","function":{"name":"search_web","description":"Search the internet for any information not available internally. Use when user asks about current events, latest versions, documentation, or any external knowledge.","parameters":{"type":"object","properties":{"query":{"type":"string","description":"Search query"},"max_results":{"type":"integer","default":5}},"required":["query"]}}},
    {"type":"function","function":{"name":"read_file","description":"Read file contents","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"write_file","description":"Create or overwrite a file","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"edit_file","description":"Replace exact string in a file. Shows diff.","parameters":{"type":"object","properties":{"path":{"type":"string"},"old_str":{"type":"string"},"new_str":{"type":"string"}},"required":["path","old_str","new_str"]}}},
    {"type":"function","function":{"name":"delete_file","description":"Delete a file","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"list_files","description":"List files in directory","parameters":{"type":"object","properties":{"path":{"type":"string"},"recursive":{"type":"boolean"}},"required":[]}}},
    {"type":"function","function":{"name":"search_in_files","description":"Search pattern in files (grep)","parameters":{"type":"object","properties":{"pattern":{"type":"string"},"path":{"type":"string"},"file_pattern":{"type":"string"}},"required":["pattern"]}}},
    {"type":"function","function":{"name":"run_command","description":"Run a shell command","parameters":{"type":"object","properties":{"command":{"type":"string"},"cwd":{"type":"string"}},"required":["command"]}}},
    {"type":"function","function":{"name":"run_tests","description":"Run test suite","parameters":{"type":"object","properties":{"command":{"type":"string"},"cwd":{"type":"string"}},"required":[]}}},
    {"type":"function","function":{"name":"git_status","description":"Git working tree status","parameters":{"type":"object","properties":{"cwd":{"type":"string"},"path":{"type":"string"}},"required":[]}}},
    {"type":"function","function":{"name":"git_diff","description":"Show git diff","parameters":{"type":"object","properties":{"cwd":{"type":"string"},"path":{"type":"string"}},"required":[]}}},
    {"type":"function","function":{"name":"git_commit","description":"Stage all and commit","parameters":{"type":"object","properties":{"message":{"type":"string"},"cwd":{"type":"string"},"path":{"type":"string"}},"required":["message"]}}},
    {"type":"function","function":{"name":"git_create_branch","description":"Create and checkout a new branch","parameters":{"type":"object","properties":{"name":{"type":"string"},"cwd":{"type":"string"},"path":{"type":"string"}},"required":["name"]}}},
    {"type":"function","function":{"name":"git_log","description":"Show recent git commits","parameters":{"type":"object","properties":{"n":{"type":"integer"},"cwd":{"type":"string"},"path":{"type":"string"}},"required":[]}}},
    {"type":"function","function":{"name":"new_project","description":"Scaffold new project: folder, git, venv, .env, README. ALWAYS use for new projects.","parameters":{"type":"object","properties":{"name":{"type":"string"},"description":{"type":"string"},"stack":{"type":"string"},"path":{"type":"string"}},"required":["name","description","stack"]}}},
    {"type":"function","function":{"name":"list_projects","description":"List all known ARIA projects","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"mark_milestone","description":"Record project milestone with status","parameters":{"type":"object","properties":{"project":{"type":"string"},"milestone":{"type":"string"},"status":{"type":"string","enum":["done","in_progress","blocked"]},"notes":{"type":"string"}},"required":["project","milestone","status"]}}},
    {"type":"function","function":{"name":"create_plan","description":"REQUIRED: Show plan to user and get approval before executing anything.","parameters":{"type":"object","properties":{"goal":{"type":"string"},"steps":{"type":"array","items":{"type":"string"}}},"required":["goal","steps"]}}},
    {"type":"function","function":{"name":"ask_clarification","description":"Ask user a clarifying question when task is ambiguous.","parameters":{"type":"object","properties":{"question":{"type":"string"}},"required":["question"]}}},
    {"type":"function","function":{"name":"request_approval","description":"Ask user approval before dangerous operations (delete, rm -rf, force push, etc).","parameters":{"type":"object","properties":{"action":{"type":"string"}},"required":["action"]}}},
    {"type":"function","function":{"name":"notify_user","description":"Send status update to user during long tasks.","parameters":{"type":"object","properties":{"message":{"type":"string"},"level":{"type":"string","enum":["info","success","warning","error"]}},"required":["message"]}}},
    {"type":"function","function":{"name":"save_memory","description":"Persist a key fact or decision for future sessions.","parameters":{"type":"object","properties":{"key":{"type":"string"},"value":{"type":"string"},"project":{"type":"string"}},"required":["key","value"]}}},
    {"type":"function","function":{"name":"read_memory","description":"Load persisted memory from previous sessions.","parameters":{"type":"object","properties":{"project":{"type":"string"}},"required":[]}}},
    {"type":"function","function":{"name":"load_project_context","description":"Load full project memory, history, and context. Call at start of any project task.","parameters":{"type":"object","properties":{"project":{"type":"string"}},"required":["project"]}}},
]

SILENT_TOOLS = {
    "create_plan", "ask_clarification", "request_approval",
    "notify_user", "mark_milestone"
}


class Agent:
    def __init__(self, client: OpenAI, model: str, quiet: bool = False, emit_cb=None):
        self.client    = client
        self.model     = model
        self.turn      = 0
        self.quiet     = quiet
        self.emit_cb   = emit_cb
        self._timeline = []
        self.reset_messages()

    def _emit(self, event: dict):
        if self.emit_cb:
            try:
                self.emit_cb(event)
            except Exception:
                pass

    def _log(self, event: str):
        self._timeline.append({
            "time":  datetime.now().strftime("%H:%M:%S"),
            "event": event
        })

    @property
    def token_usage(self) -> dict:
        prompt_tokens = sum(len(str(m.get("content", ""))) // 4 for m in self.messages)
        return {"prompt": prompt_tokens, "total": prompt_tokens}

    def reset_messages(self):
        user_mem = read_memory()
        self.messages = [{
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                cwd=os.getcwd(),
                home=str(Path.home()),
                time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                user_memory=user_mem
            )
        }]

    def _trim_context(self, max_tokens: int = 28000):
        """Remove oldest non-system messages if context is too large."""
        estimated = sum(len(str(m.get("content", ""))) // 4 for m in self.messages)
        while estimated > max_tokens and len(self.messages) > 3:
            # Remove oldest non-system message pair
            if self.messages[1]["role"] in ("user", "assistant"):
                self.messages.pop(1)
                if len(self.messages) > 1 and self.messages[1]["role"] in ("assistant", "tool"):
                    self.messages.pop(1)
            estimated = sum(len(str(m.get("content", ""))) // 4 for m in self.messages)

    def run(self, user_input: str):
        self.turn += 1
        self._log(f"Task: {user_input[:60]}")
        self._trim_context()
        self.messages.append({"role": "user", "content": user_input})
        step_num = 0
        recent_errors = []
        MAX_STEPS = 150
        self._pivot_count = 0  # reset per task
        _desc_retries = 0

        # Warn if context still large after trim
        ctx_est = sum(len(str(m.get("content","")))//4 for m in self.messages)
        if ctx_est > 20000:
            console.print(f"  [aria.warning]⚠[/aria.warning] [aria.dim]Context large (~{ctx_est:,} tokens). Use /clear to reset.[/aria.dim]")

        invalid_tool_retries = 0

        while step_num < MAX_STEPS:
            livestream.set_thinking()
            self._emit({"type": "thinking"})
            _on_token = (lambda t: self._emit({"type": "token", "text": t})) if self.emit_cb else None
            try:
                msg_dict, tool_calls, text = stream_response(
                    self.client, self.model, self.messages, TOOLS, on_token=_on_token
                )
                invalid_tool_retries = 0  # reset on success
            except RuntimeError as e:
                if "SERVER_ERROR" in str(e):
                    console.print(
                        "\n  [aria.warning]⚠[/aria.warning] [aria.dim]Ollama server error (500). Retrying...[/aria.dim]"
                    )
                    import time; time.sleep(3)
                    continue
                if "RATE_LIMIT" in str(e):
                    console.print(
                        "\n  [aria.error]◉[/aria.error] [aria.warning]Ollama usage limit reached.[/aria.warning]\n"
                        "  [aria.dim]Options:[/aria.dim]\n"
                        "  [aria.dim]  • Wait for weekly reset[/aria.dim]\n"
                        "  [aria.dim]  • Use a different model: aria --model llama3.3[/aria.dim]\n"
                        "  [aria.dim]  • Upgrade at ollama.com/upgrade[/aria.dim]"
                    )
                    break
                if "API_TIMEOUT" in str(e):
                    console.print(
                        "\n  [aria.error]◉[/aria.error] [aria.warning]API timed out (no response in 3 min).[/aria.warning]\n"
                        "  [aria.dim]Check:[/aria.dim]\n"
                        "  [aria.dim]  • Ollama running? → ollama serve[/aria.dim]\n"
                        "  [aria.dim]  • API key valid? → aria --config[/aria.dim]\n"
                        "  [aria.dim]  • Model available? → ollama list[/aria.dim]"
                    )
                    break
                if "CONTEXT_TOO_LONG" in str(e):
                    console.print("\n  [aria.warning]⚠[/aria.warning] [aria.dim]Context too long. Use /clear to reset.[/aria.dim]")
                    break
                if "INVALID_TOOL_ARGS" in str(e):
                    invalid_tool_retries += 1
                    if invalid_tool_retries >= 3:
                        console.print("\n  [aria.warning]⚠[/aria.warning] [aria.dim]Cannot complete bulk operation automatically. Use run_command with rm -rf for bulk deletion.[/aria.dim]")
                        break
                    self.messages.append({"role": "user", "content": "Use run_command with a single shell command instead of multiple delete_file calls. For example: rm -rf dir1 dir2 dir3"})
                    continue
                raise
            self.messages.append(msg_dict)

            if not tool_calls:
                # Description-mode guard: ARIA returned text with passive/waiting phrases
                # instead of calling create_plan or a tool. Re-prompt once to force action.
                _PASSIVE_SIGNALS = (
                    "please let me know", "let me know", "if you'd like",
                    "if you want", "what specific", "what would you like",
                    "happy to help", "feel free", "i can help",
                    "you can ask", "tell me what",
                )
                text_lower = (text or "").lower()
                is_passive = (
                    _desc_retries < 1
                    and len(text or "") > 80
                    and any(sig in text_lower for sig in _PASSIVE_SIGNALS)
                )
                if is_passive:
                    _desc_retries += 1
                    console.print(
                        "  [aria.warning]⚠[/aria.warning] [aria.dim]Passive response detected — forcing task mode.[/aria.dim]"
                    )
                    self.messages.append({
                        "role": "user",
                        "content": (
                            "You responded with text instead of acting. This is wrong. "
                            "You are an autonomous agent — you must ACT, not describe. "
                            "Call create_plan NOW with the concrete steps to complete this task. "
                            "Do NOT ask what I want — you already have the task. Just plan it."
                        )
                    })
                    continue
                print_response(text)
                self._log("Task complete")
                livestream.set_done("Task complete")
                tok = sum(len(str(m.get("content",""))) // 4 for m in self.messages)
                update_tokens(tok, self.turn)
                break

            rejected = False
            for tc in tool_calls:
                name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}

                if name not in SILENT_TOOLS:
                    step_num += 1
                    phrase = get_phrase(name, args)
                    livestream.update(name, args, step=step_num)
                    if not self.quiet:
                        console.print(
                            f"  [aria.cyan]◉[/aria.cyan] [aria.dim]{phrase}[/aria.dim]",
                            end="\n"
                        )
                    self._emit({"type": "tool", "name": name, "phrase": phrase, "step": step_num})

                fn = TOOL_MAP.get(name)
                try:
                    result = fn(**args) if fn else f"ERROR: unknown tool '{name}'"
                except TypeError as e:
                    result = f"ERROR: wrong arguments for {name} — {e}"

                # AST validation hook — runs after write_file on .py files
                if name == "write_file":
                    path = args.get("path", "")
                    content = args.get("content", "")
                    if path.endswith(".py") and content:
                        ast_result = _ast_validator.validate(content, filepath=path)
                        if not ast_result.valid:
                            ast_report = ast_result.for_llm()
                            console.print(f"     [aria.warning]⚠ AST:[/aria.warning] [aria.dim]{ast_result.for_human()[:200]}[/aria.dim]")
                            result = f"{result}\n{ast_report}"

                if name == "run_command" and result.strip():
                    for line in result.strip().splitlines()[:10]:
                        console.print(f"     [aria.dim]│ {line}[/aria.dim]")
                    self._emit({"type": "tool_output", "text": result.strip()[:500], "step": step_num})

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(result)
                })

                # Hard stop if user rejected the plan
                if str(result).startswith("USER_REJECTED"):
                    console.print("\n  [aria.warning]◉[/aria.warning] [aria.dim]Task cancelled.[/aria.dim]")
                    rejected = True
                    break

                # RAG — inject relevant docs + web search on error
                if name == "run_command" and ("ERROR" in str(result) or "Traceback" in str(result)):
                    cmd_context = args.get("command", "")[:100]
                    rag_context = _rag.format_for_llm(str(result)[:300], context=cmd_context)
                    if rag_context:
                        result = str(result) + "\n\n" + rag_context
                        console.print(f"     [aria.cyan]◉ RAG:[/aria.cyan] [aria.dim]Docs + web search injected[/aria.dim]")

                # Loop detection — same error repeating
                if name == "run_command" and ("ERROR" in str(result) or "Traceback" in str(result)):
                    err_sig = str(result)[:120]
                    recent_errors.append(err_sig)

                    if len(recent_errors) >= 3 and len(set(recent_errors[-3:])) == 1:
                        pivot_count = getattr(self, '_pivot_count', 0)

                        if pivot_count < 2:
                            # Pivot — try a different approach
                            self._pivot_count = pivot_count + 1
                            recent_errors.clear()
                            console.print(
                                f"\n  [aria.warning]◉[/aria.warning] [aria.dim]"
                                f"Same error 3x — pivoting to alternative approach "
                                f"(attempt {self._pivot_count}/2)[/aria.dim]"
                            )
                            self.messages.append({
                                "role": "user",
                                "content": (
                                    "You are stuck in a loop. Your current approach is not working. "
                                    "STOP what you are doing. Analyze the root cause of the repeated error. "
                                    "Try a completely different approach — different library, different implementation, "
                                    "different architecture. Do NOT repeat what you just tried. "
                                    "Think from scratch and proceed."
                                )
                            })
                        else:
                            # All pivots exhausted — stop and report clearly
                            console.print(
                                "\n  [aria.error]◉[/aria.error] [aria.dim]"
                                "Could not resolve after 2 alternative approaches. Reporting to you.[/aria.dim]"
                            )
                            self.messages.append({
                                "role": "user",
                                "content": (
                                    "All approaches failed. Give the user a clear, non-technical explanation of: "
                                    "1) What the blocker is. "
                                    "2) What you tried. "
                                    "3) The simplest possible solution they can do — even if it means using a different tool or approach entirely."
                                )
                            })
                            msg_dict, _, text = stream_response(self.client, self.model, self.messages, TOOLS)
                            print_response(text)
                            rejected = True
                            break

            if rejected:
                break

        else:
            # MAX_STEPS hit
            console.print(
                f"\n  [aria.warning]◉[/aria.warning] [aria.dim]Reached {MAX_STEPS} steps. "
                "Stopping to prevent runaway execution.[/aria.dim]"
            )
