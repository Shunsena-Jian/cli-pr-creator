import subprocess
from .utils import run_cmd, print_colored

def is_git_repo() -> bool:
    """Check if the current directory is a git repository."""
    try:
        run_cmd(["git", "rev-parse", "--is-inside-work-tree"], capture=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def fetch_latest_branches():
    """Fetch latest branches from origin."""
    print_colored("Fetching latest branches from origin...", "cyan")
    try:
        run_cmd(["git", "fetch", "origin"], check=False)
    except Exception:
        print_colored("Warning: Failed to fetch from origin. Using cached branches.", "yellow")

def get_remote_branches() -> list[str]:
    """Get a list of remote branches, stripping 'origin/' prefix."""
    try:
        result = run_cmd(["git", "branch", "-r"], capture=True)
        branches = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or "->" in line:
                continue
            # Strip origin/ prefix for cleaner selection/autocomplete
            if line.startswith("origin/"):
                line = line[len("origin/"):]
            branches.append(line)
        return branches
    except subprocess.CalledProcessError:
        return []

def get_authors() -> list[str]:
    """Get a list potential reviewers from git shortlog."""
    try:
        # -s: summary, -n: numbered sort, -e: email
        result = run_cmd(["git", "shortlog", "-sne", "--all"], capture=True)
        authors = []
        for line in result.stdout.splitlines():
            parts = line.strip().split("\t", 1)
            if len(parts) == 2:
                authors.append(parts[1])
        return authors
        return []
    except subprocess.CalledProcessError:
        return []

def get_current_branch() -> str:
    """Get the name of the currently checked out branch."""
    try:
        result = run_cmd(["git", "branch", "--show-current"], capture=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""

def get_commits_between(base: str, head: str) -> list[str]:
    """Get list of commit subject lines between base and head."""
    try:
        # --no-merges to skip merge commits, --oneline for subject only (but we want clean subject)
        # using formatted log to get just the subject
        cmd = ["git", "log", f"origin/{base}..{head}", "--no-merges", "--pretty=format:%s"]
        result = run_cmd(cmd, capture=True)
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return lines
    except subprocess.CalledProcessError:
        return []

def get_current_user_email() -> str:
    """Get the current git user's email."""
    try:
        result = run_cmd(["git", "config", "user.email"], capture=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""
