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

The MCP server exposes these tools and resources:

- Resources: projects are exposed via `jira://project/<KEY>` URIs.
- `search`: Comprehensive issue search with JQL or fields
  - Inputs: `jql`, `text`, `project`, `status`, `assignee`, `reporter`, `priority`, `issue_type`, `components[]`, `labels[]`, `created_after`, `created_before`, `updated_after`, `updated_before`, `fix_version`, `affects_version`, `epic`, `sprint`, `custom_fields{}`, `order_by`, `order_direction`, `limit`, `page`, `page_size`.
- `create-issue`: Create a new issue
  - Inputs: `project?`, `issuetype`, `summary`, `description?`, `priority?`, `assignee?`, `labels[]?`, `components[]?`.
- `view-issue`: View details of an issue
  - Inputs: `ticket`, `comments?`.
- `update-issue`: Update issue fields
  - Inputs: `ticket`, `fields{}`.
- `transition-issue` and `get-transitions`: Move issue status or list transitions
  - Inputs: `ticket`, `transition_id` (for `transition-issue`).
- `add-comment`: Add a comment to an issue
  - Inputs: `ticket`, `comment`.
- `edit-comment`: Edit an existing comment
  - Inputs: `ticket`, `comment_id`, `comment`.
- `delete-comment`: Delete a comment
  - Inputs: `ticket`, `comment_id`.
- `open-issue`: Get the browser URL for an issue
  - Inputs: `ticket`.
- `assign-issue`: Assign an issue to a user (accountId/name supported)
  - Inputs: `ticket`, `assignee`.
- `add-labels` / `remove-labels`: Manage labels on an issue
  - Inputs: `ticket`, `labels[]`.
- `link-issues`: Create an issue link (default type: Relates)
  - Inputs: `inward`, `outward`, `link_type?`, `comment?`.
- `get-comments`: List comments with pagination
  - Inputs: `ticket`, `limit?`, `page?`, `page_size?`.
- `log-work`: Add a worklog entry
  - Inputs: `ticket`, `time_spent`, `comment?`, `started?`.
- `get-changelog`: Retrieve change history with pagination
  - Inputs: `ticket`, `limit?`, `page?`, `page_size?`.
- Metadata helpers: `list-issue-types`, `list-priorities`, `list-users`, `list-labels`, `list-components`.

### Examples

Typical MCP tool payloads (exact invocation depends on your MCP client):

- Search:

```json
{
  "name": "search",
  "arguments": {
    "project": "PROJ",
    "text": "login bug",
    "status": "In Progress",
    "limit": 5,
    "page": 1
  }
}
```

- Create issue:

```json
{
  "name": "create-issue",
  "arguments": {
    "project": "PROJ",
    "issuetype": "Bug",
    "summary": "Fix login timeout",
    "description": "Steps to reproduce...",
    "priority": "High",
    "labels": ["auth", "backend"],
    "components": ["Identity"]
  }
}
```

- Assign issue:

```json
{
  "name": "assign-issue",
  "arguments": {
    "ticket": "PROJ-123",
    "assignee": "user@example.com"
  }
}
```

- Add/remove labels:

```json
{
  "name": "add-labels",
  "arguments": {
    "ticket": "PROJ-123",
    "labels": ["triaged", "regression"]
  }
}
```

```json
{
  "name": "remove-labels",
  "arguments": {
    "ticket": "PROJ-123",
    "labels": ["wip"]
  }
}
```

- Link issues:

```json
{
  "name": "link-issues",
  "arguments": {
    "inward": "PROJ-100",
    "outward": "PROJ-200",
    "link_type": "Relates",
    "comment": "Establishing relationship"
  }
}
```

- Log work:

```json
{
  "name": "log-work",
  "arguments": {
    "ticket": "PROJ-123",
    "time_spent": "1h 30m",
    "comment": "Investigation and fix"
  }
}
```

- Get comments and changelog:

```json
{
  "name": "get-comments",
  "arguments": {
    "ticket": "PROJ-123",
    "limit": 10,
    "page": 1
  }
}
```

- Edit or delete a comment (use `get-comments` to find the `comment_id`):

```json
{
  "name": "edit-comment",
  "arguments": {
    "ticket": "PROJ-123",
    "comment_id": "10001",
    "comment": "This is the updated comment text."
  }
}
```

```json
{
  "name": "delete-comment",
  "arguments": {
    "ticket": "PROJ-123",
    "comment_id": "10002"
  }
}
```

```json
{
  "name": "get-changelog",
  "arguments": {
    "ticket": "PROJ-123",
    "limit": 20
  }
}
```

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

## Web UI Server

Jayrah includes a web-based UI that can be started with:

```bash
jayrah web
```

This will start a web UI server on [http://localhost:8000](http://localhost:8000) by default. You can open this URL in your web browser to use the Jayrah web interface to browse and manage Jira issues in a quick and user-friendly way.

**Security Note:**
> The web server is intended for local development and use only. Do **not** expose it to the public internet, as it is not hardened for production or external access.

## License

Apache-2.0

## Author

Chmouel Boudjnah
