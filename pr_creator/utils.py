import subprocess

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

def run_cmd(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a subprocess command safely."""
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)

def normalize_jira_link(ticket_id: str, base_url: str) -> str:
    """Convert ticket ID (PROJ-123) to a markdown link if not already a URL."""
    ticket_id = ticket_id.strip()
    if not ticket_id:
        return ""
    if ticket_id.startswith("http"):
        return ticket_id
    # Ensure base_url ends with slash
    if not base_url.endswith("/"):
        base_url += "/"
    return f"[{ticket_id}]({base_url}{ticket_id})"
