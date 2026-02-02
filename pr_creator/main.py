import sys
import shutil
import subprocess
from .utils import print_colored, run_cmd
from .git import is_git_repo, fetch_latest_branches, get_remote_branches, get_authors, get_current_branch, get_commits_between
from .github import check_existing_pr, resolve_handle
from .ui import select_from_list, get_multiline_input, prompt_reviewers
from .config import load_config
import re

def parse_branch_name(branch: str):
    """
    Extract JIRA ticket and a readable title from branch name.
    e.g. feature/PROJ-123-some-fix -> ('PROJ-123', 'Some Fix')
    """
    # Remove prefix like feature/, bugfix/
    if "/" in branch:
        parts = branch.split("/", 1)
        name_part = parts[1]
    else:
        name_part = branch

    # Try to find ticket like KEY-123
    ticket = ""
    ticket_match = re.search(r'([A-Z]+-\d+)', name_part, re.IGNORECASE)
    if ticket_match:
        ticket = ticket_match.group(1).upper()
        # Remove ticket from name for the title
        name_part = name_part.replace(ticket_match.group(0), "").strip(" -_")

    # Clean up title: replace separators with spaces and title case
    title = re.sub(r'[-_]', ' ', name_part).strip().title()
    
    return ticket, title

def prompt_strategy(current_branch: str, remote_branches: list[str]) -> tuple[str, str, list[str]]:
    """
    Ask user for strategy and Determine targets.
    Returns: (strategy_name, source_branch, list_of_target_branches)
    """
    strategies = [
        "Release Strategy",
        "Hotfix Strategy",
        "Manually Create Pull Request"
    ]
    
    print_colored("\nWhat's the current branching rules?", "cyan")
    choice = select_from_list("Select Strategy:", strategies)
    
    source = current_branch
    
    if choice == "Release Strategy":
        stages = [
            "feature or bugfix branch -> develop & staging",
            "staging -> alpha",
            "alpha -> beta",
            "beta -> live (main/master)"
        ]
        stage = select_from_list("What stage are you now?", stages)
        
        if "feature or bugfix" in stage:
            return "Release: Feature", source, ["develop", "staging_placeholder"] 
            
        elif "staging -> alpha" in stage:
            # [Existing logic hidden]
            # Source must be release/0.0.0
            # Check if current matches
            is_valid_staging = (
                source.startswith("release/") and 
                not source.endswith("-a") and 
                not source.endswith("-b")
            )
            
            if not is_valid_staging:
                print_colored("Current branch is not a valid Staging branch (release/x.y.z).", "yellow")
                # Find valid candidates
                candidates = [b for b in remote_branches if "release/" in b and not b.endswith("-a") and not b.endswith("-b")]
                if candidates:
                    source = select_from_list("Select Source Staging Branch:", candidates)
                else:
                    print_colored("No Staging branches found remotely. Continuing with current...", "red")
            
            target = f"{source}-a"
            return "Release: Staging->Alpha", source, [target]

        elif "alpha -> beta" in stage:
            # [Existing logic hidden]
            # Source must be release/0.0.0-a
            is_valid_alpha = source.startswith("release/") and source.endswith("-a")
            
            if not is_valid_alpha:
                print_colored("Current branch is not a valid Alpha branch (release/x.y.z-a).", "yellow")
                candidates = [b for b in remote_branches if b.startswith("release/") and b.endswith("-a")]
                if candidates:
                    source = select_from_list("Select Source Alpha Branch:", candidates)
                else:
                    print_colored("No Alpha branches found remotely. Continuing with current...", "red")

            target = source.replace("-a", "-b")
            return "Release: Alpha->Beta", source, [target]

        elif "beta -> live" in stage:
            # Source must be release/0.0.0-b
            is_valid_beta = source.startswith("release/") and source.endswith("-b")
            
            if not is_valid_beta:
                 print_colored("Current branch is not a valid Beta branch (release/x.y.z-b).", "yellow")
                 candidates = [b for b in remote_branches if b.startswith("release/") and b.endswith("-b")]
                 if candidates:
                     source = select_from_list("Select Source Beta Branch:", candidates)
                 else:
                     print_colored("No Beta branches found remotely. Continuing with current...", "red")
            
            # Determine main/master
            if "main" in remote_branches:
                target = "main"
            elif "master" in remote_branches:
                target = "master"
            else:
                 target = select_from_list("Select Live Branch:", remote_branches)
            
            return "Release: Beta->Live", source, [target]

    elif choice == "Hotfix Strategy":
        stages = [
            "Child Hotfix -> Parent Hotfix",
            "Parent Hotfix -> develop & staging",
            "Parent Hotfix -> alpha & beta"
        ]
        stage = select_from_list("What stage are you now?", stages)
        
        if "Child Hotfix" in stage:
            # Source should be child hotfix (hotfix/0.0.0-foo)
            # Target should be parent (hotfix/0.0.0)
            if "-" in source:
                parent_guess = source.split("-", 1)[0]
                if parent_guess in remote_branches:
                     return "Hotfix: Child", source, [parent_guess]
            
            return "Hotfix: Child", source, ["parent_placeholder"]
            
        elif "Parent Hotfix -> develop" in stage:
             # Source check: hotfix/0.0.0 (no extra dash usually, but lenient)
             return "Hotfix: Parent->Dev/Staging", source, ["develop", "staging_placeholder"]
             
        elif "Parent Hotfix -> alpha" in stage:
             return "Hotfix: Parent->Alpha/Beta", source, ["alpha_placeholder", "beta_placeholder"]

    return "Manual", source, []

def resolve_placeholder_targets(targets: list[str], remote_branches: list[str]) -> list[str]:
    """
    Replace placeholders like 'staging_placeholder' with actual branches selected by user.
    """
    resolved = []
    
    # Filter for release branches
    release_branches = [b for b in remote_branches if "release/" in b and not b.endswith("-a") and not b.endswith("-b")]
    alpha_branches = [b for b in remote_branches if b.endswith("-a")]
    beta_branches = [b for b in remote_branches if b.endswith("-b")]
    hotfix_branches = [b for b in remote_branches if "hotfix/" in b]
    
    for t in targets:
        if t == "staging_placeholder":
            if not release_branches:
                print_colored("No staging branches (release/x.y.z) found.", "yellow")
                # Fallback to manual? or skip?
                # Let's ask user to pick or skip
                sel = select_from_list("Select Staging Branch (or 'skip'):", release_branches + ['skip'])
                if sel != 'skip':
                    resolved.append(sel)
            elif len(release_branches) == 1:
                resolved.append(release_branches[0])
            else:
                sel = select_from_list("Select Staging Branch:", release_branches)
                resolved.append(sel)
        
        elif t == "alpha_placeholder":
             if not alpha_branches:
                 print_colored("No Alpha branches found.", "yellow")
                 sel = select_from_list("Select Alpha Branch (or 'skip'):", alpha_branches + ['skip'])
                 if sel != 'skip': resolved.append(sel)
             else:
                 sel = select_from_list("Select Alpha Branch:", alpha_branches)
                 resolved.append(sel)
                 
        elif t == "beta_placeholder":
             if not beta_branches:
                 print_colored("No Beta branches found.", "yellow")
                 sel = select_from_list("Select Beta Branch (or 'skip'):", beta_branches + ['skip'])
                 if sel != 'skip': resolved.append(sel)
             else:
                 sel = select_from_list("Select Beta Branch:", beta_branches)
                 resolved.append(sel)
        elif t == "parent_placeholder":
             # Show all remote branches? Or just hotfixes?
             all_opts = hotfix_branches if hotfix_branches else remote_branches
             sel = select_from_list("Select Parent Branch:", all_opts)
             resolved.append(sel)
        else:
            resolved.append(t)
            
    return resolved

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
    
    # Check if current branch exists remotely. If not, push might be needed, but we assume user handles that or we just use local name.
    # Actually GH CLI requires pushed branch usually.
    
    source_branch = current_branch
    
    print(f"Current Branch (Source): {source_branch}")
    
    strategy_name, source_branch, target_candidates = prompt_strategy(source_branch, remote_branches)
    
    targets = []
    if strategy_name == "Manual":
        # Fallback to standard flow
        target_candidates = [] # Logic handled below in manual loop
    else:
        # Resolve placeholders
        targets = resolve_placeholder_targets(target_candidates, remote_branches)
    
    # If manual, we ask for target
    if strategy_name == "Manual" or not targets:
        if strategy_name != "Manual":
            print_colored("No valid targets determined from strategy. Reverting to manual selection.", "yellow")
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
        links = [f"{t} - {config.get('jira_base_url', '')}{t}" if 'http' not in t else t for t in ids] # Simple local format for now, or use util
        # Better: use the util we made? We need to import it properly or inline logic.
        from .utils import normalize_jira_link
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
    # Note: Description might differ per target if we strictly diff, but usually for multi-target PRs (backports etc) the description is same.
    # We'll generate a default description based on the FIRST target or just generic commits.
    # Let's just use commits against the first target to populate.
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
        check_existing_pr(source_branch, target)
        
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

        cmd = [
            "gh", "pr", "create",
            "--base", target,
            "--head", source_branch,
            "--title", final_title,
            "--body", body
        ]
        
        if reviewers:
             for r in reviewers:
                handle = resolve_handle(r)
                cmd.extend(["--reviewer", handle])

        print_colored("Generated Command:", "cyan")
        print(f"gh pr create --base {target} --head {source_branch} --title \"{final_title}\" ...")
        
        if shutil.which("gh"):
            user_conf = input(f"Create PR to {target}? [Y/n] ").strip().lower()
            if user_conf != 'n':
                try:
                    run_cmd(cmd)
                except subprocess.CalledProcessError as e:
                    print_colored(f"Command failed with exit code {e.returncode}", "red")
        else:
             print_colored("gh CLI not found.", "yellow")



