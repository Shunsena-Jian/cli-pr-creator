import subprocess
import re
import sys

def clear_screen():
    """Clear the terminal screen."""
    print("\033[H\033[J", end="")

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
    print(f"{prefix}{text}{colors['reset']}", file=sys.stderr)

def run_cmd(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a subprocess command safely."""
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)

def extract_jira_id(input_str: str) -> str:
    """Extract JIRA ticket ID (e.g. PROJ-123) from a string or URL."""
    input_str = input_str.strip()
    # Check if it's a URL
    if input_str.startswith("http"):
        # Match something like /browse/PROJ-123 or just the end of URL
        match = re.search(r'([A-Z]+-\d+)', input_str, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    
    # If not a URL or no ID found in URL, check if it's just a ticket ID
    match = re.search(r'([A-Z]+-\d+)', input_str, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    
    return input_str

def normalize_jira_link(ticket_input: str, base_url: str) -> str:
    """Convert ticket ID or URL to a markdown link with ID as label."""
    ticket_id = extract_jira_id(ticket_input)
    
    # Ensure base_url ends with slash
    if not base_url.endswith("/"):
        base_url += "/"
        
    url = ticket_input if ticket_input.startswith("http") else f"{base_url}{ticket_id}"
    return f"[{ticket_id}]({url})"
