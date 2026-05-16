"""verify_goal tool — Pillar C of v1.6: agent that proves work works.

After execution, the LLM must call this with the original goal and concrete
evidence that the goal was achieved. The verifier checks:

  1. Did the named artifacts (file paths) actually get created?
  2. Did the run commands succeed (exit_code 0)?
  3. Did the stated outcome show up in output (substring match)?
  4. Are there obvious failure signals in evidence (Traceback, ERROR)?

Returns:
  "VERIFIED: <reason>" — when all checks pass
  "VERIFY_FAILED: <reason>" — when any check fails; LLM must fix and retry
"""
import os
from pathlib import Path
from typing import Any


def verify_goal(goal: str, evidence: dict) -> str:
    """Verify a goal was achieved using concrete evidence.

    Args:
      goal: the user-stated goal (from create_plan or original input)
      evidence: structured dict with optional keys:
        files_created: list[str] — paths that should exist
        commands_run: list[{cmd, exit_code, stdout_excerpt}]
        expected_output: list[str] — substrings that should appear in any stdout
        forbidden_output: list[str] — substrings that should NOT appear
        notes: str — free-form reasoning

    Returns success or failure string.
    """
    if not isinstance(evidence, dict):
        return "VERIFY_FAILED: evidence must be a dict with files_created, commands_run, expected_output, etc."

    failures = []

    # 1. Files created
    files = evidence.get("files_created") or []
    for f in files:
        if not f:
            continue
        p = Path(str(f)).expanduser()
        if not p.exists():
            failures.append(f"  - File not found: {f}")
        elif p.is_file() and p.stat().st_size == 0:
            failures.append(f"  - File is empty: {f}")

    # 2. Commands succeeded
    cmds = evidence.get("commands_run") or []
    for c in cmds:
        if not isinstance(c, dict):
            continue
        ec = c.get("exit_code")
        if ec is not None and ec != 0:
            failures.append(f"  - Command failed (exit {ec}): {str(c.get('cmd',''))[:80]}")

    # 3. Expected output present
    all_stdout = "\n".join(str(c.get("stdout_excerpt", "")) for c in cmds if isinstance(c, dict))
    expected = evidence.get("expected_output") or []
    for needle in expected:
        if needle and str(needle) not in all_stdout:
            failures.append(f"  - Expected output not found: '{str(needle)[:60]}'")

    # 4. Forbidden output absent
    forbidden = evidence.get("forbidden_output") or []
    auto_forbidden = ["Traceback", "FATAL", "panic:"]
    for needle in list(forbidden) + auto_forbidden:
        if needle and str(needle) in all_stdout:
            failures.append(f"  - Forbidden output found: '{str(needle)[:60]}'")

    if failures:
        return (
            f"VERIFY_FAILED: goal '{goal[:80]}' could not be verified.\n"
            + "\n".join(failures)
            + "\nFix the failures and retry verification. Do NOT claim success until verified."
        )

    return (
        f"VERIFIED: goal '{goal[:80]}' confirmed via "
        f"{len(files)} file(s), {len(cmds)} command(s) checked."
    )
