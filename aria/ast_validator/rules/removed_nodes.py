"""
Rules for detecting Python 3.14+ removed AST nodes.
In Python 3.14, the following legacy AST nodes are removed:
- ast.Str
- ast.Bytes
- ast.Num
- ast.NameConstant
- ast.Ellipsis (note: Ellipsis as a singleton is still available, but the node type is removed)

These are replaced by ast.Constant.
"""
import ast
from typing import List


# Check if removed node types exist (they don't in Python 3.14+)
_HAS_STR = hasattr(ast, 'Str')
_HAS_BYTES = hasattr(ast, 'Bytes')
_HAS_NUM = hasattr(ast, 'Num')
_HAS_NAMECONSTANT = hasattr(ast, 'NameConstant')
_HAS_ELLIPSIS = hasattr(ast, 'Ellipsis')


class RemovedNodeIssue:
    def __init__(self, line: int, code: str, message: str, fix: str):
        self.line    = line
        self.code    = code
        self.message = message
        self.fix     = fix

    def __repr__(self):
        return f"Line {self.line}: [{self.code}] {self.message} → Fix: {self.fix}"


def check_removed_nodes(tree: ast.AST) -> List[RemovedNodeIssue]:
    issues = []
    # Only check for removed nodes if they exist in this Python version
    # In Python 3.14+, these won't exist, so we won't flag anything
    # This rule is primarily for backward compatibility or when running on older Python
    
    for node in ast.walk(tree):
        # Check for removed node types only if they exist
        if _HAS_STR and isinstance(node, ast.Str):
            issues.append(RemovedNodeIssue(
                line=getattr(node, 'lineno', 0),
                code="REM001",
                message="ast.Str is removed in Python 3.14+, use ast.Constant",
                fix="String literals are now represented as ast.Constant nodes"
            ))
        elif _HAS_BYTES and isinstance(node, ast.Bytes):
            issues.append(RemovedNodeIssue(
                line=getattr(node, 'lineno', 0),
                code="REM002",
                message="ast.Bytes is removed in Python 3.14+, use ast.Constant",
                fix="Bytes literals are now represented as ast.Constant nodes"
            ))
        elif _HAS_NUM and isinstance(node, ast.Num):
            issues.append(RemovedNodeIssue(
                line=getattr(node, 'lineno', 0),
                code="REM003",
                message="ast.Num is removed in Python 3.14+, use ast.Constant",
                fix="Number literals are now represented as ast.Constant nodes"
            ))
        elif _HAS_NAMECONSTANT and isinstance(node, ast.NameConstant):
            issues.append(RemovedNodeIssue(
                line=getattr(node, 'lineno', 0),
                code="REM004",
                message="ast.NameConstant is removed in Python 3.14+, use ast.Constant",
                fix="True, False, None literals are now represented as ast.Constant nodes"
            ))
        elif _HAS_ELLIPSIS and isinstance(node, ast.Ellipsis):
            issues.append(RemovedNodeIssue(
                line=getattr(node, 'lineno', 0),
                code="REM005",
                message="ast.Ellipsis is removed in Python 3.12+, use ast.Constant",
                fix="Ellipsis literal is now represented as ast.Constant nodes"
            ))
    return issues