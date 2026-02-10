import re

def parse_branch_name(branch: str):
    """
    Extract JIRA tickets and a readable title from branch name.
    e.g. feature/PROJ-123-PROJ-456-some-fix -> (['PROJ-123', 'PROJ-456'], 'Some Fix')
    """
    # Remove prefix like feature/, bugfix/
    if "/" in branch:
        parts = branch.split("/", 1)
        name_part = parts[1]
    else:
        name_part = branch

    # Find all tickets like KEY-123
    tickets = []
    ticket_matches = re.findall(r'([A-Z]+-\d+)', name_part, re.IGNORECASE)
    if ticket_matches:
        tickets = [t.upper() for t in ticket_matches]
        # Remove all tickets from name for the title
        for tm in ticket_matches:
            name_part = name_part.replace(tm, "")
        name_part = name_part.strip(" -_")

    # Clean up title: replace separators with spaces and title case
    title = re.sub(r'[-_]+', ' ', name_part).strip().title()
    
    return tickets, title
