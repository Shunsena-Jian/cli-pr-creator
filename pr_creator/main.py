import sys
from .utils import print_colored, run_cmd, normalize_jira_link, extract_jira_id
from .git import is_git_repo, fetch_latest_branches, get_remote_branches, get_current_branch, get_commits_between, get_current_user_email
from .github import check_existing_pr, create_pr, get_contributors, get_current_username
from .ui import select_from_list, get_multiline_input, prompt_reviewers
from .config import load_config
from .naming import parse_branch_name
from .strategy import prompt_strategy, resolve_placeholder_targets
from .templates import PR_TEMPLATE

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
    
    tickets_auto, title_auto = parse_branch_name(source_branch)
    
    # JIRA Flow
    print_colored("\n--- JIRA Details ---", "cyan")
    print("1. Enter JIRA Ticket IDs")
    print("2. Enter JIRA Release info")
    print("3. Skip / Manual")
    j_choice = input("Select [1-3]: ").strip()
    
    jira_section = ""
    ticket_ids = tickets_auto[:]

    if j_choice == "1":
        ids_input = get_multiline_input("Enter JIRA Ticket IDs or URLs (e.g. PROJ-123):")
        new_ids = []
        links = []
        for t in ids_input:
            if not t.strip(): continue
            tid = extract_jira_id(t)
            new_ids.append(tid)
            links.append(normalize_jira_link(t, jira_base_url))
        
        jira_section = "\n".join(links)
        # Add new IDs to our list, avoiding duplicates
        for tid in new_ids:
            if tid not in ticket_ids:
                ticket_ids.append(tid)
            
    elif j_choice == "2":
        r_title = input("Release Title: ").strip()
        r_url = input("Release URL: ").strip()
        jira_section = f"[{r_title}]({r_url})"
        if not title_auto:
            title_auto = r_title
            
    else:
        jira_section = "None"
        title_auto = ""

    # Construct the ticket prefix for the title: [ID1][ID2]...
    ticket_prefix = "".join([f"[{tid}]" for tid in ticket_ids])

    # Title Preview and Input
    preview_target = targets[0] if targets else "target"
    default_full = f"{ticket_prefix}[{source_branch}] -> [{preview_target}]"
    
    print_colored("\n--- Title Configuration ---", "cyan")
    print_colored(f"Default Title Style: {default_full}", "green")
    if len(targets) > 1:
        print_colored(f"(Will be applied to {len(targets)} targets)", "green")

    print_colored(f"\nDescriptive Title / Extension (Default: {title_auto if not ticket_ids else 'None'})", "cyan")
    print_colored("(Press Enter to keep the default pattern above, or type to add a descriptive title)", "bold")
    t_input = input("> ").strip()
    
    # If tickets exist, default is empty (no extra title). If no tickets, default is title_auto.
    final_title_base = t_input if t_input else (title_auto if not ticket_ids else "")
    
    # Description from commits
    commits = []
    if targets:
         commits = get_commits_between(targets[0], source_branch)
    
    desc_auto = "\n".join([f"- {c}" for c in commits]) if commits else ""
    
    print_colored("\nDescription (Enter to keep auto-generated)", "cyan")
    if desc_auto:
        print(f"Current: \n{desc_auto}")
    else:
        print("(No commits found - description will be blank by default)")

    d_lines = get_multiline_input("New description?")
    if d_lines:
        final_description = "\n".join([f"- {line}" for line in d_lines])
    else:
        final_description = desc_auto

    # Reviewers
    authors = get_contributors()
    
    current_email = get_current_user_email()
    current_handle = get_current_username()
    ignored_authors = config.get("ignored_authors", [])
    
    # Filter out current user and ignored authors
    filtered_authors = []
    for a in authors:
        # Check current email (if author string contains it)
        if current_email and current_email in a:
            continue
        # Check current handle (exact match)
        if current_handle and current_handle.lower() == a.lower():
            continue
        # Check ignored list (partial match)
        is_ignored = False
        for ignored in ignored_authors:
            if ignored in a:
                is_ignored = True
                break
        if is_ignored:
            continue
            
        filtered_authors.append(a)
    
    reviewers = prompt_reviewers(filtered_authors)

    # --- 3. Execution Loop for Targets ---
    
    for target in targets:
        print_colored(f"\n--- Preparing PR for {target} ---", "cyan")
        
        # Check existing
        if check_existing_pr(source_branch, target):
            continue
        
        # Construct Title: [ID1][ID2][Title][source] -> [target]
        # or if no title: [ID1][ID2][source] -> [target]
        title_part = f"[{final_title_base}]" if final_title_base else ""
        final_title = f"{ticket_prefix}{title_part}[{source_branch}] -> [{target}]"
        
        # Template
        body = PR_TEMPLATE.format(tickets=jira_section, description=final_description)
        create_pr(source_branch, target, final_title, body, reviewers)

if __name__ == "__main__":
    main()
