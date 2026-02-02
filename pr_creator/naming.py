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
