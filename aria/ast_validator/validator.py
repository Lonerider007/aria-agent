"""
Core AST Validator — entry point.
ARIA's pre-execution intelligence layer.

Formula: AST(code) → Intent → Attention → Context → Validated Output
"""
import ast
import sys
from typing import Optional

from .rules.type_rules   import check_type_annotations
from .rules.import_rules import check_imports
from .rules.compat       import check_compat
from .rules.removed_nodes import check_removed_nodes
from .reporter           import format_issues, format_for_llm


class ValidationResult:
    def __init__(self, valid: bool, issues: list, filepath: str = ""):
        self.valid    = valid
        self.issues   = issues
        self.filepath = filepath

    def for_llm(self) -> str:
        return format_for_llm(self.issues, self.filepath)

    def for_human(self) -> str:
        return format_issues(self.issues, self.filepath)

    def __bool__(self):
        return self.valid


class ASTValidator:
    def __init__(self, python_version: Optional[tuple] = None):
        self.python_version = python_version or sys.version_info[:2]

    def validate(self, code: str, filepath: str = "<code>") -> ValidationResult:
        """
        Parse and validate Python code.
        Returns ValidationResult with all issues found.
        """
        # Parse
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            issue = _SyntaxIssue(e)
            return ValidationResult(valid=False, issues=[issue], filepath=filepath)

        # Run all rule sets
        issues = []
        issues += check_type_annotations(tree, self.python_version)
        issues += check_imports(tree)
        issues += check_compat(tree, self.python_version)
        issues += check_removed_nodes(tree)

        return ValidationResult(
            valid=len(issues) == 0,
            issues=sorted(issues, key=lambda x: x.line),
            filepath=filepath
        )


class _SyntaxIssue:
    def __init__(self, e: SyntaxError):
        self.line    = e.lineno or 0
        self.code    = "SYN001"
        self.message = f"Syntax error: {e.msg}"
        self.fix     = "Fix the syntax before running"

    def __repr__(self):
        return f"Line {self.line}: [{self.code}] {self.message}"
