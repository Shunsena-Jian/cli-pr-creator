from .utils import print_colored
from .ui import select_from_list

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
            "Parent Hotfix -> All (Dev/Staging/Alpha/Beta/Live)"
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
            
        elif "Parent Hotfix -> All" in stage:
             # Source must be parent hotfix (hotfix/0.0.0) without extra dash suffix
             is_valid_parent = source.startswith("hotfix/") and "-" not in source.replace("hotfix/", "")
             
             if not is_valid_parent:
                  if "-" in source and source.startswith("hotfix/"):
                       # Try stripping suffix
                       parent_guess = source.split("-", 1)[0]
                       if parent_guess in remote_branches:
                            source = parent_guess
                            is_valid_parent = True
                  
                  if not is_valid_parent:
                       # Prompt from list
                       candidates = [b for b in remote_branches if b.startswith("hotfix/") and "-" not in b.replace("hotfix/", "")]
                       if candidates:
                            source = select_from_list("Select Parent Hotfix Branch:", candidates)
                       else:
                            print_colored("Warning: No clean parent hotfix branch found.", "yellow")
             
             return "Hotfix: Parent->All", source, ["develop", "staging_placeholder", "alpha_placeholder", "beta_placeholder", "default_placeholder"]

    return "Manual", source, []

def resolve_placeholder_targets(targets: list[str], remote_branches: list[str], default_target: str = "main") -> list[str]:
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
        elif t == "default_placeholder":
             resolved.append(default_target)
        else:
            resolved.append(t)
            
    return resolved
