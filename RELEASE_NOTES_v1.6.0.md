# ARIA v1.6.0 — The Comeback Release

> *Agent that writes code AND proves it works — verified end-to-end.*

Most coding agents — Aider, Cursor, even Claude Code — mark tasks done on **structural completion**: the files exist, the code looks plausible, no syntax errors. The agent reports success. Then you run the code and it doesn't actually work.

ARIA v1.6 closes this gap with three gates enforced at the code level:

### 1. `fetch_api_spec` before HTTP integration
No more hardcoded params from training-era memory. If your code calls `requests.get("https://api.example.com/...")` and you never fetched the spec for `api.example.com` this session, the write is **blocked**.

### 2. `verify_goal` before any "done"
The agent must call `verify_goal(goal, evidence)` with concrete proof — files that exist, commands that exited 0, expected output that actually appeared. No evidence? No completion.

### 3. `acceptance_test` proves it works
A small runnable script that demonstrates the goal. Trading bot? Simulate a paper trade and assert P&L updates. CRUD API? Send a real request and assert response shape. Until this passes, the task isn't done.

The agent can't "I'm done!" past these gates. If verification fails, ARIA reports honestly: *what was tried, what blocked it, what the simplest next step is.*

---

## Architecture upgrades

Behaviors that used to live in the system prompt (and which LLMs would politely ignore) are now **deterministic code**:

| Old (prompt rule, often ignored) | New (code, always enforced) |
|---|---|
| "Never run bare `pip install`" | Tool guard blocks; suggests `.venv/bin/pip` |
| "Use Pydantic V2 patterns" | Pre-write lint warns on `orm_mode`, `from_orm`, `class Config:` |
| "Never call write_file before plan approval" | FSM blocks at the agent loop |
| "Stop after 3 retries" | LoopGuard fingerprints errors, pivots automatically |
| "Don't claim done if errors exist" | RuntimeValidator inspects recent results before accepting "done" |

### Memory & context

- **Mode router** — greetings and factual questions bypass tools entirely (single API call, ~600 tokens saved per turn).
- **Delta context memory** — repeated tool outputs (re-reads of the same file, re-runs of the same command) get replaced with short references. Long sessions stay flat in tokens.
- **Adaptive recall (TF-IDF + relation-graph)** — when over budget, irrelevant old messages get dropped first. Project switches preserve current-task context.
- **System prompt size: 153 → 77 lines.**

### Time awareness

System prompt is rebuilt every turn with the real wall-clock (`YYYY-MM-DD HH:MM Weekday`). The model is forbidden to quote versions or dates from training memory — for anything "current" or "latest", it must call `search_web`. No more "as of my last update…".

### Runtime validator

- **Hallucinated file paths** → blocked (tool can't reference a file that doesn't exist and isn't being created by this call).
- **No-go list** — when user says "don't touch X" or "leave Y alone", the validator harvests these tokens and blocks any tool call that targets them.
- **Completion claim rejection** — if the LLM says "task complete" while recent tool results contain `ERROR / Traceback / BLOCKED / VERIFY_FAILED`, the claim is rejected and the LLM is asked to re-examine.
- **Stale belief catch** — if the same factual claim repeats across 3+ turns without re-verifying, the validator forces a re-check.

### Security & hygiene

- `git_commit` shell injection fixed (subprocess list form).
- `git_create_branch` rejects unsafe branch names.
- Web bridge version no longer hardcoded.
- Onboarding fast-path no longer re-prompts TnC on existing configs.
- Output caps on `read_file` (16KB), `list_files` recursive (500 entries + noise-dir skip), `search_in_files` (200 matches/file).

### New: `/undo`

```
> /undo            # rolls back the most recent write/edit/delete
> /undo list       # shows recent mutations this session
```

Lightweight per-session snapshot at `~/.aria/undo/<pid>/`. For complex rollbacks use git.

---

## Install / upgrade

```bash
pipx upgrade aria-x
# or fresh:
pipx install aria-x
```

Web extras unchanged:
```bash
pip install 'aria-x[web]'
aria web
```

## Try the new flow

```
◉ aria(my-project) › build a python script that fetches the current bitcoin price
                     from coingecko and saves it to btc.txt
```

Watch the gates fire:
1. `fetch_api_spec("coingecko docs")`
2. `create_plan(...)` → user approves
3. `write_file("btc.py", ...)` — allowed because spec was fetched
4. `run_command("python btc.py")`
5. `verify_goal(goal, {files_created:["btc.txt"], commands_run:[...], expected_output:["$"]})`
6. `acceptance_test(goal, "cat btc.txt | grep -E '\\d+'", "exit 0")`
7. Done — for real this time.

---

## Compatibility

- Python 3.10+ (3.14 tested).
- Existing `~/.aria/` data preserved — no schema migration needed.
- All prior slash commands work; `/clear` is now more thorough (resets FSM + guards + validator).

---

**Credits:** ARIA by Sumit (vision, direction). Implementation in collaboration with Claude Code.
