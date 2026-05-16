"""Pre-execution tool guards — enforce rules at code level.

These were previously prompt rules ("never run bare pip install"). Now they're
deterministic blocks. Returns a tool result string starting with BLOCKED: which
the LLM treats as a failure and retries with corrected args.
"""
import os
import re
from pathlib import Path
from typing import Dict, Tuple

# track per-turn tool call counts; reset by Agent at run() start
_TURN_CALL_COUNTS: Dict[str, int] = {}


def reset_turn_counts():
    _TURN_CALL_COUNTS.clear()


def _bump(tool_name: str) -> int:
    _TURN_CALL_COUNTS[tool_name] = _TURN_CALL_COUNTS.get(tool_name, 0) + 1
    return _TURN_CALL_COUNTS[tool_name]


# --- Pattern guards ---

DANGEROUS_RM_PATTERNS = [
    re.compile(r"rm\s+-rf?\s+/\s*(?:$|[^a-zA-Z0-9_-])"),         # rm -rf /
    re.compile(r"rm\s+-rf?\s+/\*"),                              # rm -rf /*
    re.compile(r"rm\s+-rf?\s+~\s*$"),                            # rm -rf ~
    re.compile(r"rm\s+-rf?\s+\$HOME\s*$"),                       # rm -rf $HOME
]

BARE_PIP_RE = re.compile(r"^\s*(sudo\s+)?pip\d?\s+install\b")
SYSTEM_PYTHON_PIP_RE = re.compile(r"(/usr/bin/python|/usr/local/bin/python)\d?\s+-m\s+pip\s+install")

PYDANTIC_V1_PATTERNS = [
    re.compile(r"class\s+Config\s*:\s*$", re.MULTILINE),
    re.compile(r"\borm_mode\s*=\s*True\b"),
    re.compile(r"\.from_orm\s*\("),
]

LEGACY_PYTEST_PATTERNS = [
    re.compile(r"pytest\s*<\s*8"),
    re.compile(r"pytest-asyncio\s*<\s*0\.23"),
]


def _check_run_command(args: Dict) -> Tuple[bool, str]:
    cmd = (args.get("command") or "").strip()
    if not cmd:
        return True, ""

    # Dangerous rm
    for pat in DANGEROUS_RM_PATTERNS:
        if pat.search(cmd):
            return False, f"BLOCKED: dangerous rm pattern detected — `{cmd[:60]}`. Refuse and ask user for explicit path."

    # rm -rf of cwd parent or absolute /home etc.
    rm_match = re.search(r"rm\s+-rf?\s+(\S+)", cmd)
    if rm_match:
        target = rm_match.group(1)
        cwd = os.getcwd()
        try:
            tgt_abs = Path(target).expanduser().resolve()
            if str(tgt_abs) == "/" or str(tgt_abs) == str(Path.home()):
                return False, f"BLOCKED: cannot rm `{tgt_abs}` (root or home). Specify a project subdirectory."
            if str(cwd).startswith(str(tgt_abs)) and str(tgt_abs) != str(cwd):
                return False, f"BLOCKED: target `{tgt_abs}` contains current working directory. Refuse."
        except Exception:
            pass

    # Bare pip install (without project venv)
    if BARE_PIP_RE.match(cmd) and ".venv/bin/pip" not in cmd and "venv/bin/pip" not in cmd:
        return False, (
            "BLOCKED: bare `pip install` is not allowed. Use the project venv:\n"
            "  .venv/bin/pip install <package>\n"
            "Or activate the venv first: source .venv/bin/activate && pip install <package>"
        )

    # System Python pip
    if SYSTEM_PYTHON_PIP_RE.search(cmd):
        return False, (
            "BLOCKED: do not install into the system Python. Use the project's `.venv/bin/pip`."
        )

    return True, ""


HTTP_INTEGRATION_RE = re.compile(
    r"\b(requests\.(get|post|put|delete|patch)|httpx\.(get|post|put|delete|patch|Client|AsyncClient)|aiohttp\.|urllib\.request\.urlopen)\b"
)
URL_IN_CODE_RE = re.compile(r"https?://([\w.-]+)")


def _check_write_file(args: Dict, fsm=None) -> Tuple[bool, str]:
    path = args.get("path") or ""
    content = args.get("content") or ""

    if not path.endswith(".py") or not content:
        return True, ""

    # HTTP integration without spec fetched → block
    if HTTP_INTEGRATION_RE.search(content) and fsm is not None:
        domains_in_code = set(URL_IN_CODE_RE.findall(content))
        # Filter localhost / placeholder hosts
        domains_in_code = {d for d in domains_in_code if d not in {"localhost", "127.0.0.1", "example.com", "api.example.com"}}
        if domains_in_code:
            fetched = getattr(fsm, "spec_fetched_domains", set()) or set()
            missing = [d for d in domains_in_code if not any(d.endswith(f) or f.endswith(d) for f in fetched)]
            if missing:
                return False, (
                    f"BLOCKED: write_file contains HTTP integration code for {missing} but "
                    "fetch_api_spec was not called for these domains. "
                    "Call fetch_api_spec(url) first — read the actual API contract, then write integration code."
                )

    warnings = []
    for pat in PYDANTIC_V1_PATTERNS:
        if pat.search(content):
            warnings.append(
                f"  - Pydantic V1 pattern `{pat.pattern}` detected. Use V2: "
                "`model_config = ConfigDict(from_attributes=True)`, `model_validate`, `model_dump`."
            )
            break

    for pat in LEGACY_PYTEST_PATTERNS:
        if pat.search(content):
            warnings.append(
                f"  - Legacy test pin `{pat.pattern}` detected. Use pytest>=8.1.0 on Python 3.14."
            )
            break

    if warnings:
        # Soft block — return as warning prefix; agent treats it as advisory
        return True, "WARN_PYDANTIC_V1:\n" + "\n".join(warnings)

    return True, ""


def _check_delete_file(args: Dict) -> Tuple[bool, str]:
    n = _bump("delete_file")
    if n > 1:
        return False, (
            "BLOCKED: delete_file called multiple times this turn. "
            "For bulk deletion use `run_command` with `rm -rf path1 path2 ...` in a single call."
        )
    return True, ""


def _check_new_project(args: Dict) -> Tuple[bool, str]:
    name = args.get("name", "")
    path = args.get("path") or os.getcwd()
    if not name:
        return True, ""
    target = Path(path) / name.replace(" ", "-").lower()
    if target.exists() and any(target.iterdir()):
        return False, (
            f"BLOCKED: `{target}` already exists and is not empty. "
            "Use a different name or `/workspace` to switch into existing project."
        )
    return True, ""


# --- Dispatch ---

CHECKS = {
    "run_command":  _check_run_command,
    "write_file":   _check_write_file,
    "delete_file":  _check_delete_file,
    "new_project":  _check_new_project,
}


def validate(tool_name: str, args: Dict, fsm=None) -> Tuple[bool, str]:
    """Run pre-execution checks. Returns (allowed, message).

    message starts with 'BLOCKED:' for hard blocks, 'WARN_' for advisory.
    fsm: optional PlanFSM — used by spec-required check.
    """
    fn = CHECKS.get(tool_name)
    if not fn:
        return True, ""
    # write_file needs FSM for spec check
    if tool_name == "write_file":
        return fn(args or {}, fsm=fsm)
    return fn(args or {})
