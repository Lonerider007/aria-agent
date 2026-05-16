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
from aria.controllers.router import classify as classify_mode
from aria.controllers.state_machine import PlanFSM, State
from aria.controllers import tool_guard
from aria.controllers.loop_guard import LoopGuard, PIVOT_MESSAGE, EXHAUSTED_MESSAGE
from aria.context.budget import TokenBudget
from aria.validator.runtime import RuntimeValidator

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
from aria.tools.verify import verify_goal
from aria.tools.spec import fetch_api_spec
from aria.tools.acceptance import acceptance_test
from aria.memory.store import save_memory, read_memory
from aria.memory.context import load_project_context
from aria.memory.checkpoint import save_checkpoint, load_checkpoint, clear_checkpoint, mark_plan_shown, get_checkpoint_data

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
    "save_checkpoint":     save_checkpoint,
    "load_checkpoint":     load_checkpoint,
    "clear_checkpoint":    clear_checkpoint,
    "verify_goal":         verify_goal,
    "fetch_api_spec":      fetch_api_spec,
    "acceptance_test":     acceptance_test,
}

TOOLS = [
    {"type":"function","function":{"name":"search_web","description":"Search the internet for any information not available internally. Use when user asks about current events, latest versions, documentation, or any external knowledge.","parameters":{"type":"object","properties":{"query":{"type":"string","description":"Search query"},"max_results":{"type":"integer","default":5}},"required":["query"]}}},
    {"type":"function","function":{"name":"read_file","description":"Read file contents","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"write_file","description":"Create or overwrite a file","parameters":{"type":"object","properties":{"path":{"type":"string"},"content":{"type":"string"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"edit_file","description":"Replace exact string in a file. Shows diff.","parameters":{"type":"object","properties":{"path":{"type":"string"},"old_str":{"type":"string"},"new_str":{"type":"string"}},"required":["path","old_str","new_str"]}}},
    {"type":"function","function":{"name":"delete_file","description":"Delete a file","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"]}}},
    {"type":"function","function":{"name":"list_files","description":"List files in directory","parameters":{"type":"object","properties":{"path":{"type":"string"},"recursive":{"type":"boolean"}},"required":[]}}},
    {"type":"function","function":{"name":"search_in_files","description":"Search pattern in files (grep)","parameters":{"type":"object","properties":{"pattern":{"type":"string"},"path":{"type":"string"},"file_pattern":{"type":"string"}},"required":["pattern"]}}},
    {"type":"function","function":{"name":"run_command","description":"Run a shell command. For servers/long processes use background=true to avoid timeout.","parameters":{"type":"object","properties":{"command":{"type":"string"},"cwd":{"type":"string"},"background":{"type":"boolean","description":"Run in background, no timeout. Use for servers, uvicorn, flask, etc."}},"required":["command"]}}},
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
    {"type":"function","function":{"name":"save_checkpoint","description":"CPRS: Save current task state before context reset. Call when context is large (>18k tokens) or task will span multiple sessions.","parameters":{"type":"object","properties":{"project":{"type":"string"},"task":{"type":"string"},"completed_steps":{"type":"array","items":{"type":"string"}},"next_step":{"type":"string"},"key_paths":{"type":"array","items":{"type":"string"}},"summary":{"type":"string"}},"required":["project","task","completed_steps","next_step","key_paths","summary"]}}},
    {"type":"function","function":{"name":"load_checkpoint","description":"CPRS: Load saved checkpoint from previous session to resume interrupted work.","parameters":{"type":"object","properties":{"project":{"type":"string"}},"required":["project"]}}},
    {"type":"function","function":{"name":"clear_checkpoint","description":"CPRS: Clear checkpoint after task is fully complete.","parameters":{"type":"object","properties":{"project":{"type":"string"}},"required":["project"]}}},
    {"type":"function","function":{"name":"verify_goal","description":"REQUIRED before marking a task done. Confirm goal was achieved via concrete evidence (files created, commands succeeded, expected output appeared). Returns VERIFIED or VERIFY_FAILED.","parameters":{"type":"object","properties":{"goal":{"type":"string","description":"User-stated goal from the plan."},"evidence":{"type":"object","description":"Structured proof. Keys: files_created (list of paths), commands_run (list of {cmd, exit_code, stdout_excerpt}), expected_output (list of substrings expected in stdout), forbidden_output (list of substrings that must NOT appear), notes (string)."}},"required":["goal","evidence"]}}},
    {"type":"function","function":{"name":"fetch_api_spec","description":"REQUIRED before writing HTTP integration code (requests/httpx/aiohttp). Fetches OpenAPI/Swagger/docs page so integration uses real param types. Provide a URL or an API name (will search).","parameters":{"type":"object","properties":{"url_or_name":{"type":"string"}},"required":["url_or_name"]}}},
    {"type":"function","function":{"name":"acceptance_test","description":"REQUIRED before final task completion (after verify_goal passes). Provide a small runnable Python or shell snippet that proves the goal works end-to-end, plus an expected_outcome substring (or 'exit 0' for any successful run).","parameters":{"type":"object","properties":{"goal":{"type":"string"},"test_code":{"type":"string","description":"Runnable Python (default) or shell (starts with bash). Should produce expected_outcome in stdout."},"expected_outcome":{"type":"string","description":"Substring to look for, or 'exit 0' for any clean exit."}},"required":["goal","test_code","expected_outcome"]}}},
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
        self.fsm        = PlanFSM()
        self.budget     = TokenBudget()
        self.loop_guard = LoopGuard()
        self.validator  = RuntimeValidator()
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
        from aria.memory.store import read_user_facts
        facts = read_user_facts() or "(none yet — user has not shared identity)"
        self.messages = [{
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                cwd=os.getcwd(),
                home=str(Path.home()),
                time=datetime.now().strftime("%Y-%m-%d %H:%M %A"),
                user_memory=user_mem,
                user_facts=facts,
            )
        }]
        # CPRS: auto-inject checkpoint if one exists for current project
        project = os.path.basename(os.getcwd())
        from aria.memory.checkpoint import get_checkpoint_data
        cp = get_checkpoint_data(project)
        if cp:
            plan_note = (
                " Plan has already been shown and approved — do NOT show the same plan again. Resume execution directly from next_step."
                if cp.get("plan_shown") else
                " When user asks to continue, show a plan and ask for approval before executing."
            )
            self.messages.append({
                "role": "user",
                "content": (
                    f"CPRS RELAY: A checkpoint exists from a previous session.\n"
                    f"Project: {cp['project']}\n"
                    f"Task: {cp['task']}\n"
                    f"Completed: {', '.join(cp['completed_steps']) if cp['completed_steps'] else 'none'}\n"
                    f"Next step: {cp['next_step']}\n"
                    f"Key paths: {', '.join(cp['key_paths']) if cp['key_paths'] else 'none'}\n"
                    f"Summary: {cp['summary']}\n"
                    f"Saved at: {cp['saved_at']}\n\n"
                    f"{plan_note}"
                )
            })
            console.print(
                f"  [aria.cyan]◉ CPRS[/aria.cyan] [aria.dim]Checkpoint loaded — "
                f"resuming '{cp['task'][:60]}'[/aria.dim]"
            )

    def _completion_gate_message(self) -> str:
        """Return a nudge message if the LLM is trying to finish without verifying.

        Returns empty string when completion is allowed.
        """
        # Not in task EXECUTING state → no gate
        if self.fsm.state != State.EXECUTING:
            return ""
        if self.fsm.skip_verification:
            return ""
        if not self.fsm.verified:
            return (
                "COMPLETION_BLOCKED: you have not called verify_goal yet. "
                f"Goal: '{self.fsm.goal[:120]}'. "
                "Call verify_goal with concrete evidence (files_created, commands_run with exit codes, "
                "expected_output that proves the goal was met). Do NOT mark the task done before verification."
            )
        if not self.fsm.acceptance_passed:
            return (
                "COMPLETION_BLOCKED: verify_goal passed, but acceptance_test has not run. "
                f"Goal: '{self.fsm.goal[:120]}'. "
                "Write a small runnable proof script and call acceptance_test(goal, test_code, expected_outcome). "
                "This proves the goal works end-to-end. ARIA v1.6 requires this before any task is marked done."
            )
        return ""

    # Safe tools allowed in conversational mode — read-only + identity memory.
    _CONVERSATIONAL_TOOLS = {"save_memory", "read_memory", "search_web"}

    def _run_conversational(self):
        """Fast path for greetings, questions, explanations.

        Allows a tiny set of safe tools (save_memory, read_memory, search_web) so the
        model can persist user identity or look up current facts during chat.
        """
        # Build a filtered tools list — only the safe set
        safe_tools = [t for t in TOOLS if t["function"]["name"] in self._CONVERSATIONAL_TOOLS]
        livestream.set_thinking()
        self._emit({"type": "thinking"})
        _on_token = (lambda t: self._emit({"type": "token", "text": t})) if self.emit_cb else None
        # Allow up to 3 tool-call rounds in chat (memory save + reply)
        for _ in range(3):
            try:
                msg_dict, tool_calls, text = stream_response(
                    self.client, self.model, self.messages, tools=safe_tools, on_token=_on_token
                )
            except RuntimeError as e:
                console.print(f"\n  [aria.error]◉[/aria.error] [aria.dim]{e}[/aria.dim]")
                return
            self.messages.append(msg_dict)
            if not tool_calls:
                print_response(text)
                break
            # Execute the safe tool call(s)
            for tc in tool_calls:
                name = tc["function"]["name"]
                if name not in self._CONVERSATIONAL_TOOLS:
                    result = f"ERROR: tool '{name}' not allowed in conversational mode."
                else:
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        args = {}
                    fn = TOOL_MAP.get(name)
                    try:
                        result = fn(**args) if fn else f"ERROR: unknown tool '{name}'"
                    except TypeError as e:
                        result = f"ERROR: wrong arguments for {name} — {e}"
                self.messages.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})
        livestream.set_done("Done")
        tok = sum(len(str(m.get("content",""))) // 4 for m in self.messages)
        update_tokens(tok, self.turn)
        self._log("Conversational reply")

    def _trim_context(self, max_tokens: int = 24000):
        """Enforce token budget using delta dedup + FIFO fallback.

        Dedup runs every turn (cheap, finds duplicate tool outputs).
        FIFO only runs when over budget.
        """
        before = self.budget.estimate(self.messages)

        # Always try dedup — cheap and frees space without dropping anything.
        from aria.context import delta
        new_msgs, dedup_stats = delta.compress(self.messages)
        if dedup_stats["dedup_count"]:
            self.messages = new_msgs
            self.budget._cache.clear()
            after_dedup = self.budget.estimate(self.messages)
            console.print(
                f"  [aria.cyan]◉ Delta[/aria.cyan] [aria.dim]"
                f"dedup {dedup_stats['dedup_count']} duplicates · "
                f"{dedup_stats['chars_saved']:,} chars saved · "
                f"{before:,} → {after_dedup:,} tok[/aria.dim]"
            )
            before = after_dedup

        # FIFO trim + recall pruning if still over budget.
        if before > max_tokens:
            # Use latest user message as recall query
            recall_query = ""
            for m in reversed(self.messages):
                if m.get("role") == "user":
                    recall_query = str(m.get("content", ""))
                    break
            self.messages, stats = self.budget.enforce(
                self.messages, limit=max_tokens, recall_query=recall_query
            )
            console.print(
                f"  [aria.cyan]◉ Budget[/aria.cyan] [aria.dim]"
                f"{before:,} → {stats['end_tokens']:,} tok · "
                f"truncated {stats.get('truncated', 0)} · "
                f"recall {stats.get('recall_dropped', 0)} · "
                f"FIFO {stats['fifo_dropped']}[/aria.dim]"
            )

    def _refresh_system_time(self):
        """Rebuild the system message with current date/time on every turn.

        Without this, the model anchors to session-start time and drifts into
        thinking it's still that moment hours later. Fresh wall-clock each turn
        keeps responses present-aware.
        """
        if not self.messages or self.messages[0].get("role") != "system":
            return
        from aria.memory.store import read_memory, read_user_facts
        facts = read_user_facts() or "(none yet — user has not shared identity)"
        self.messages[0]["content"] = SYSTEM_PROMPT.format(
            cwd=os.getcwd(),
            home=str(Path.home()),
            time=datetime.now().strftime("%Y-%m-%d %H:%M %A"),
            user_memory=read_memory(),
            user_facts=facts,
        )
        # Invalidate token cache for system msg
        if hasattr(self, "budget"):
            self.budget._cache.clear()

    def run(self, user_input: str):
        self.turn += 1
        self._log(f"Task: {user_input[:60]}")
        # M1 — harvest identity/preference facts from this user message into memory.json
        try:
            from aria.memory.harvest import apply as _harvest_apply
            captured = _harvest_apply(user_input)
            if captured:
                console.print(f"  [aria.cyan]◉ Memory[/aria.cyan] [aria.dim]captured: {', '.join(captured)}[/aria.dim]")
        except Exception:
            pass
        self._refresh_system_time()
        self._trim_context()
        self.messages.append({"role": "user", "content": user_input})

        # Mode routing — conversational gets a fast path with no tools.
        mode = classify_mode(user_input)
        if mode == "conversational":
            self._run_conversational()
            return

        # Task mode — reset controllers for this turn, then run full loop.
        self.fsm.reset()
        self.fsm.begin_task()
        self.loop_guard.reset()
        tool_guard.reset_turn_counts()
        # Validator harvests no-go list from user message (don't reset across task — sticks per session)
        self.validator.scan_user_message(user_input)

        step_num = 0
        MAX_STEPS = 150

        # Warn if context still large after trim
        ctx_est = sum(len(str(m.get("content","")))//4 for m in self.messages)
        _checkpoint_injected = False
        if ctx_est > 18000 and not _checkpoint_injected:
            _checkpoint_injected = True
            console.print(
                f"  [aria.warning]⚠[/aria.warning] [aria.dim]"
                f"Context ~{ctx_est:,} tokens — CPRS checkpoint recommended.[/aria.dim]"
            )
            self.messages.append({
                "role": "user",
                "content": (
                    f"CPRS ALERT: Context is ~{ctx_est:,} tokens. "
                    "Before continuing, call save_checkpoint with: current project name, "
                    "what task you are doing, what steps are completed, "
                    "exact next step, key file paths, and a short summary. "
                    "This ensures work can resume if context resets. Do it NOW before next action."
                )
            })
        elif ctx_est > 20000:
            console.print(f"  [aria.warning]⚠[/aria.warning] [aria.dim]Context large (~{ctx_est:,} tokens). Use /clear to reset.[/aria.dim]")

        invalid_tool_retries = 0

        while step_num < MAX_STEPS:
            # Trim context at start of each loop iteration to prevent buildup during long runs
            self._trim_context()
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
                # Runtime validator — reject false "task complete" claims, catch stale beliefs.
                recent_results = [m.get("content","") for m in self.messages[-8:] if m.get("role")=="tool"]
                rej = self.validator.check_completion_claim(text, recent_results)
                if rej:
                    self.messages.append({"role": "user", "content": rej})
                    console.print(f"  [aria.warning]⚠ Validator:[/aria.warning] [aria.dim]{rej.splitlines()[0][:80]}[/aria.dim]")
                    continue
                stale = self.validator.track_claims(text)
                if stale:
                    self.messages.append({"role": "user", "content": stale})
                    console.print(f"  [aria.warning]⚠ Validator:[/aria.warning] [aria.dim]{stale.splitlines()[0][:80]}[/aria.dim]")
                    continue
                # Completion gate — block "task done" until verify_goal + acceptance_test pass.
                gate_msg = self._completion_gate_message()
                if gate_msg:
                    self.messages.append({"role": "user", "content": gate_msg})
                    console.print(f"  [aria.warning]⚠ Gate:[/aria.warning] [aria.dim]{gate_msg.splitlines()[0][:80]}[/aria.dim]")
                    continue
                print_response(text)
                self._log("Task complete")
                livestream.set_done("Task complete")
                tok = sum(len(str(m.get("content",""))) // 4 for m in self.messages)
                update_tokens(tok, self.turn)
                self.fsm.mark_done()
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

                # FSM gate — block mutating tools unless plan is approved.
                allowed, reason = self.fsm.can_call(name)
                if not allowed:
                    result = reason
                    console.print(f"     [aria.warning]⚠ FSM:[/aria.warning] [aria.dim]{reason}[/aria.dim]")
                else:
                    # Tool guard — pre-execution validation (pip, rm -rf, pydantic v1, spec required, etc.)
                    tg_ok, tg_msg = tool_guard.validate(name, args, fsm=self.fsm)
                    # Runtime validator — hallucination + no-go list
                    being_created = name in {"write_file", "new_project"}
                    rv_ok, rv_msg = self.validator.check_tool_call(name, args, being_created=being_created)
                    if not tg_ok:
                        result = tg_msg
                        console.print(f"     [aria.warning]⚠ Guard:[/aria.warning] [aria.dim]{tg_msg.splitlines()[0][:80]}[/aria.dim]")
                    elif not rv_ok:
                        result = rv_msg
                        console.print(f"     [aria.warning]⚠ Validator:[/aria.warning] [aria.dim]{rv_msg.splitlines()[0][:80]}[/aria.dim]")
                    else:
                        fn = TOOL_MAP.get(name)
                        try:
                            result = fn(**args) if fn else f"ERROR: unknown tool '{name}'"
                        except TypeError as e:
                            result = f"ERROR: wrong arguments for {name} — {e}"
                        # Soft advisory (e.g., pydantic v1 detected) prepended to result
                        if tg_msg.startswith("WARN_"):
                            result = f"{tg_msg}\n---\n{result}"

                # Relation graph — auto-record key events
                from aria.context import relation as _rel
                project = os.path.basename(os.getcwd())
                task_id = f"{project}-{self.turn}"
                if name in ("write_file", "edit_file") and args.get("path"):
                    _rel.add(args["path"], "modified_by", task_id)
                elif name == "delete_file" and args.get("path"):
                    _rel.add(args["path"], "deleted_in", task_id)
                elif name == "new_project" and args.get("name"):
                    _rel.add(args["name"], "created_at", datetime.now().isoformat())

                # FSM transitions based on tool results.
                prev_state = self.fsm.state
                if name == "create_plan":
                    self.fsm.on_create_plan(args)
                    if str(result).strip() == "APPROVED":
                        self.fsm.state = State.EXECUTING
                        # Heuristic — if goal is purely read/explain/analyze, skip verification.
                        g_low = (self.fsm.goal or "").lower()
                        if any(w in g_low for w in ("read ", "explain ", "describe ", "analyze ", "review ")) \
                                and not any(w in g_low for w in ("create ", "build ", "fix ", "write ", "edit ", "modify ", "implement ", "run ", "test ", "deploy ")):
                            self.fsm.skip_verification = True
                # Emit state change for web UI
                if self.fsm.state != prev_state:
                    self._emit({"type": "fsm_state", "state": self.fsm.state.value, "goal": self.fsm.goal[:120]})

                if name == "verify_goal" and str(result).startswith("VERIFIED"):
                    self.fsm.verified = True
                    _rel.add(project, "verified_at", task_id)
                if name == "acceptance_test" and str(result).startswith("ACCEPTANCE_PASSED"):
                    self.fsm.acceptance_passed = True
                    _rel.add(project, "accepted_at", task_id)
                if name == "fetch_api_spec":
                    # Record domain so tool_guard knows spec was fetched
                    import re as _re
                    m = _re.search(r"domain ['\"]([^'\"]+)['\"]", str(result))
                    if m:
                        self.fsm.spec_fetched_domains.add(m.group(1))
                        _rel.add(m.group(1), "spec_fetched_for", task_id)

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

                # Phase C — if this successful call followed a recent error, persist as learned fix
                self.loop_guard.maybe_capture_fix(name, args, str(result))

                # Loop detection via LoopGuard
                signal = self.loop_guard.observe(name, str(result))
                if signal == "PIVOT":
                    console.print(
                        f"\n  [aria.warning]◉[/aria.warning] [aria.dim]"
                        f"Same error 3x — pivoting (attempt {self.loop_guard.pivot_count}/2)[/aria.dim]"
                    )
                    self.messages.append({"role": "user", "content": PIVOT_MESSAGE})
                elif signal == "EXHAUSTED":
                    console.print(
                        "\n  [aria.error]◉[/aria.error] [aria.dim]"
                        "All pivots exhausted — reporting honestly to user.[/aria.dim]"
                    )
                    self.messages.append({"role": "user", "content": EXHAUSTED_MESSAGE})
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
