"""
Import validation rules.
"""
import ast
import importlib.util
import os
from pathlib import Path
from typing import List, Optional


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


def _get_project_venv_packages(filepath: str = "") -> Optional[set]:
    """Find project .venv and return installed package names."""
    search_dirs = []
    if filepath:
        search_dirs.append(Path(filepath).parent)
    search_dirs.append(Path(os.getcwd()))

    for base in search_dirs:
        for venv_name in (".venv", "venv", "env"):
            venv = base / venv_name
            if not venv.exists():
                # Walk up to find venv
                for parent in base.parents:
                    venv = parent / venv_name
                    if venv.exists():
                        break
                else:
                    continue
            # Find site-packages
            site_pkgs = list(venv.glob("lib/python*/site-packages"))
            if site_pkgs:
                pkgs = set()
                for sp in site_pkgs:
                    for item in sp.iterdir():
                        name = item.name.split("-")[0].split(".")[0].lower()
                        pkgs.add(name)
                return pkgs
    return None


def check_imports(tree: ast.AST, filepath: str = "") -> List[ImportIssue]:
    project_pkgs = _get_project_venv_packages(filepath)
    issues = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                issue = _check_module(alias.name, node.lineno, project_pkgs)
                if issue:
                    issues.append(issue)

        if isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                issue = _check_module(root, node.lineno, project_pkgs)
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


def _check_module(module_name: str, line: int, project_pkgs: Optional[set] = None):
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

    # Skip stdlib modules
    if _is_stdlib(root):
        return None

    # Check project venv first — if found there, no issue
    if project_pkgs is not None:
        if root.lower() in project_pkgs:
            return None
        # Not in project venv — report missing
        return ImportIssue(
            line=line,
            code="IMP002",
            module=root,
            message=f"Module '{root}' not found in project venv",
            fix=f".venv/bin/pip install {root}"
        )

    # Fallback — check ARIA's own interpreter (less accurate)
    spec = importlib.util.find_spec(root)
    if spec is None:
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
