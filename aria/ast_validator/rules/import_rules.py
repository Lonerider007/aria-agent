"""
Import validation rules.
"""
import ast
import importlib.util
from typing import List


class ImportIssue:
    def __init__(self, line: int, code: str, module: str, message: str, fix: str):
        self.line    = line
        self.code    = code
        self.module  = module
        self.message = message
        self.fix     = fix

    def __repr__(self):
        return f"Line {self.line}: [{self.code}] {self.message} → Fix: {self.fix}"


# Packages that are commonly confused or renamed
KNOWN_RENAMES = {
    "sklearn":       "scikit-learn",
    "cv2":           "opencv-python",
    "PIL":           "Pillow",
    "bs4":           "beautifulsoup4",
    "yaml":          "pyyaml",
    "dotenv":        "python-dotenv",
    "jose":          "python-jose",
}


def check_imports(tree: ast.AST) -> List[ImportIssue]:
    issues = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                issue = _check_module(alias.name, node.lineno)
                if issue:
                    issues.append(issue)

        if isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                issue = _check_module(root, node.lineno)
                if issue:
                    issues.append(issue)

    return issues


LOCAL_MODULE_PATTERNS = {
    # Common project module names — not pip packages
    "app", "config", "database", "models", "schemas", "utils",
    "crud", "routers", "auth", "deps", "core", "api", "main",
    "settings", "exceptions", "middleware", "services", "tasks",
    # Single-file module names
    "task", "storage", "users", "posts", "comments", "routes",
    "views", "serializers", "forms", "admin", "urls", "wsgi",
    "asgi", "celery", "signals", "managers", "mixins", "helpers",
    "constants", "validators", "permissions", "filters", "tests",
    "conftest", "fixtures", "factories", "migrations",
}


def _check_module(module_name: str, line: int):
    root = module_name.split(".")[0]

    # Skip local/project modules — not pip packages
    if root in LOCAL_MODULE_PATTERNS:
        return None

    # Skip relative imports (start with .)
    if module_name.startswith("."):
        return None

    # Check if installable name differs
    pip_name = KNOWN_RENAMES.get(root)
    if pip_name:
        return ImportIssue(
            line=line,
            code="IMP001",
            module=root,
            message=f"'{root}' is imported as '{root}' but installed as '{pip_name}'",
            fix=f"pip install {pip_name}"
        )

    # Check if module can be found — only for known third-party style names
    spec = importlib.util.find_spec(root)
    if spec is None and not _is_stdlib(root):
        return ImportIssue(
            line=line,
            code="IMP002",
            module=root,
            message=f"Module '{root}' not found in current environment",
            fix=f"pip install {root}  (or activate the correct venv)"
        )

    return None


def _is_stdlib(name: str) -> bool:
    import sys
    return name in sys.stdlib_module_names
