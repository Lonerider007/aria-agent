"""acceptance_test tool — Pillar E of v1.6: prove the goal works end-to-end.

After verify_goal passes, LLM must call acceptance_test with a small runnable
proof script. We execute it in a subprocess and check that the actual outcome
matches the expected outcome string.

Returns:
  "ACCEPTANCE_PASSED: <reason>" — script ran and outcome matched
  "ACCEPTANCE_FAILED: <reason>" — script crashed or outcome mismatched
"""
import os
import subprocess
import tempfile
from pathlib import Path

TIMEOUT = 60


def acceptance_test(goal: str, test_code: str, expected_outcome: str) -> str:
    """Run a small proof-of-goal script and verify the expected outcome.

    Args:
      goal: original user goal (for context in messages)
      test_code: runnable Python (or shell) snippet. Must produce stdout that
                 either contains `expected_outcome` literally OR exits 0 if
                 `expected_outcome` is the literal string "exit 0".
      expected_outcome: substring expected in stdout, or "exit 0" for just
                        successful execution.

    The script runs in the project venv if present, otherwise system python3.
    """
    if not test_code or not expected_outcome:
        return "ACCEPTANCE_FAILED: test_code and expected_outcome are both required."

    # Pick interpreter
    cwd = os.getcwd()
    venv_py = Path(cwd) / ".venv" / "bin" / "python"
    interpreter = str(venv_py) if venv_py.exists() else "python3"

    # Heuristic — is this shell or python?
    is_shell = test_code.strip().startswith("#!/bin/") or test_code.strip().startswith("bash ")

    suffix = ".sh" if is_shell else ".py"
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False) as tf:
        tf.write(test_code)
        tmp_path = tf.name

    try:
        if is_shell:
            os.chmod(tmp_path, 0o755)
            cmd = ["bash", tmp_path]
        else:
            cmd = [interpreter, tmp_path]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=TIMEOUT, cwd=cwd
            )
        except subprocess.TimeoutExpired:
            return f"ACCEPTANCE_FAILED: test exceeded {TIMEOUT}s timeout. Code may have hung or contains long-running loop."

        stdout = (result.stdout or "")[:4000]
        stderr = (result.stderr or "")[:2000]
        combined = stdout + "\n" + stderr

        if expected_outcome.strip().lower() in ("exit 0", "exit_0", "success"):
            if result.returncode == 0:
                return f"ACCEPTANCE_PASSED: goal '{goal[:60]}' — script exited 0.\nstdout: {stdout[:500]}"
            return f"ACCEPTANCE_FAILED: script exited {result.returncode}.\nstdout: {stdout[:500]}\nstderr: {stderr[:500]}"

        if expected_outcome in combined:
            return (
                f"ACCEPTANCE_PASSED: goal '{goal[:60]}' confirmed.\n"
                f"Expected '{expected_outcome[:60]}' found in output."
            )

        return (
            f"ACCEPTANCE_FAILED: expected '{expected_outcome[:60]}' NOT found in output.\n"
            f"Exit code: {result.returncode}\n"
            f"stdout: {stdout[:600]}\n"
            f"stderr: {stderr[:400]}\n"
            "Fix the implementation and retry. Do NOT mark task done until acceptance passes."
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
