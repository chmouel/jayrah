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

#### 🔎 Field Filtering Examples

Jayrah supports powerful field-specific filtering with the `--filter` option:

```bash
# Basic status filtering
jayrah browse myissues --filter status="In Progress"
jayrah browse myissues --filter status="Code Review"

# Multiple field filters (combined with AND)
jayrah browse myissues --filter status="In Progress" --filter priority=High
jayrah browse myissues --filter assignee=currentUser() --filter created>"-1w"

# Combining content search with field filters
jayrah browse myissues bug frontend --filter status="To Do"

# Using Jira JQL operators in filters
jayrah browse myissues --filter created>"-1w"       # Issues created in last week
jayrah browse myissues --filter updated<"-30d"      # Issues not updated in 30 days 
jayrah browse myissues --filter summary~"Critical"  # Summary contains "Critical"
jayrah browse myissues --filter labels="backend"    # Has "backend" label

# Complex filtering examples
jayrah browse myissues --filter "sprint in openSprints()" --filter status!="Done"
jayrah browse myissues --filter "duedate < endOfWeek()" --filter priority="High"
```

Pick a board from your config file. Add search terms as arguments to filter issues by content. By default, multiple terms are combined with AND logic, but you can use the `--or` flag to combine them with OR logic. Use the `--filter` option to add field-specific filters in Jira JQL format.

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

#### 🌿 Git Branch Filtering Examples

Filtering works with the `git-branch` command too, helping you quickly find the right issue to branch from:

```bash
# Focus on specific issue statuses
jayrah git-branch --filter status="To Do"           # Only To Do issues
jayrah git-branch --filter status="In Progress"     # Only In Progress issues

# Find high-priority issues
jayrah git-branch --filter priority=High

# Combine with content search
jayrah git-branch bug --filter status="To Do"       # Bug issues in To Do
jayrah git-branch feature --filter sprint="Current Sprint"

# Advanced filtering
jayrah git-branch --filter "issuetype=Story" --filter "labels=frontend"
jayrah git-branch --filter "created>startOfWeek()" --filter "assignee=currentUser()"
```

The `git-branch` command will show you matching issues and let you select one to create a branch name from. The branch name will be formatted as `ISSUE-KEY-issue-summary-in-kebab-case`.

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

Follow these steps to set up Jayrah with VS Code:

* Clone the repo somewhere (e.g., `/path/to/jayrah`)
* Make sure you have Copilot in VS Code
* Hit `F1` and pick `MCP: Add server`
* Choose `Command Stdio`
* Enter: `uv run --directory=/path/to/jayrah jayrah mcp`
* Save the config (e.g., to `.vscode/mcp.json`):

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

* In Copilot Chat, select the tools button (often a sparkle icon or similar) to see and use Jayrah's available actions.

### Using MCP with Pagination and Filtering

When using the MCP server in Copilot Chat, you can leverage powerful pagination and filtering capabilities:

```bash
# Basic board browsing
@jira browse --board="myissues"

# Pagination options
@jira browse --board="myissues" --limit=20             # Show 20 issues per page
@jira browse --board="myissues" --page=2               # Show second page of results
@jira browse --board="myissues" --page_size=50 --page=3 # Customize page size and go to page 3

# Field filtering examples
@jira browse --board="myissues" --filters=["status=In Progress"]
@jira browse --board="myissues" --filters=["priority=High", "assignee=currentUser()"]

# Combining search terms with filters
@jira browse --board="myissues" --search_terms=["bug", "frontend"] --filters=["status=To Do"]
@jira browse --board="myissues" --search_terms=["api"] --filters=["created>-1w"]

# Using JQL operators in filters
@jira browse --board="myissues" --filters=["updated<-30d"]      # Not updated in 30 days
@jira browse --board="myissues" --filters=["summary~Critical"]  # Summary contains "Critical"

# Complex filtering examples
@jira browse --board="myissues" --filters=["sprint in openSprints()", "status!=Done"]
@jira browse --board="myissues" --filters=["duedate < endOfWeek()", "priority=High"]

# Using OR logic for search terms
@jira browse --board="myissues" --search_terms=["bug", "error"] --use_or=true

# Git branch suggestions with filters
@jira git-branch --filters=["status=To Do"]
@jira git-branch --search_terms=["feature"] --filters=["sprint in openSprints()"]
@jira git-branch --filters=["issuetype=Story", "labels=frontend"]
```

The output will show you which page you're viewing and how to navigate between pages. When using the git-branch command, you'll get a suggested branch name ready to use.

## Need help?

Run `jayrah help` for all the details.

## License

[Apache-2.0](./LICENSE)

## Author

### Chmouel Boudjnah

* Fediverse - <[@chmouel@chmouel.com](https://fosstodon.org/@chmouel)>
* Twitter - <[@chmouel](https://twitter.com/chmouel)>
* Blog - <[https://blog.chmouel.com](https://blog.chmouel.com)>
