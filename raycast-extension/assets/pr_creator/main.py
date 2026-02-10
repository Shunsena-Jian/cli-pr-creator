import sys
import argparse
import json
from .utils import print_colored, normalize_jira_link, extract_jira_id, clear_screen
from .git import is_git_repo, fetch_latest_branches, get_remote_branches, get_current_branch, get_commits_between, get_current_user_email
from .github import check_existing_pr, create_pr, get_contributors, get_current_username
from .ui import select_from_list, get_multiline_input, prompt_reviewers
from .config import load_config
from .naming import parse_branch_name
from .strategy import prompt_strategy, resolve_placeholder_targets
from .templates import PR_TEMPLATE

def print_header(source=None, targets=None, strategy=None, tickets=None, title=None, description=None, reviewers=None):
    clear_screen()
    print_colored("QualityTrade Asia Pull Request Creator", "green")
    print_colored("="*40, "green")
    
    if source:
        print(f"Source   : {source}")
    if targets:
        print(f"Targets  : {', '.join(targets)}")
    if strategy:
        print(f"Strategy : {strategy}")
    if tickets:
        print(f"Tickets  : {', '.join(tickets)}")
    if title is not None:
        print(f"Title    : {title}")
    if description:
        # Show summary of description
        lines = description.strip().split("\n")
        desc_sum = lines[0][:50] + ("..." if len(lines) > 1 or len(lines[0]) > 50 else "")
        print(f"Desc     : {desc_sum}")
    if reviewers:
        # Show count or first few if many
        rev_str = ", ".join(reviewers)
        if len(rev_str) > 50:
             rev_str = f"{len(reviewers)} selected"
        print(f"Reviewers: {rev_str}")
        
    if any([source, targets, strategy, tickets, title, description, reviewers]):
        print_colored("-" * 40, "green")

def run_interactive():
    print_header()

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

    # Redraw with context
    print_header(source_branch, targets, strategy_name)

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

    # Refresh header with JIRA info
    print_header(source_branch, targets, strategy_name, tickets=ticket_ids)

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
    
    # Refresh header with Title
    print_header(source_branch, targets, strategy_name, tickets=ticket_ids, title=final_title_base)
    
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

    # Redraw before reviewers
    print_header(
        source_branch, targets, strategy_name, 
        tickets=ticket_ids, 
        title=final_title_base, 
        description=final_description
    )

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

    # --- 3. Compilation & Batch Execution ---
    
    all_prs = []
    for target in targets:
        title_part = f"[{final_title_base}]" if final_title_base else ""
        final_title = f"{ticket_prefix}{title_part}[{source_branch}] -> [{target}]"
        body = PR_TEMPLATE.format(tickets=jira_section, description=final_description)
        
        all_prs.append({
            "target": target,
            "title": final_title,
            "body": body,
            "reviewers": reviewers
        })

    # Final Redraw with full context
    print_header(
        source=source_branch, 
        targets=targets, 
        strategy=strategy_name, 
        tickets=ticket_ids, 
        title=final_title_base, 
        description=final_description, 
        reviewers=reviewers
    )

    print_colored(f"\nReady to create {len(all_prs)} Pull Request(s):", "cyan")
    for pr in all_prs:
        print(f"  -> {pr['target']}: {pr['title']}")
    
    confirm = input("\nCreate these PRs? [Y/n] ").strip().lower()
    if confirm == 'n':
        print_colored("Aborted.", "red")
        sys.exit(0)

    # Execution
    created_urls = []
    for pr in all_prs:
        print_colored(f"\n--- Processing {pr['target']} ---", "cyan")
        
        # Check existing
        if check_existing_pr(source_branch, pr['target']):
            continue
            
        url = create_pr(source_branch, pr['target'], pr['title'], pr['body'], pr['reviewers'], skip_confirm=True)
        if url:
            created_urls.append((pr['target'], url))

    # Final summary display
    if created_urls:
        print_header(
            source=source_branch, 
            targets=targets, 
            strategy=strategy_name, 
            tickets=ticket_ids, 
            title=final_title_base, 
            description=final_description, 
            reviewers=reviewers
        )
        print_colored("\n" + "="*50, "green")
        print_colored("ALL PULL REQUESTS COMPLETED!", "green")
        for target, url in created_urls:
            print_colored(f"  {target.ljust(15)}: {url}", "bold")
        print_colored("="*50 + "\n", "green")
    else:
        print_colored("\nNo PRs were created.", "yellow")

def output_git_data():
    """Output git/github metadata in JSON for Raycast."""
    if not is_git_repo():
        print(json.dumps({"error": "Not a git repository"}))
        return

    # fetch_latest_branches()
    current_branch = get_current_branch()
    remote_branches = get_remote_branches()
    contributors = get_contributors()
    tickets_auto, title_auto = parse_branch_name(current_branch)
    
    data = {
        "currentBranch": current_branch,
        "remoteBranches": remote_branches,
        "contributors": contributors,
        "suggestedTickets": tickets_auto,
        "suggestedTitle": title_auto
    }
    print(json.dumps(data))

def output_description(source, target):
    """Output commit-based description in JSON for Raycast."""
    commits = get_commits_between(target, source)
    description = "\n".join([f"- {c}" for c in commits])
    print(json.dumps({"description": description}))

def run_headless(args):
    """Execute PR creation without interaction."""
    source = args.source or get_current_branch()
    targets = args.target or []
    title_base = args.title or ""
    description = args.body or ""
    reviewers = args.reviewers or []
    tickets = args.tickets or []
    
    if not targets:
        print(json.dumps({"error": "No target branches specified"}))
        return

    config = load_config()
    jira_base_url = config.get("jira_base_url", "https://qualitytrade.atlassian.net/browse/")
    
    # Construct JIRA section
    jira_links = []
    for t in tickets:
        jira_links.append(normalize_jira_link(t, jira_base_url))
    jira_section = "\n".join(jira_links) if jira_links else "None"
    
    ticket_prefix = "".join([f"[{tid}]" for tid in tickets])
    
    results = []
    for target in targets:
        title_part = f"[{title_base}]" if title_base else ""
        final_title = f"{ticket_prefix}{title_part}[{source}] -> [{target}]"
        body = PR_TEMPLATE.format(tickets=jira_section, description=description)
        
        # Check existing
        if check_existing_pr(source, target):
            results.append({"target": target, "skipped": True, "reason": "PR already exists"})
            continue
            
        url = create_pr(source, target, final_title, body, reviewers, skip_confirm=True)
        results.append({"target": target, "url": url})
    
    print(json.dumps({"success": True, "results": results}))

def output_preview(args):
    """Output PR preview based on inputs."""
    source = args.source or get_current_branch()
    target = args.target[0] if args.target else "main"
    title_base = args.title or ""
    description_base = args.body or ""
    tickets = args.tickets or []
    
    config = load_config()
    jira_base_url = config.get("jira_base_url", "https://qualitytrade.atlassian.net/browse/")
    
    jira_links = []
    for t in tickets:
        jira_links.append(normalize_jira_link(t, jira_base_url))
    jira_section = "\n".join(jira_links) if jira_links else "None"
    
    ticket_prefix = "".join([f"[{tid}]" for tid in tickets])
    title_part = f"[{title_base}]" if title_base else ""
    final_title = f"{ticket_prefix}{title_part}[{source}] -> [{target}]"
    final_body = PR_TEMPLATE.format(tickets=jira_section, description=description_base)
    
    print(json.dumps({
        "title": final_title,
        "body": final_body
    }))

def main():
    parser = argparse.ArgumentParser(description="QualityTrade PR Creator")
    
    # Mode Flags
    parser.add_argument("--headless", action="store_true", help="Run without interaction")
    parser.add_argument("--get-data", action="store_true", help="Output JSON data for Raycast")
    parser.add_argument("--get-description", action="store_true", help="Output JSON description")
    parser.add_argument("--get-preview", action="store_true", help="Output PR preview")
    
    # Metadata Arguments
    parser.add_argument("--source", help="Source branch")
    parser.add_argument("--target", action="append", help="Target branch (can be repeated)")
    parser.add_argument("--title", help="Descriptive part of the PR title")
    parser.add_argument("--body", help="PR description body")
    parser.add_argument("--reviewers", action="append", help="Reviewer usernames (can be repeated)")
    parser.add_argument("--tickets", action="append", help="JIRA ticket IDs (can be repeated)")

    args = parser.parse_args()

    if args.get_data:
        output_git_data()
    elif args.get_description:
        if not args.target or not args.source:
             print(json.dumps({"error": "Source and Target required for description"}))
        else:
             output_description(args.source, args.target[0])
    elif args.get_preview:
        output_preview(args)
    elif args.headless:
        run_headless(args)
    else:
        run_interactive()

if __name__ == "__main__":
    main()
