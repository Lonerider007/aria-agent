"""
Type annotation compatibility rules.
"""
import ast
from typing import List


class TypeIssue:
    def __init__(self, line: int, code: str, message: str, fix: str):
        self.line    = line
        self.code    = code
        self.message = message
        self.fix     = fix

    def __repr__(self):
        return f"Line {self.line}: [{self.code}] {self.message} → Fix: {self.fix}"


def check_type_annotations(tree: ast.AST, python_version: tuple) -> List[TypeIssue]:
    issues = []

    for node in ast.walk(tree):
        # AnnAssign: variable: Type = value
        if isinstance(node, ast.AnnAssign):
            issues += _check_annotation(node.annotation, node.col_offset, python_version)

        # Function args and return types
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                if arg.annotation:
                    issues += _check_annotation(arg.annotation, arg.col_offset, python_version)
            if node.returns:
                issues += _check_annotation(node.returns, node.col_offset, python_version)

    return issues


def _check_annotation(node: ast.AST, col: int, python_version: tuple) -> List[TypeIssue]:
    issues = []
    line = getattr(node, 'lineno', 0)

    # Optional without subscript — e.g. `x: Optional`
    if isinstance(node, ast.Name) and node.id == "Optional":
        issues.append(TypeIssue(
            line=line,
            code="TYPE001",
            message="'Optional' used without type parameter",
            fix="Use 'Optional[YourType]' or 'YourType | None'"
        ))

    # Union without subscript — e.g. `x: Union`
    if isinstance(node, ast.Name) and node.id == "Union":
        issues.append(TypeIssue(
            line=line,
            code="TYPE002",
            message="'Union' used without type parameters",
            fix="Use 'Union[TypeA, TypeB]' or 'TypeA | TypeB'"
        ))

    # X | Y syntax requires Python 3.10+
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        if python_version < (3, 10):
            issues.append(TypeIssue(
                line=line,
                code="TYPE003",
                message=f"'X | Y' union syntax requires Python 3.10+, got {python_version}",
                fix="Use 'Union[X, Y]' or 'Optional[X]' for older Python"
            ))

    return issues
