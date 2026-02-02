#!/usr/bin/env python3
import sys
import subprocess
import shutil

# --- Helpers ---

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

def main():
    print_colored("Welcome to this CLI PR Creator", "green")
    print_colored("="*30, "green")

    if not is_git_repo():
        print_colored("Error: This command must be executed in a git repository.", "red")
        sys.exit(1)

    # 1. Source Branch
    remote_branches = get_remote_branches()
    if not remote_branches:
        print_colored("Warning: No remote branches found. Make sure you have fetched.", "yellow")
    
    source_branch = select_from_list("From which remote branch?", remote_branches)
    print(f"Selected: {source_branch}")

    # 2. Target Branch
    target_branch = select_from_list("To which remote branch?", remote_branches)
    print(f"Selected: {target_branch}")

    # 3. Title
    print_colored("\nWhat is the PR title?", "cyan")
    pr_title = input("> ").strip()

    # 4. Jira
    print_colored("\nWhat are the JIRA Tickets or JIRA Release (separated by comma)?", "cyan")
    jira_info = input("> ").strip()

    # 5. Description
    print_colored("\nThe PR Description?", "cyan")
    description = input("> ").strip()

    # 6. Reviewers
    authors = get_authors()
    selected_reviewers = []
    
    print_colored("\nWho are the reviewers?", "cyan")
    if not authors:
        print_colored("Could not find authors in git log.", "yellow")
    else:
        print(f"Found {len(authors)} authors in history.")

    while True:
        # Filter out already selected
        available_authors = [a for a in authors if a not in selected_reviewers]
        
        # We can't use select_from_list easily in a loop with "Done" option integrated cleanly 
        # without modifying input logic. Let's do a custom loop here.
        if selected_reviewers:
            print_colored(f"Current reviewers: {', '.join(selected_reviewers)}", "green")
        
        user_input = input("\nType reviewer name/number to add, 'l' to list, 'd' when done: ").strip()
        
        if user_input.lower() == 'd' or user_input == '':
            if not selected_reviewers and user_input == '':
                 # If empty input on first try, maybe they don't want reviewers or just pressed enter?
                 # Let's assume 'd' is explicit. If just enter, maybe ignore or ask.
                 # Let's require 'd' or 'done' to finish if they have added none? 
                 # Or just break.
                 pass
            
            if user_input.lower() == 'd':
                break
            if user_input == '' and selected_reviewers:
                break
            if user_input == '' and not selected_reviewers:
                 # Allow skipping reviewers
                 break
        
        if user_input.lower() == 'l':
             for idx, a in enumerate(available_authors):
                 if idx >= 20: 
                     print(f"... {len(available_authors)-20} more")
                     break
                 print(f"[{idx+1}] {a}")
             continue
        
        # Match logic
        # Is digit? -> index in available_authors (displayed via 'l' logic implies stable ordering?? 
        # Actually 'l' showed based on current filter. 
        # Let's rely on name matching mostly or list full if requested.
        
        # To make it simple: Just fuzzy match from full list
        matches = [a for a in available_authors if user_input.lower() in a.lower()]
        
        if len(matches) == 1:
            selected_reviewers.append(matches[0])
            print_colored(f"Added {matches[0]}", "green")
        elif len(matches) > 1:
            # Check for exact match
            exact = [a for a in matches if a.lower() == user_input.lower()]
            if len(exact) == 1:
                selected_reviewers.append(exact[0])
                print_colored(f"Added {exact[0]}", "green")
            else:
                print_colored(f"Multiple matches found: {', '.join(matches[:5])}...", "yellow")
                # optional: let them pick from narrowed list? For now just ask to be specific.
        else:
            print_colored("No match found.", "red")

    # Command construction
    gh_installed = shutil.which("gh") is not None
    
    full_body = f"{description}\n\nJira: {jira_info}"
    
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
