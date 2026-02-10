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

    print_colored("Checking for existing PRs...", "cyan")
    # Branch names are already stripped of 'origin/'
    head = source_branch
    base = target_branch
    
    try:
        cmd = ["gh", "pr", "list", "--head", head, "--base", base, "--state", "open", "--json", "url,title"]
        result = run_cmd(cmd, capture=True)
        prs = json.loads(result.stdout)
        
        if prs:
            print_colored(f"\n[!] A PR already exists for {head} -> {base}:", "red")
            for pr in prs:
                print_colored(f"- {pr.get('title')}", "yellow")
                print_colored(f"  URL: {pr.get('url')}", "bold")
            print_colored("Skipping creation for this target.", "yellow")
            return True
        else:
            print_colored("No existing PR found. Proceeding...", "green")
            return False

    except (subprocess.CalledProcessError, json.JSONDecodeError):
        print_colored("Warning: Failed to check for existing PRs.", "yellow")
        return False

def resolve_handle(git_identity: str, interactive: bool = True) -> str:
    """Resolve 'Name <email>' to GitHub username via config or gh api. Returns None if not found."""
    email = None
    # Handle "Name <email>" format
    if "<" in git_identity and ">" in git_identity:
        m = re.search(r'<([^>]+)>', git_identity)
        if m:
            email = m.group(1)
    # Handle raw email format
    elif "@" in git_identity:
        email = git_identity.strip()
            
    if not email:
        # If it doesn't look like an email, assume it's already a handle or name
        return git_identity
    
    # 1. Check Config Map
    config = load_config()
    user_map = config.get("github_user_map", {})
    if email in user_map:
        return user_map[email]
        
    # 2. Try GH API
    try:
        cmd = ["gh", "api", f"search/users?q={email}", "--jq", ".items[0].login"]
        result = run_cmd(cmd, capture=True, check=False)
        handle = result.stdout.strip()
        if handle:
            return handle
    except Exception:
        pass
    
    # 3. Prompt user (Final Fallback) - Skip if not interactive
    if not interactive:
        return None

    print_colored(f"Could not automatically resolve GitHub username for email: {email}", "yellow")
    user_input = input(f"Please enter GitHub username for {email} (or leave empty to skip): ").strip()
    if user_input:
        add_to_user_map(email, user_input)
        return user_input
    
    return None 

def create_pr(source: str, target: str, title: str, body: str, reviewers: list[str] = None, skip_confirm: bool = False) -> str:
    """
    Constructs and executes the gh pr create command.
    Returns the URL of the created PR, or None if failed/skipped.
    """
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
            else:
                print_colored(f"Warning: Could not resolve GitHub handle for '{r}'. Skipping.", "yellow")

    if not shutil.which("gh"):
        print_colored("gh CLI not found.", "yellow")
        return None

    if not skip_confirm:
        print_colored("\nGenerated Command Preview:", "cyan")
        cmd_str = f"gh pr create --base {target} --head {source} --title \"{title}\" ..."
        print(f"  {cmd_str}")
        user_conf = input(f"Create PR to {target}? [Y/n] ").strip().lower()
        if user_conf == 'n':
            return None

    try:
        result = run_cmd(cmd, capture=True)
        pr_url = result.stdout.strip()
        print_colored(f"SUCCESS: PR created for {target}", "green")
        print_colored(f"URL: {pr_url}", "bold")
        return pr_url
    except subprocess.CalledProcessError as e:
        print_colored(f"Command failed with exit code {e.returncode} for target {target}", "red")
        if e.stdout: print(e.stdout)
        if e.stderr: print(e.stderr)
        return None

def get_contributors() -> list[str]:
    """
    Fetch list of contributors (handles) from GitHub API.
    Uses :owner and :repo placeholders which gh CLI resolves from current directory.
    """
    if shutil.which("gh") is None:
        return []
        
    try:
        # Fetch contributors, returning just their login (handle)
        cmd = ["gh", "api", "repos/:owner/:repo/contributors", "--jq", ".[].login"]
        result = run_cmd(cmd, capture=True)
        contributors = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return contributors
    except (subprocess.CalledProcessError, Exception):
        # Fail silently or log if needed, fallback will handle it
        return []

def get_current_username() -> str:
    """Get the currently authenticated GitHub username."""
    if shutil.which("gh") is None:
        return ""
    try:
        # Check cached auth status or api user
        # 'gh api user' is reliable
        cmd = ["gh", "api", "user", "--jq", ".login"]
        result = run_cmd(cmd, capture=True)
        return result.stdout.strip()
    except Exception:
        return ""


