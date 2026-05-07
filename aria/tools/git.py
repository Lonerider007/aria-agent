from aria.tools.shell import run_command


def git_status(cwd: str = None, path: str = None) -> str:
    return run_command("git status --short", cwd=cwd or path)


def git_diff(cwd: str = None, path: str = None) -> str:
    return run_command("git diff", cwd=cwd or path)


def git_commit(message: str, cwd: str = None, path: str = None) -> str:
    wd = cwd or path
    run_command("git add -A", cwd=wd)
    return run_command(f'git commit -m "{message}"', cwd=wd)


def git_create_branch(name: str, cwd: str = None, path: str = None) -> str:
    return run_command(f"git checkout -b {name}", cwd=cwd or path)


def git_log(n: int = 5, cwd: str = None, path: str = None) -> str:
    return run_command(f"git log --oneline -{n}", cwd=cwd or path)
