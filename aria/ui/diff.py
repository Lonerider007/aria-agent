from .console import console


def show_diff(filepath: str, old: str, new: str):
    old_lines = old.splitlines()
    new_lines = new.splitlines()

    console.print(f"\n  [aria.dim]{filepath.upper()}[/aria.dim]")
    console.print(f"  [aria.dim]{'─' * 40}[/aria.dim]")

    import difflib
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))

    for line in diff[2:]:  # skip --- +++ header
        if line.startswith("+"):
            console.print(f"  [aria.success]+ {line[1:]}[/aria.success]")
        elif line.startswith("-"):
            console.print(f"  [aria.error]- {line[1:]}[/aria.error]")
        elif line.startswith("@@"):
            console.print(f"  [aria.dim]{line}[/aria.dim]")
        else:
            console.print(f"  [aria.dim]  {line}[/aria.dim]")

    console.print()
