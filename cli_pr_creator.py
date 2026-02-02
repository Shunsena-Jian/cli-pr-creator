#!/usr/bin/env python3
import sys
import subprocess
import shutil
import readline

# --- Helpers ---
class SimpleCompleter:
    def __init__(self, options):
        self.options = sorted(options)
        self.matches = []
        
    def complete(self, text, state):
        if state == 0:
            if text:
                # Substring match, case-insensitive
                self.matches = [s for s in self.options if s and text.lower() in s.lower()]
            else:
                self.matches = self.options[:]
        try:
            return self.matches[state]
        except IndexError:
            return None

def print_colored(text: str, color: str = "green"):
    """
    Simple ANSI color printer. 
    Colors: green, red, yellow, cyan, bold
    """
    colors = {
        "green": "\033[92m",
        "red": "\033[91m",
        "yellow": "\033[93m",
        "cyan": "\033[96m",
        "bold": "\033[1m",
        "reset": "\033[0m"
    }
    prefix = colors.get(color, "")
    print(f"{prefix}{text}{colors['reset']}")

def is_git_repo() -> bool:
    """Check if the current directory is a git repository."""
    try:
        subprocess.check_output(
            ["git", "rev-parse", "--is-inside-work-tree"], 
            stderr=subprocess.STDOUT
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def get_remote_branches() -> list[str]:
    """Get a list of remote branches."""
    try:
        output = subprocess.check_output(["git", "branch", "-r"], text=True)
        branches = []
        for line in output.splitlines():
            line = line.strip()
            if not line or "->" in line:
                continue
            branches.append(line)
        return branches
    except subprocess.CalledProcessError:
        return []

def get_authors() -> list[str]:
    """Get a list potential reviewers from git shortlog."""
    try:
        # -s: summary, -n: numbered sort, -e: email
        output = subprocess.check_output(["git", "shortlog", "-sne", "--all"], text=True)
        authors = []
        for line in output.splitlines():
            # Format: "  10  Name <email>"
            parts = line.strip().split("\t", 1)
            if len(parts) == 2:
                authors.append(parts[1])
        return authors
    except subprocess.CalledProcessError:
        return []

def select_from_list(prompt: str, choices: list[str]) -> str:
    """
    Presents a numbered list of choices to the user and returns the selected item.
    Also allows typing the item directly if it matches (fuzzy or exact).
    Supports Tab-completion.
    """
    print_colored(f"\n{prompt}", "cyan")
    if not choices:
        return ""
    
    # Display list
    limit = 20 # don't spam if too many
    for idx, choice in enumerate(choices):
        if idx >= limit:
            print(f"... and {len(choices) - limit} more.")
            break
        print(f"[{idx+1}] {choice}")
    
    # Setup autocomplete
    completer = SimpleCompleter(choices)
    readline.set_completer(completer.complete)
    
    # Bind tab for both Mac (libedit) and Linux (GNU readline)
    if 'libedit' in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")

    print_colored("(Tip: You can use TAB to autocomplete branch names)", "bold")
    
    try:
        while True:
            user_input = input("Select number or type name: ").strip()
            if not user_input:
                continue
                
            # Check if number
            if user_input.isdigit():
                idx = int(user_input) - 1
                if 0 <= idx < len(choices):
                    return choices[idx]
            
            # Check if exact match or fuzzy
            # Priority: Exact match -> Contains
            matches = [c for c in choices if c == user_input]
            if len(matches) == 1:
                return matches[0]
                
            # Fuzzy/Contains
            matches = [c for c in choices if user_input.lower() in c.lower()]
            if len(matches) == 1:
                return matches[0]
            elif len(matches) > 1:
                print_colored(f"Ambiguous match: {', '.join(matches[:5])}...", "yellow")
            else:
                print_colored("Invalid selection, try again.", "red")
    finally:
        # Cleanup readline to avoid messing up subsequent inputs
        readline.set_completer(None)

def check_existing_pr(source_branch: str, target_branch: str):
    """Check if an open PR already exists for these branches."""
    # Clean branch names for gh (remove origin/)
    head = source_branch.replace("origin/", "").strip()
    base = target_branch.replace("origin/", "").strip()
    
    if shutil.which("gh") is None:
        return # Cannot check without gh

    print_colored("Checking for existing PRs...", "cyan")
    try:
        # gh pr list --head <head> --base <base> --state open --json url,title
        # Note: --head needs to be just the branch name usually, or owner:branch
        # If the user is running this in the repo, branch name usually suffices.
        cmd = ["gh", "pr", "list", "--head", head, "--base", base, "--state", "open", "--json", "url,title"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        import json
        prs = json.loads(result.stdout)
        
        if prs:
            print_colored(f"\n[!] A PR already exists for {head} -> {base}:", "red")
            for pr in prs:
                print_colored(f"- {pr.get('title')} ({pr.get('url')})", "yellow")
            print_colored("\nAborting creation process.", "red")
            sys.exit(0)
        else:
            print_colored("No existing PR found. Proceeding...", "green")

    except subprocess.CalledProcessError:
        print_colored("Warning: Failed to check for existing PRs (gh command failed).", "yellow")
    except json.JSONDecodeError:
         print_colored("Warning: Failed to parse gh output.", "yellow")

def main():
    print_colored("Welcome to this CLI PR Creator", "green")
    print_colored("="*30, "green")

    if not is_git_repo():
        print_colored("Error: This command must be executed in a git repository.", "red")
        sys.exit(1)

    # Fetch latest from origin
    print_colored("Fetching latest branches from origin...", "cyan")
    try:
        subprocess.run(["git", "fetch", "origin"], check=False) # Don't crash if offline
    except Exception:
        print_colored("Warning: Failed to fetch from origin. Using cached branches.", "yellow")

    # 1. Source Branch
    remote_branches = get_remote_branches()
    if not remote_branches:
        print_colored("Warning: No remote branches found. Make sure you have fetched.", "yellow")
    
    source_branch = select_from_list("From which remote branch?", remote_branches)
    print(f"Selected: {source_branch}")

    # 2. Target Branch
    target_branch = select_from_list("To which remote branch?", remote_branches)
    print(f"Selected: {target_branch}")

    # Check for existing PR
    check_existing_pr(source_branch, target_branch)

    # 3. Title
    print_colored("\nWhat is the PR title?", "cyan")
    pr_title = input("> ").strip()

    # 4. Jira
    print_colored("\nWhat are the JIRA Tickets or JIRA Release? (Enter multiple lines, press Enter to finish)", "cyan")
    jira_lines = []
    while True:
        line = input("> ").strip()
        if not line:
            break
        jira_lines.append(line)
    
    jira_info = "\n".join(jira_lines) if jira_lines else "None"

    # 5. Description
    print_colored("\nThe PR Description? (Enter multiple lines, press Enter on empty line to finish)", "cyan")
    description_lines = []
    while True:
        line = input("> ").strip()
        if not line:
            break
        description_lines.append(line)
    
    if description_lines:
        # Join with newlines and prefix with bullet
        # The template already has a newline before {description} if we want strictly 
        # but let's make sure it looks good.
        description = "\n".join([f"- {line}" for line in description_lines])
    else:
        description = "No description provided."

    # 6. Reviewers
    authors = get_authors()
    selected_reviewers = []
    
    print_colored("\nWho are the reviewers?", "cyan")
    print_colored("(Tip: You can use TAB to autocomplete reviewer names)", "bold")
    
    if not authors:
        print_colored("Could not find authors in git log.", "yellow")
    else:
        print(f"Found {len(authors)} authors in history.")

    # Bind tab for completion once here (or ensure it's bound)
    if 'libedit' in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")

    try:
        while True:
            # Filter out already selected
            available_authors = [a for a in authors if a not in selected_reviewers]
            
            # Update completer with current available authors
            # Add 'done' and 'list' to options for convenience
            completer = SimpleCompleter(available_authors + ['done', 'list'])
            readline.set_completer(completer.complete)

            # We can't use select_from_list easily in a loop with "Done" option integrated cleanly 
            # without modifying input logic. Let's do a custom loop here.
            if selected_reviewers:
                print_colored(f"Current reviewers: {', '.join(selected_reviewers)}", "green")
            
            user_input = input("\nType reviewer name/number to add (Press Enter to finish): ").strip()
            
            if not user_input:
                 # Stop if empty (Enter pressed directly)
                 break

            # Legacy 'd' check just in case, or list
            if user_input.lower() in ('d', 'done'):
                break
                
            if user_input.lower() in ('l', 'list'):
                 for idx, a in enumerate(available_authors):
                     if idx >= 20: 
                         print(f"... {len(available_authors)-20} more")
                         break
                     print(f"[{idx+1}] {a}")
                 continue
            
            # Match logic
            matched_author = None
            
            # Check if number
            if user_input.isdigit():
                idx = int(user_input) - 1
                if 0 <= idx < len(available_authors):
                    matched_author = available_authors[idx]
            
            if not matched_author:
                # Fuzzy match from full list
                matches = [a for a in available_authors if user_input.lower() in a.lower()]
                
                if len(matches) == 1:
                    matched_author = matches[0]
                elif len(matches) > 1:
                    # Check for exact match
                    exact = [a for a in matches if a.lower() == user_input.lower()]
                    if len(exact) == 1:
                        matched_author = exact[0]
                    else:
                        print_colored(f"Multiple matches found: {', '.join(matches[:5])}...", "yellow")
                        continue
                else:
                    if user_input.isdigit():
                         print_colored("Invalid number selection.", "red")
                    else:
                         print_colored("No match found.", "red")
                    continue

            if matched_author:
                selected_reviewers.append(matched_author)
                print_colored(f"Added {matched_author}", "green")
    finally:
        readline.set_completer(None)

    # Command construction
    gh_installed = shutil.which("gh") is not None
    
    pr_template = """**JIRA Ticket/Release:**
{tickets}

<br>**Description:**
{description}

<br>**Checklist:**

Refer to the checklist [here](https://qualitytrade.atlassian.net/wiki/spaces/BDT/pages/2708307969/Pull+request+guidelines)

- [ ] Checklist covered"""

    full_body = pr_template.format(tickets=jira_info, description=description)
    
    # Cleaning branch names 'origin/feat' -> 'feat'
    base = target_branch.replace("origin/", "")
    head = source_branch.replace("origin/", "")
    
    cmd = [
        "gh", "pr", "create",
        "--base", base,
        "--head", head,
        "--title", pr_title,
        "--body", full_body
    ]
    
    for r in selected_reviewers:
        # extracting email for safety if 'gh' needs login or email
        # gh often accepts email.
        val = r
        if "<" in r and ">" in r:
            import re
            m = re.search(r'<([^>]+)>', r)
            if m:
                val = m.group(1)
        cmd.extend(["--reviewer", val])
        
    print_colored("\n" + "="*30, "green")
    print_colored("Generated Command:", "cyan")
    print(" ".join(cmd))
    
    if gh_installed:
        confirm = input("\nExecute this command? [y/N] ").strip().lower()
        if confirm == 'y':
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError as e:
                print_colored(f"Command failed with exit code {e.returncode}", "red")
    else:
        print_colored("\n'gh' CLI not found on path. Please install GitHub CLI to execute commands automatically.", "yellow")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)
