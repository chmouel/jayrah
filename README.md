# 🌞 Jayrah - Jira from your terminal with fuzzy search and AI-powered command palette (MCP) 🌞

Jayrah is a CLI tool that makes working with Jira faster by adding fuzzy search
(via fzf) and AI-powered capabilities to your workflow (via
[MCP](https://modelcontextprotocol.io/introduction) protocol). It lets you
quickly find, create, and manage issues without leaving your terminal.

## Installation

Install it with uv:

```bash
uvx jayrah
```

Or build from source:

```bash
git clone https://github.com/chmouel/jayrah.git
cd jayrah
uv run jayrah
```

## What you'll need

* **uv** - Get it here: <https://docs.astral.sh/uv/getting-started/installation>
* **fzf** - Install through your system's package manager

## Setting it up

Jayrah looks for its config at `~/.config/jayrah/config.yaml`. Use
`--config-file` if you need a different location.

Here's a sample config:

```yaml
jira_server: "https://your-jira.atlassian.net"
jira_user: "you@example.com"
jira_password: "your-api-token"
jira_component: "your-team-component"

# Custom issue views
boards:
  myissues:
    jql: "assignee = currentUser() AND resolution = Unresolved ORDER BY updated DESC"
    order_by: "updated DESC"
  myinprogress:
    jql: "assignee = currentUser() AND status = 'In Progress' ORDER BY updated DESC"
    order_by: "updated DESC"
  mytodo:
    jql: "assignee = currentUser() AND status = 'To Do' ORDER BY updated DESC"
    order_by: "priority DESC"
```

You can also set these via environment variables:

* `JIRA_SERVER`
* `JIRA_USER`
* `JIRA_PASSWORD`
* `JIRA_COMPONENT`

## How to use it

### 🔍 Find issues

```bash
# Browse all issues in a board
jayrah browse [BOARD]

# Search for issues containing specific terms in summary or description 
jayrah browse [BOARD] term1 term2   # Searches for term1 AND term2
jayrah browse [BOARD] --or term1 term2   # Searches for term1 OR term2
```

Pick a board from your config file. Add search terms as arguments to filter issues by content. By default, multiple terms are combined with AND logic, but you can use the `--or` flag to combine them with OR logic.

### ✨ Make a new issue

```bash
jayrah create --type "Story" --summary "What needs doing" --description "Details here"
```

### 🛠️ Work with issues

```bash
# Open in browser
jayrah issue open TICKET-123

# See details
jayrah issue view TICKET-123 [--comments N]

# Change status, edit fields, etc.
jayrah issue action TICKET-123

# Update description
jayrah issue edit-description TICKET-123

# Move to a different status
jayrah issue transition TICKET-123
```

### 🔀 Create Git branches

```bash
# Create a git branch name from your assigned issues
jayrah git-branch

# Search your assigned issues for specific terms and create a branch
jayrah git-branch term1 term2      # Searches for term1 AND term2
jayrah git-branch --or term1 term2  # Searches for term1 OR term2
```

## Shell completion

### For ZSH

Either:

1. Copy [./misc/completion.zsh](./misc/completion.zsh) to your zsh fpath
2. Or add this to your `.zshrc`:

```shell
eval "$(_JAYRAH_COMPLETE=zsh_source jayrah)" 
```

### For Bash

Either:

1. Copy [./misc/completion.bash](./misc/completion.bash) to your bash completion dir
2. Or add this to your `.bashrc`:

```shell
eval "$(_JAYRAH_COMPLETE=bash_source jayrah)" 
```

## MCP Server for AI integration

Jayrah can run as an MCP server to work with AI tools like VS Code Copilot.

### Start the server

```bash
jayrah mcp
```

This runs in stdio mode by default for VS Code.

### Available actions

The server exposes these Jira operations:

* Browse issues (with pagination support)
  * `limit` - Control how many issues to display (default: 10)
  * `page` - Select which page of results to view (starts at 1)
  * `page_size` - Number of issues per page (default: 100)
* Create/view issues
* Change issue status
* Get possible status changes
* Open issues in browser
* List your boards

### VS Code setup

1. Clone the repo somewhere (e.g., `/path/to/jayrah`)
2. Make sure you have Copilot in VS Code
3. Hit `F1` and pick `MCP: Add server`
4. Choose `Command Stdio`
5. Enter: `uv run --directory=/path/to/jayrah jayrah mcp`
6. Save the config (e.g., to `.vscode/mcp.json`):

```json
{
    "servers": {
        "jayrah": {
            "type": "stdio",
            "command": "uv",
            "args": [
                "run",
                "--directory",
               "/path/to/jayrah",
               "jayrah",
               "mcp"
            ]
        }
    }
}
```

7. In Copilot Chat, select the tools button (often a sparkle icon or similar) to see and use Jayrah's available actions.

### Using Pagination with Browse

When browsing issues using the MCP server in Copilot Chat, you can now use pagination to navigate through large sets of issues:

```bash
# Basic usage
@jira browse --board="MyBoard"

# Display more issues on a single page (default is 10)
@jira browse --board="MyBoard" --limit=20

# Navigate to page 2 of the results
@jira browse --board="MyBoard" --page=2

# Customize page size (default is 100 issues per page)
@jira browse --board="MyBoard" --page_size=50 

# Combine parameters for fine-grained control
@jira browse --board="MyBoard" --limit=15 --page=3 --page_size=50

# Search for issues containing specific terms
@jira browse --board="MyBoard" --search_terms=["urgent", "bug"]

# Using OR instead of AND for search terms
@jira browse --board="MyBoard" --search_terms=["urgent", "bug"] --use_or=true

# Combine search with pagination
@jira browse --board="MyBoard" --search_terms=["urgent", "bug"] --page=2 --limit=15
```

The output will show you which page you're viewing and how to navigate between pages.

The output will show you which page you're viewing and how to navigate between pages.

## Need help?

Run `jayrah help` for all the details.

## License

[Apache-2.0](./LICENSE)

## Author

### Chmouel Boudjnah

* Fediverse - <[@chmouel@chmouel.com](https://fosstodon.org/@chmouel)>
* Twitter - <[@chmouel](https://twitter.com/chmouel)>
* Blog - <[https://blog.chmouel.com](https://blog.chmouel.com)>
