"""Mode router — classify user input as conversational vs task.

Conversational: greetings, identity questions, factual Qs, opinions.
  → single LLM call, no tools, no plan, no FSM.
Task: any request that changes filesystem, runs code, or builds something.
  → full agent loop with FSM + tools.

When ambiguous, default to TASK (safer — extra plan is cheap, missed work is not).
"""
import re

ACTION_VERBS = {
    "build", "create", "make", "fix", "edit", "modify", "change",
    "run", "execute", "test", "deploy", "refactor", "write",
    "delete", "remove", "install", "uninstall", "setup", "init",
    "add", "implement", "debug", "migrate", "optimize", "upgrade",
    "scaffold", "generate", "compile", "push", "commit", "merge",
    "patch", "rename", "move", "copy", "format", "lint",
}

CONVERSATIONAL_STARTS = (
    "hi", "hello", "hey", "namaste", "yo",
    "who", "what", "why", "when", "where", "how",
    "kaun", "kya", "kyu", "kab", "kahan", "kaise",
    "thanks", "thank", "ok", "okay", "cool", "nice",
    "explain", "tell", "describe", "compare", "difference",
)

FILE_PATH_RE = re.compile(r"[\w./-]+\.(py|js|ts|tsx|jsx|md|json|yml|yaml|toml|sh|txt|html|css|sql)\b")
PATH_LIKE_RE = re.compile(r"(?:^|\s)(/|\./|\.\./|~/)[\w./-]+")
SLASH_COMMAND_RE = re.compile(r"^/(task|plan|build|fix|run)\b")


def classify(user_input: str) -> str:
    """Return 'conversational' or 'task'."""
    text = user_input.strip().lower()
    if not text:
        return "conversational"

    if SLASH_COMMAND_RE.match(text):
        return "task"

    words = re.findall(r"\b[\w']+\b", text)
    word_count = len(words)

    # Explicit action verb → task
    if any(w in ACTION_VERBS for w in words):
        return "task"

    # File paths or shell-y paths → task
    if FILE_PATH_RE.search(text) or PATH_LIKE_RE.search(text):
        return "task"

    # Very short input starting with greeting/question word → conversational
    first = words[0] if words else ""
    if word_count <= 8 and first in CONVERSATIONAL_STARTS:
        return "conversational"

    # Ends with "?" and no action verb → conversational
    if text.rstrip().endswith("?") and not any(w in ACTION_VERBS for w in words):
        return "conversational"

    # Default to task — safer
    return "task"
