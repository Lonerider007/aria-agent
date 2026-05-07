"""
Python version compatibility rules.
"""
import ast
from typing import List


class CompatIssue:
    def __init__(self, line: int, code: str, message: str, fix: str):
        self.line    = line
        self.code    = code
        self.message = message
        self.fix     = fix

    def __repr__(self):
        return f"Line {self.line}: [{self.code}] {self.message} → Fix: {self.fix}"


def check_compat(tree: ast.AST, python_version: tuple) -> List[CompatIssue]:
    issues = []

    for node in ast.walk(tree):

        # match statement — requires 3.10+
        if isinstance(node, ast.Match) and python_version < (3, 10):
            issues.append(CompatIssue(
                line=node.lineno,
                code="COMPAT001",
                message=f"'match' statement requires Python 3.10+, got {python_version}",
                fix="Use if/elif chain for older Python"
            ))

        # walrus operator := — requires 3.8+
        if isinstance(node, ast.NamedExpr) and python_version < (3, 8):
            issues.append(CompatIssue(
                line=node.lineno,
                code="COMPAT002",
                message=f"Walrus operator ':=' requires Python 3.8+",
                fix="Use a regular assignment before the expression"
            ))

        # f-strings — requires 3.6+
        if isinstance(node, ast.JoinedStr) and python_version < (3, 6):
            issues.append(CompatIssue(
                line=getattr(node, 'lineno', 0),
                code="COMPAT003",
                message="f-strings require Python 3.6+",
                fix="Use .format() or % formatting"
            ))

        # Exception groups (3.11+)
        if isinstance(node, ast.ExceptHandler):
            if isinstance(getattr(node, 'type', None), ast.Starred) and python_version < (3, 11):
                issues.append(CompatIssue(
                    line=node.lineno,
                    code="COMPAT004",
                    message="Exception groups require Python 3.11+",
                    fix="Use separate try/except blocks"
                ))

    return issues
