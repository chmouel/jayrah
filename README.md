# Jayrah

A simple CLI and TUI for working with Jira from your terminal.

## Install

```sh
uvx jayrah
```

Or from source:

```sh
git clone https://github.com/chmouel/jayrah.git
cd jayrah
uv run jayrah
```

## Quick Setup

Create `~/.config/jayrah/config.yaml`:

```yaml
jira_server: "https://your-jira.atlassian.net"
jira_user: "you@example.com"
jira_password: "your-api-token" # or you can use a pass path, with the pass:: prefix, for example pass::jira/token
jira_project: "PROJECT-KEY"
```

if you don't configure your config.yaml file, jayrah will prompt you for the
required information when you run it for the first time.

## Usage

### Browse

Launch the issue browser with:

```sh
jayrah browse # or just `jayrah` will do the same
```

List all your boards with the `-l/--list-boards` option.
Filter issues by board with the `-f/--filter` option for example:

```sh
jayrah browse myissue --filter status=New
```

if you add words after the `jayrah browse BOARD` command, it will search for
issues that match those words.

```sh
jayrah browse myissue search1 search2
```

This by default will search for issues that match the words in the summary, you
can use the switch `--or` to instead do a or on the search terms.

- Create issue: `jayrah create`

## TUI (Terminal UI)

When you start browsing the issues of your board, you will be presented with a
list of all the issues in that board. You can use your mouse or your keyboard:

- Navigate with arrow keys or `j`/`k`
- Move the preview pan up and down with `J`/`K`
- Press `q` or `Escape` to quit
- Press `o` to open the issue in your browser
- Press `f` to filter issues by status, assignee, or other fields.
- Press `a` for all actions you can do on the issue.
- Press `c` for accessing or adding a comment.
- Press `t` to transition the issue to a new status.
- Press `e` to edit the title or description of the issue. (the editor emulate
  readline/emacs keys).
- Use `F1` for the command palette

## MCP Server for AI integration

Jayrah can run as an MCP server to work with AI tools like VS Code Copilot.

### Start the server

```bash
jayrah mcp
```

This runs in stdio mode by default for VS Code.

### Available actions

The server exposes these Jira operations:

- Browse issues (with pagination support)
  - `limit` - Control how many issues to display (default: 10)
  - `page` - Select which page of results to view (starts at 1)
  - `page_size` - Number of issues per page (default: 100)
- Create/view issues
- Change issue status
- Get possible status changes
- Open issues in browser
- List your boards

### VS Code setup

Follow these steps to set up Jayrah with VS Code:

- Clone the repo somewhere (e.g., `/path/to/jayrah`)
- Make sure you have Copilot in VS Code
- Hit `F1` and pick `MCP: Add server`
- Choose `Command Stdio`
- Enter: `uv run --directory=/path/to/jayrah jayrah mcp`
- Save the config (e.g., to `.vscode/mcp.json`):

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

- In Copilot Chat, select the tools button (often a sparkle icon or similar) to
see and use Jayrah's available actions.

## License

Apache-2.0

## Author

Chmouel Boudjnah
