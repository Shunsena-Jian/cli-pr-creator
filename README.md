# Qualitytrade Command Line Pull Request Creator

A smart command-line interface tool to streamline and automate the creation of GitHub Pull Requests. It helps ensure correct branching strategies, auto-generates titles and descriptions from JIRA tickets and git history, and facilitates reviewer selection.

## Features

- **Branching Strategy Support**: Built-in logic for standard Git flow strategies:
  - **Release Strategy**: Handles flow from Feature -> Develop/Staging -> Alpha -> Beta -> Live.
  - **Hotfix Strategy**: Handles flow from Child Hotfix -> Parent Hotfix -> All Environments.
  - **Manual Mode**: Flexible selection for ad-hoc PRs.
- **Smart Context Detection**:
  - Automatically parses **multiple JIRA ticket IDs** from branch names (e.g., `feature/PROJ-123-PROJ-456-update`).
  - Supports pasting **JIRA Ticket IDs or full URLs** manually.
  - Defaults source branch to current branch.
  - Validates source and target branch naming conventions for specific stages.
- **Auto-Documentation**:
  - Generates PR titles in the format: `[jira ticket id 1][jira ticket id 2][source branch] -> [target branch]`.
  - Populates PR descriptions with commit messages between source and target (defaults to **blank** if no new commits are found).
  - Formats JIRA links automatically as clickable labels in the PR body.
- **Interactive CLI**:
  - Fuzzy search and autocomplete for branch selection.
  - Autocomplete for choosing reviewers from git history.
  - Multi-line input support for descriptions.
- **Configurable**: Customize default targets, JIRA URLs, and more via a JSON config file.

## Prerequisites

- **Python 3.6+** (Standard library only, no pip dependencies required).
- **[GitHub CLI (`gh`)](https://cli.github.com/)**: Must be installed and authenticated (`gh auth login`).
- **Git**: Must be installed and available in the system path.

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/cli-pr-creator.git
   cd cli-pr-creator
   ```

2. Make the script executable:

   ```bash
   chmod +x cli_pr_creator.py
   ```

3. (Optional) Create an alias for easy access. Add this to your shell profile (e.g., `.bashrc` or `.zshrc`):
   ```bash
   alias create-pr="/path/to/cli-pr-creator/cli_pr_creator.py"
   ```

## Usage

Navigate to any git repository where you want to create a PR and run the script:

```bash
/path/to/cli_pr_creator.py
# or if you created an alias:
create-pr
```

### Interactive Workflow

1. **Strategy Selection**: Choose between Release, Hotfix, or Manual flow.
2. **Target Resolution**: The tool determines the appropriate target branch (e.g., if you are on a `release/x.y.z` branch, it may suggest `release/x.y.z-a`).
3. **JIRA Details**:
   - Tickets are auto-detected from the branch name (supports multiple IDs).
   - You can manually enter additional ticket IDs or **paste full JIRA URLs**.
4. **Metadata Review**:
   - **Title**: Shows a preview of the clean `[IDs][Source] -> [Target]` pattern. You can optionally add a descriptive title suffix.
   - **Description**: Review auto-generated commits or enter a custom description. Defaults to blank if no commits are found.
5. **Reviewers**: Interactively select reviewers from a list of authors found in the git log.
6. **Execution**: The tool constructs and previews the `gh pr create` command before running it.

## Configuration

You can configure the tool using a `.pr_creator_config.json` file. The tool searches for this file in:

1. The current working directory.
2. Your home directory (`~/`).

### Configuration Options

| Key                     | Default                                        | Description                                  |
| :---------------------- | :--------------------------------------------- | :------------------------------------------- |
| `default_target_branch` | `"main"`                                       | The fallback target branch name.             |
| `jira_base_url`         | `"https://qualitytrade.atlassian.net/browse/"` | Base URL for JIRA tickets.                   |
| `reviewer_groups`       | `{}`                                           | (Future) Predefined groups of reviewers.     |
| `jira_project_keys`     | `[]`                                           | (Future) List of expected JIRA project keys. |

**Example `.pr_creator_config.json`:**

```json
{
  "default_target_branch": "master",
  "jira_base_url": "https://mycompany.atlassian.net/browse/"
}
```

## Project Structure

- `cli_pr_creator.py`: Entry point wrapper script.
- `pr_creator/`: Main package source.
  - `main.py`: Core logic and orchestration.
  - `config.py`: Configuration loader.
  - `git.py`: Git command wrappers.
  - `github.py`: GitHub interaction logic.
  - `ui.py`: CLI prompting and autocomplete utilities.
  - `utils.py`: Helper functions.

## Troubleshooting

- **"gh CLI not found"**: Ensure `gh` is installed and in your PATH.
- **"Not a git repository"**: You must run the tool from within a git directory.
- **"Command failed with exit code X"**: The `gh` command failed. Check if you have local changes pushed to the remote source branch, as `gh` requires the branch to exist on the remote.
