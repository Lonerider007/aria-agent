# Changelog

All notable changes to ARIA.

## [1.6.1] — 2026-05-16 — Patch release

### Fixed
- `aria --reset` flag added to argparse (G3 fix was incomplete in 1.6.0 — the sys.argv check existed but argparse didn't register `--reset`, causing "unrecognized arguments" error).
- `aria --version` flag added — prints version and exits.
- `RuntimeValidator.check_completion_claim` no longer flags `STATE_ERROR` (FSM procedural blocks) or `WARN_*` advisories as "real failures". Previously caused 3x REJECTED_COMPLETION_CLAIM loops on tasks where the LLM made an early FSM-blocked attempt that was then properly retried via plan.

## [1.6.0] — 2026-05-16 — The Comeback Release

**Tagline:** *"Agent that writes code AND proves it works — verified end-to-end."*

### Added — comeback differentiator trio
- `verify_goal(goal, evidence)` tool — checks files exist, commands succeeded, expected output present, no Traceback. Required before any task completion.
- `fetch_api_spec(url_or_name)` tool — fetches OpenAPI/Swagger/docs to `~/.aria/spec_cache/`. Required before HTTP integration code (`requests`, `httpx`, `aiohttp`).
- `acceptance_test(goal, test_code, expected_outcome)` tool — runs a proof script in the project venv. Required before final "done".
- Completion gate in `agent.py` — LLM cannot return final response without tool_calls while verify/acceptance are pending.

### Added — architecture
- `controllers/router.py` — mode classifier (conversational vs task). Skips tool schema for greetings/questions.
- `controllers/state_machine.py` — `PlanFSM` with IDLE / PLANNING / AWAITING_APPROVAL / EXECUTING / DONE / REJECTED states. Mutating tools blocked until APPROVED.
- `controllers/tool_guard.py` — pre-execution rules: bare pip, dangerous rm, duplicate delete_file, Pydantic V1, HTTP-without-spec.
- `controllers/loop_guard.py` — error fingerprint tracking; auto-pivot on 3 identical errors; honest "I can't" after 2 pivots. Also captures successful recoveries to `rag/store.py` learned fixes.
- `context/delta.py` — duplicate tool-output dedup by content hash.
- `context/budget.py` — `TokenBudget`: dedup → recall pruning → FIFO with proper tool-call/result pair handling. Single oversized messages truncated.
- `context/recall.py` — pure-Python TF-IDF cosine + relation-graph proximity boost. No sklearn dependency.
- `context/relation.py` — SQLite relation graph at `~/.aria/relations.db`. Auto-records file edits, project switches, verified tasks.
- `validator/runtime.py` — `RuntimeValidator`: harvests user no-go list, blocks hallucinated file paths, rejects "task complete" claims with recent errors, catches stale-belief repetition.
- `tools/undo_log.py` — file mutation snapshot log per session.

### Added — commands & UX
- `/undo` and `/undo list` slash commands.
- Time awareness: system prompt rebuilt every turn with wall-clock (`YYYY-MM-DD HH:MM Weekday`).
- Prompt rule: never quote versions/dates from training memory; always `search_web` for "latest".

### Changed
- System prompt: **153 → 77 lines** (~50% reduction). Behaviors moved from prompt rules to code-level enforcement.
- `_trim_context` replaced by `budget.enforce()`; runs every turn, not just at task start.
- Streaming: `t.join(timeout=5)` on stream thread cleanup; `httpx.Timeout(read=300)` for slow Ollama.
- `read_file`, `list_files`, `search_in_files`: output capped at 16KB.
- `list_files` recursive: max 500 entries, skips `.git/node_modules/__pycache__/.venv/dist/build`.
- `run_command`: background process tracking with PID cleanup (max 10 concurrent, 30s cleanup, 24h max age).
- `/clear` also resets FSM, loop guard, validator, budget cache.
- Web bridge: version no longer hardcoded — imports `banner.VERSION`.

### Fixed
- **Security:** `git_commit` shell injection. Now uses `subprocess.run` list form.
- `git_create_branch` rejects unsafe branch names (spaces, `;|&$\``).
- `git_log` validates `n` as int before string interpolation.
- `main.py` onboarding fast-path — no longer triggers full TnC re-prompt when config has a stored api_key. Use `--reset` to force.

### Deferred to v1.6.1
- Web UI HTML rendering of new FSM states (event emit already wired in `agent.py`).
- FTS5 full-text index over delta chunks (TF-IDF + relation-graph proximity is current path).
- Sentence-transformers embedding recall behind `--recall=embeddings` flag.
- CPRS checkpoint schema migration to delta refs (still stores full content).

---

## [1.5.5] — Previous release

Bug fixes, minor polish on streaming/livestream UI.

## [1.5.0–1.5.4]

Sandbox + web mode + persistent memory + AST validator + RAG.

## [1.4.x]

See README "What's New" sections.
