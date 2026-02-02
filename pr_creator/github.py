import shutil
import sys
import json
import re
import subprocess
from .utils import run_cmd, print_colored

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
    """Resolve 'Name <email>' to GitHub username via gh api."""
    email = None
    if "<" in git_identity and ">" in git_identity:
        m = re.search(r'<([^>]+)>', git_identity)
        if m:
            email = m.group(1)
            
    if not email:
        return git_identity
        
    try:
        cmd = ["gh", "api", f"search/users?q={email}", "--jq", ".items[0].login"]
        result = run_cmd(cmd, capture=True, check=False)
        handle = result.stdout.strip()
        if handle:
            return handle
    except Exception:
        pass
    return email 

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
            cmd.extend(["--reviewer", handle])

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
