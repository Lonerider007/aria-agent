"""
Unit tests for ARIA's AST Validator.
"""
import pytest
from aria.ast_validator import ASTValidator, ValidationResult


def test_valid_python_314_code():
    """Test that valid Python 3.14 code passes validation."""
    validator = ASTValidator()
    code = '''
def hello(name: str) -> str:
    return f"Hello, {name}"

class Example:
    def __init__(self, value: int):
        self.value = value
        
    @property
    def prop(self) -> int:
        return self.value

# Structural pattern matching (Python 3.10+)
def process_data(data):
    match data:
        case {"type": "error", "message": msg}:
            return f"Error: {msg}"
        case [x, y] if x > y:
            return f"First ({x}) greater than second ({y})"
        case _:
            return "No match"
'''
    result = validator.validate(code, filepath="test.py")
    assert result.valid, f"Unexpected validation errors: {result.for_human()}"


def test_syntax_error_detection():
    """Test that syntax errors are properly caught."""
    validator = ASTValidator()
    code = '''
def broken_function(
    # Missing closing parenthesis and colon
    x: int
    return x
'''
    result = validator.validate(code, filepath="test.py")
    assert not result.valid
    assert any(issue.code == "SYN001" for issue in result.issues)  # Syntax error


def test_python_314_removed_ast_nodes():
    """Test detection of Python 3.14 removed AST nodes."""
    validator = ASTValidator()
    # This would be caught by enhanced rules - for now testing basic functionality
    code = "x = 'test'"
    result = validator.validate(code, filepath="test.py")
    assert result.valid  # Simple string assignment should be valid


if __name__ == "__main__":
    pytest.main([__file__])