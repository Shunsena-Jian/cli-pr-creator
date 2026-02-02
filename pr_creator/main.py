import sys
from .utils import print_colored, run_cmd, normalize_jira_link
from .git import is_git_repo, fetch_latest_branches, get_remote_branches, get_authors, get_current_branch, get_commits_between
from .github import check_existing_pr, create_pr
from .ui import select_from_list, get_multiline_input, prompt_reviewers
from .config import load_config
from .naming import parse_branch_name
from .strategy import prompt_strategy, resolve_placeholder_targets

def main():
    print_colored("Welcome to this CLI PR Creator", "green")
    print_colored("="*30, "green")

    if not is_git_repo():
        print_colored("Error: Not a git repository.", "red")
        sys.exit(1)

    config = load_config()
    default_target = config.get("default_target_branch", "main")
    jira_base_url = config.get("jira_base_url", "https://qualitytrade.atlassian.net/browse/")

    fetch_latest_branches()
    remote_branches = get_remote_branches()
    current_branch = get_current_branch()

    # --- 1. Determine Context & Strategy ---
    
    source_branch = current_branch
    
    print(f"Current Branch (Source): {source_branch}")
    
    strategy_name, source_branch, target_candidates = prompt_strategy(source_branch, remote_branches)
    
    targets = []
    if strategy_name == "Manual":
        # Fallback to standard flow
        target_candidates = [] # Logic handled below in manual loop
    else:
        # Resolve placeholders
        targets = resolve_placeholder_targets(target_candidates, remote_branches, default_target)
    
    # If manual, we ask for target
    if strategy_name == "Manual" or not targets:
        if strategy_name != "Manual":
            print_colored("No valid targets determined from strategy. Reverting to manual selection.", "yellow")
        
        # Explicitly ask for Source if manual
        if strategy_name == "Manual":
            if remote_branches:
                # Default to current if available
                source_branch = select_from_list(f"Source Branch? (Current: {source_branch})", remote_branches)
            else:
                source_branch = input(f"Source Branch? (Default: {source_branch}) ").strip() or source_branch

        t_choice = select_from_list(f"Target Branch? (Default: {default_target})", remote_branches)
        targets = [t_choice]

    # --- 2. Shared Metadata ---
    # We collect Title/Desc/Tickets ONCE, then apply to all PRs (maybe varying title slightly?)
    
    ticket_auto, title_auto = parse_branch_name(source_branch)
    
    # JIRA Flow
    print_colored("\n--- JIRA Details ---", "cyan")
    print("1. Enter JIRA Ticket IDs")
    print("2. Enter JIRA Release info")
    print("3. Skip / Manual")
    j_choice = input("Select [1-3]: ").strip()
    
    jira_section = ""
    
    if j_choice == "1":
        ids = get_multiline_input("Enter JIRA Ticket IDs (e.g. PROJ-123):")
        links = [normalize_jira_link(t, jira_base_url) for t in ids]
        jira_section = "\n".join(links)
        # Update ticket_auto if empty
        if not ticket_auto and ids:
            ticket_auto = ",".join(ids)
            
    elif j_choice == "2":
        r_title = input("Release Title: ").strip()
        r_url = input("Release URL: ").strip()
        jira_section = f"[{r_title}]({r_url})"
        if not title_auto:
            title_auto = r_title
            
    else:
        jira_section = "None"
        title_auto = ""

    # Title & Description
    print_colored(f"\nTitle (Default: {title_auto})", "cyan")
    t_input = input("> ").strip()
    final_title_base = t_input if t_input else title_auto
    
    # Description from commits
    commits = []
    if targets:
         commits = get_commits_between(targets[0], source_branch)
    
    desc_auto = "\n".join([f"- {c}" for c in commits]) if commits else "No description provided."
    
    print_colored("\nDescription (Enter to keep auto-generated)", "cyan")
    if desc_auto:
        print(f"Current: \n{desc_auto}")
    d_lines = get_multiline_input("New description?")
    if d_lines:
        final_description = "\n".join([f"- {line}" for line in d_lines])
    else:
        final_description = desc_auto

    # Reviewers
    authors = get_authors()
    reviewers = prompt_reviewers(authors)

    # --- 3. Execution Loop for Targets ---
    
    for target in targets:
        print_colored(f"\n--- Preparing PR for {target} ---", "cyan")
        
        # Check existing
        if check_existing_pr(source_branch, target):
            continue
        
        # Construct Title
        if final_title_base:
            final_title = f"[{final_title_base}][{source_branch}] -> [{target}]"
        else:
            final_title = f"[{source_branch}] -> [{target}]"
        
        # Template
        pr_template = """**JIRA Ticket/Release:**
{tickets}

<br>**Description:**
{description}

<br>**Checklist:**

Refer to the checklist [here](https://qualitytrade.atlassian.net/wiki/spaces/BDT/pages/2708307969/Pull+request+guidelines)

- [ ] Checklist covered"""
    
        body = pr_template.format(tickets=jira_section, description=final_description)

        create_pr(source_branch, target, final_title, body, reviewers)

if __name__ == "__main__":
    main()
