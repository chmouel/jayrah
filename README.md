<img align="right" src="https://github.com/user-attachments/assets/e65d653a-2442-4034-aba0-b302a0094a59" alt="ChatGPT Image" width="128" height="128">

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
jira_server: "https://your-jira-id.atlassian.net" # or other Jira custom server URL
jira_user: "you@example.com"
jira_password: "your-api-token" # or you can use a pass path, with the pass:: prefix, for example pass::jira/token
jira_project: "PROJECT-KEY"
api_version: "2"  # Use "3" for Jira Cloud with the newer API
auth_method: "basic" # or "bearer" for operations Bearer authentication
```

Jayrah supports both Bearer token and Basic authentication:

- API v2 uses Bearer token authentication by default
- API v3 uses Basic authentication by default

For Basic authentication, make sure your configuration includes both `jira_user` and `jira_password`.

If you don't configure your config.yaml file, jayrah will prompt you for the
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
- Press `e` to edit the title or description of the issue. (the editor emulates
  readline/emacs keys).
- Use `F1` for the command palette

### Editing issue descriptions

Jayrah supports editing issue title and descriptions.

When editing a description:

1. Press `e` to access the edit menu
2. Select "description" from the options
3. Edit your description in the text area
4. You can navigate with emacs or readline keys.
5. Press `Ctrl+S` to save your changes or `Escape` to cancel

## Custom Fields

You can display and edit custom Jira fields in the TUI by adding a section to your config:

```yaml
custom_fields:
  - name: Git PR
    description: "URL to the git pull request"
    field: customfield_12310220
    type: url
  - name: Release Note
    description: "Release note for the issue"
    field: customfield_12317313
    type: text
  - name: Some Number Field
    description: "A numeric value"
    field: customfield_999999
    type: number
  - name: Some Other Custom Field
    field: customfield_45678
    type: string
```

- `type` can be `string` (default), `text`, `url`, or `number`.
  - `url` fields are validated as URLs.
  - `text` fields use a multi-line editor.
  - `number` fields require a valid number.
  - `string` fields use a single-line input.
- `description` is shown in the edit dialog if provided.

If a custom field is not empty, it will be shown in the issue details view. You can also edit these fields from the edit menu.

To find the correct custom field ID (e.g., `customfield_12310`), the easiest way is to use your web browser's developer tools while editing a field in Jira. Look at the network requests and see which field is being updated in the REST API call. Use that field ID in your config.

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
