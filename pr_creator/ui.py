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
    Clears the menu after selection for a clean UI.
    """
    if not choices:
        return ""

    print_colored(f"\n{prompt}", "cyan")
    
    # Display list (limited to 20)
    limit = 20
    lines_printed = 1 # for the prompt
    
    for idx, choice in enumerate(choices):
        if idx >= limit:
            print(f"... and {len(choices) - limit} more.")
            lines_printed += 1
            break
        print(f"[{idx+1}] {choice}")
        lines_printed += 1
    
    completer = SimpleCompleter(choices)
    setup_readline(completer.complete)
    print_colored("(Tip: Type part of the name and hit TAB to autocomplete)", "bold")
    print_colored("Select number or type name:", "cyan")
    lines_printed += 2
    
    try:
        while True:
            user_input = input("> ").strip()
            # input line itself is one line
            current_input_lines = 1 
            
            if not user_input:
                # Clear empty input attempt
                sys.stdout.write("\033[F\033[K")
                continue
            
            # Resolve selection
            match = None
            if user_input.isdigit():
                idx = int(user_input) - 1
                if 0 <= idx < len(choices):
                    match = choices[idx]
            
            if not match:
                matches = [c for c in choices if c == user_input or user_input.lower() in c.lower()]
                if len(matches) == 1:
                    match = matches[0]
                elif len(matches) > 1:
                    exact = [c for c in matches if c.lower() == user_input.lower()]
                    match = exact[0] if len(exact) == 1 else None
                    if not match:
                        print_colored(f"Ambiguous match: {', '.join(matches[:5])}...", "yellow")
                        current_input_lines += 1
            
            if match:
                # 1. Clear everything printed by this function
                # Go up total lines + current input lines
                total_to_clear = lines_printed + current_input_lines
                for _ in range(total_to_clear):
                    sys.stdout.write("\033[F\033[K")
                
                # 2. Print a single clean line with the result
                print_colored(f"{prompt} Selected: {match}", "green")
                return match
            else:
                # Clear invalid input and current_input_lines (if any error msgs were printed)
                for _ in range(current_input_lines):
                    sys.stdout.write("\033[F\033[K")
                print_colored("Invalid selection. Try again.", "red")
                # Error message adds a line, so next iteration input will be one line below it.
                # Actually, the error message itself will be cleared in next loop or after valid selection.
                # To keep it simple, let's just use the existing logic for errors but fix it.
                pass
    finally:
        readline.set_completer(None)

def get_multiline_input(prompt: str, instructions: str = "(Enter multiple lines, press Enter on empty line to finish)") -> list[str]:
    """Helper for collecting multi-line input with cleanup."""
    print_colored(f"\n{prompt}", "cyan")
    print_colored(f"  {instructions}", "bold")
    lines = []
    while True:
        line = input("> ").strip()
        if not line:
            break
        lines.append(line)
    
    # Clean up the input lines to keep it focused
    # +2 for prompt lines, +len(lines) for inputs, +1 for the last empty input
    total_to_clear = 2 + len(lines) + 1
    for _ in range(total_to_clear):
        sys.stdout.write("\033[F\033[K")
        
    if lines:
        print_colored(f"{prompt} ({len(lines)} lines entered)", "green")
    else:
        print_colored(f"{prompt} (None)", "yellow")
        
    return lines

def prompt_reviewers(authors: list[str]) -> list[str]:
    """Interactive loop to select reviewers with screen cleanup."""
    selected_reviewers = []
    
    if not authors:
        print_colored("\nWho are the reviewers? (No authors found in history)", "cyan")
    else:
        print_colored(f"\nWho are the reviewers? ({len(authors)} candidates found)", "cyan")

    lines_to_clear = 0
    
    try:
        # Autocomplete loop setup
        if 'libedit' in readline.__doc__:
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
        
        print_colored("(Tip: Type part of name and hit TAB. 'done' to finish, 'list' to show candidates)", "bold")
        
        while True:
            # Clear previous "status" lines if any
            for _ in range(lines_to_clear):
                sys.stdout.write("\033[F\033[K")
            
            status_lines = []
            if selected_reviewers:
                status_lines.append(f"Current reviewers: {', '.join(selected_reviewers)}")
            
            for line in status_lines:
                print_colored(line, "green")
            
            available_authors = [a for a in authors if a not in selected_reviewers]
            completer = SimpleCompleter(available_authors + ['done', 'list'])
            readline.set_completer(completer.complete)

            user_input = input("Select reviewer > ").strip()
            
            # We will clear the input line + the status lines in the next loop
            lines_to_clear = len(status_lines) + 1 
            
            if not user_input or user_input.lower() in ('d', 'done'):
                break
                
            if user_input.lower() in ('l', 'list'):
                # Display list temporarily
                print_colored("Candidates:", "cyan")
                temp_lines = 1
                for idx, a in enumerate(available_authors):
                    if idx >= 15: 
                        print(f"... {len(available_authors)-15} more")
                        temp_lines += 1
                        break
                    print(f"[{idx+1}] {a}")
                    temp_lines += 1
                
                input("Press Enter to continue...")
                # Clear the list we just printed
                for _ in range(temp_lines + 1):
                    sys.stdout.write("\033[F\033[K")
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
            
            if matched:
                selected_reviewers.append(matched)
            else:
                if not user_input.isdigit():
                    print_colored(f"No match for '{user_input}'", "red")
                    lines_to_clear += 1
                    
    finally:
        readline.set_completer(None)
        
    return selected_reviewers
