import readline
import sys
from .utils import print_colored

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

def setup_readline(completer_func):
    """Configure readline for autocomplete."""
    readline.set_completer(completer_func)
    if 'libedit' in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")
        readline.parse_and_bind("set show-all-if-ambiguous on")
        readline.parse_and_bind("set completion-ignore-case on")

def select_from_list(prompt: str, choices: list[str]) -> str:
    """
    Presents a numbered list of choices to the user.
    Supports fuzzy matching and tab-completion.
    """
    print_colored(f"\n{prompt}", "cyan")
    if not choices:
        return ""
    
    # Display list (limited to 20)
    limit = 20
    for idx, choice in enumerate(choices):
        if idx >= limit:
            print(f"... and {len(choices) - limit} more.")
            break
        print(f"[{idx+1}] {choice}")
    
    completer = SimpleCompleter(choices)
    setup_readline(completer.complete)
    print_colored("(Tip: Type part of the name and hit TAB to autocomplete)", "bold")
    print_colored("Select number or type name:", "cyan")
    
    try:
        while True:
            # Short prompt to avoid clutter on tab-completion
            user_input = input("> ").strip()
            if not user_input:
                continue
            
            # 1. Number selection
            if user_input.isdigit():
                idx = int(user_input) - 1
                if 0 <= idx < len(choices):
                    return choices[idx]
            
            # 2. Exact match
            matches = [c for c in choices if c == user_input]
            if len(matches) == 1:
                return matches[0]
                
            # 3. Fuzzy match
            matches = [c for c in choices if user_input.lower() in c.lower()]
            if len(matches) == 1:
                return matches[0]
            elif len(matches) > 1:
                print_colored(f"Ambiguous match: {', '.join(matches[:5])}...", "yellow")
            else:
                 # Clear previous line (input) and print error
                 sys.stdout.write("\033[F\033[K")
                 print_colored("Invalid selection. Try again.", "red")
                 continue
    finally:
        readline.set_completer(None)

def get_multiline_input(prompt: str, instructions: str = "(Enter multiple lines, press Enter on empty line to finish)") -> list[str]:
    """Helper for collecting multi-line input."""
    print_colored(f"\n{prompt} {instructions}", "cyan")
    lines = []
    while True:
        line = input("> ").strip()
        if not line:
            break
        lines.append(line)
    return lines

def prompt_reviewers(authors: list[str]) -> list[str]:
    """Interactive loop to select reviewers."""
    selected_reviewers = []
    print_colored("\nWho are the reviewers?", "cyan")
    
    if not authors:
        print_colored("Could not find authors in git log.", "yellow")
    else:
        print_colored(f"Found {len(authors)} authors in history.", "green")

    # Autocomplete loop
    try:
        # Initial readline setup
        if 'libedit' in readline.__doc__:
             readline.parse_and_bind("bind ^I rl_complete")
        else:
             readline.parse_and_bind("tab: complete")
             readline.parse_and_bind("set show-all-if-ambiguous on")
             readline.parse_and_bind("set completion-ignore-case on")

        print_colored("(Tip: Type part of the name and hit TAB to autocomplete)", "bold")
        print_colored("Type reviewer name/number to add (Press Enter to finish):", "cyan")
        
        while True:
            available_authors = [a for a in authors if a not in selected_reviewers]
            completer = SimpleCompleter(available_authors + ['done', 'list'])
            readline.set_completer(completer.complete)

            if selected_reviewers:
                print_colored(f"Current reviewers: {', '.join(selected_reviewers)}", "green")
            
            # Short prompt
            user_input = input("> ").strip()
            
            if not user_input or user_input.lower() in ('d', 'done'):
                break
                
            if user_input.lower() in ('l', 'list'):
                for idx, a in enumerate(available_authors):
                    if idx >= 20: 
                        print(f"... {len(available_authors)-20} more")
                        break
                    print(f"[{idx+1}] {a}")
                continue
            
            # Resolve input
            matched = None
            if user_input.isdigit():
                idx = int(user_input) - 1
                if 0 <= idx < len(available_authors):
                    matched = available_authors[idx]
            
            if not matched:
                matches = [a for a in available_authors if user_input.lower() in a.lower()]
                if len(matches) == 1:
                    matched = matches[0]
                elif len(matches) > 1:
                    exact = [a for a in matches if a.lower() == user_input.lower()]
                    matched = exact[0] if len(exact) == 1 else None
                    if not matched:
                        print_colored(f"Multiple matches: {', '.join(matches[:5])}...", "yellow")
                        continue
            
            if matched:
                selected_reviewers.append(matched)
                print_colored(f"Added {matched}", "green")
            else:
                 if not user_input.isdigit():
                    # Cleanup and error
                    sys.stdout.write("\033[F\033[K")
                    print_colored("No match found.", "red")
                    
    finally:
        readline.set_completer(None)
        
    return selected_reviewers
