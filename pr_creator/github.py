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
                print_colored(f"- {pr.get('title')} ({pr.get('url')})", "yellow")
            print_colored("Skipping creation for this target.", "yellow")
            return True
        else:
            print_colored("No existing PR found. Proceeding...", "green")
            return False

    except (subprocess.CalledProcessError, json.JSONDecodeError):
        print_colored("Warning: Failed to check for existing PRs.", "yellow")
        return False

def resolve_handle(git_identity: str) -> str:
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
    
    # 3. Prompt user (Final Fallback)
    print_colored(f"Could not automatically resolve GitHub username for email: {email}", "yellow")
    user_input = input(f"Please enter GitHub username for {email} (or leave empty to skip): ").strip()
    if user_input:
        add_to_user_map(email, user_input)
        return user_input
    
    return None 

def create_pr(source: str, target: str, title: str, body: str, reviewers: list[str] = None):
    """
    Constructs and executes the gh pr create command.
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
            handle = resolve_handle(r)
            if handle:
                cmd.extend(["--reviewer", handle])
            else:
                print_colored(f"Warning: Could not resolve GitHub handle for '{r}'. Skipping.", "yellow")

    print_colored("Generated Command:", "cyan")
    # Masking body for display brevity if needed, but here we just show it all or summary
    # Just show the command as a string roughly
    cmd_str = f"gh pr create --base {target} --head {source} --title \"{title}\" ..."
    print(cmd_str)
    
    if shutil.which("gh"):
        user_conf = input(f"Create PR to {target}? [Y/n] ").strip().lower()
        if user_conf != 'n':
            try:
                run_cmd(cmd)
            except subprocess.CalledProcessError as e:
                print_colored(f"Command failed with exit code {e.returncode}", "red")
    else:
         print_colored("gh CLI not found.", "yellow")
