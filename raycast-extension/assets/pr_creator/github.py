import shutil
import sys
import json
import re
import subprocess
from .utils import run_cmd, print_colored
from .config import load_config, add_to_user_map

def check_existing_pr(source_branch: str, target_branch: str) -> bool:
    """Check if an open PR already exists using 'gh'. Returns True if exists."""
    if shutil.which("gh") is None:
        return False

    # Debug info to stderr
    print_colored(f"Checking for existing PRs: {source_branch} -> {target_branch}...", "cyan")
    
    head = source_branch
    base = target_branch
    
    try:
        # We specify the current repo explicitly if possible, or just let gh handle it
        cmd = ["gh", "pr", "list", "--head", head, "--base", base, "--state", "open", "--json", "url,title"]
        result = run_cmd(cmd, capture=True)
        prs = json.loads(result.stdout)
        
        if prs:
            print_colored(f"[!] A PR already exists for {head} -> {base}", "yellow")
            return True
        return False

    except Exception as e:
        print_colored(f"Warning: Failed to check for existing PRs: {str(e)}", "yellow")
        return False

def resolve_handle(git_identity: str, interactive: bool = True) -> str:
    """Resolve 'Name <email>' to GitHub username via config or gh api."""
    email = None
    if "<" in git_identity and ">" in git_identity:
        m = re.search(r'<([^>]+)>', git_identity)
        if m:
            email = m.group(1)
    elif "@" in git_identity:
        email = git_identity.strip()
            
    if not email:
        return git_identity
    
    config = load_config()
    user_map = config.get("github_user_map", {})
    if email in user_map:
        return user_map[email]
        
    try:
        cmd = ["gh", "api", f"search/users?q={email}", "--jq", ".items[0].login"]
        result = run_cmd(cmd, capture=True, check=False)
        handle = result.stdout.strip()
        if handle:
            return handle
    except Exception:
        pass
    
    if not interactive:
        return None

    print_colored(f"Could not resolve GitHub username for: {email}", "yellow")
    # Note: In Raycast mode, input() will fail or hang. We should avoid it.
    return None 

def create_pr(source: str, target: str, title: str, body: str, reviewers: list[str] = None, skip_confirm: bool = False) -> dict:
    """
    Constructs and executes the gh pr create command.
    Returns a dict with 'url' and/or 'error'.
    """
    if not shutil.which("gh"):
        return {"error": "gh CLI not found"}

    cmd = [
        "gh", "pr", "create",
        "--base", target,
        "--head", source,
        "--title", title,
        "--body", body
    ]
    
    if reviewers:
         for r in reviewers:
            handle = resolve_handle(r, interactive=not skip_confirm)
            if handle:
                cmd.extend(["--reviewer", handle])

    try:
        # Use capture=True and check=True. If error, it raises CalledProcessError.
        result = run_cmd(cmd, capture=True)
        pr_url = result.stdout.strip()
        return {"url": pr_url}
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() or e.stdout.strip() or f"Exit code {e.returncode}"
        print_colored(f"GH Error: {error_msg}", "red")
        return {"error": error_msg}
    except Exception as e:
        return {"error": str(e)}

def get_contributors() -> list[str]:
    """Fetch list of contributors from GitHub API."""
    if shutil.which("gh") is None:
        return []
        
    try:
        cmd = ["gh", "api", "repos/:owner/:repo/contributors", "--jq", ".[].login"]
        result = run_cmd(cmd, capture=True)
        contributors = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return contributors
    except Exception:
        return []

def get_current_username() -> str:
    """Get the currently authenticated GitHub username."""
    if shutil.which("gh") is None:
        return ""
    try:
        cmd = ["gh", "api", "user", "--jq", ".login"]
        result = run_cmd(cmd, capture=True)
        return result.stdout.strip()
    except Exception:
        return ""
