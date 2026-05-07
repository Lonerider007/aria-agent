"""
Intent classification for AST nodes.
Maps Python AST node types to human-understandable intents.
"""
import ast


class Intent:
    IMPORT      = "import"
    TYPE_HINT   = "type_hint"
    DEFINE      = "define"
    CALL        = "call"
    CONTROL     = "control"
    IO          = "io"
    ASSIGN      = "assign"
    RETURN      = "return"
    UNKNOWN     = "unknown"


def classify(node: ast.AST) -> str:
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return Intent.IMPORT
    if isinstance(node, ast.AnnAssign):
        return Intent.TYPE_HINT
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return Intent.DEFINE
    if isinstance(node, ast.Call):
        return Intent.CALL
    if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
        return Intent.CONTROL
    if isinstance(node, (ast.Assign, ast.AugAssign)):
        return Intent.ASSIGN
    if isinstance(node, ast.Return):
        return Intent.RETURN
    return Intent.UNKNOWN
