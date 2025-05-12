# 🌞 Jayrah - A Jira with FZF CLI 🌞

Jayrah is a command-line interface (CLI) tool that helps you interact with Jira more efficiently. It provides a fuzzy search interface via FZF for browsing issues, creating tickets, and performing various actions on tickets.

## Installation

```bash
uvx jayrah
```

Or install from source:

```bash
git clone https://github.com/chmouel/jayrah.git
cd jayrah
uv run jayrah
```

## Requirements

* **uv** - Install from <https://docs.astral.sh/uv/getting-started/installation>
* **fzf** - install with your package manager.

## Configuration

Jayrah uses a configuration file located at `~/.config/jayrah/config.yaml` by default. You can specify a different config file using the `--config-file` option.

Example configuration:

```yaml
jira_server: "https://your-jira-instance.atlassian.net"
jira_user: "your-email@example.com"
jira_password: "your-api-token"
jira_component: "your-component"

# Custom boards configuration
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

You can also set configuration through environment variables:

* `JIRA_SERVER`
* `JIRA_USER`
* `JIRA_PASSWORD`
* `JIRA_COMPONENT`

## Usage

### 🔍 Browse issues

```bash
jayrah browse [BOARD]
```

Where `BOARD` is one of the boards defined in your configuration file.

### ✨ Create an issue

```bash
jayrah create --type "Story" --summary "Issue summary" --description "Issue description"
```

### 🛠️ Working with issues

```bash
# 🌐 Open an issue in browser
jayrah issue open TICKET-123

# 👁️ View issue details
jayrah issue view TICKET-123 [--comments N]

# 🎬 Perform actions on an issue (transition, edit, etc.)
jayrah issue action TICKET-123

# 📝 Edit issue description
jayrah issue edit-description TICKET-123

# 🔄 Transition an issue to a new status
jayrah issue transition TICKET-123
```

## Shell completion

## ZSH

copy [./misc/completion.zsh](./misc/completion.zsh) to your [zsh fpath](https://github.com/zsh-users/zsh-completions/blob/master/zsh-completions-howto.org#telling-zsh-which-function-to-use-for-completing-a-command)
directory or add the following to your `.zshrc`:

```shell
eval "$(_JAYRAH_COMPLETE=zsh_source jayrah)" 
```

## Bash

Copy [./misc/completion.bash](./misc/completion.bash) to your bash completion
directory or add this to your `.bashrc`:

```shell
```shell
eval "$(_JAYRAH_COMPLETE=bash_source jayrah)" 
```

## MCP Server Integration with Jayrah

To integrate Jayrah's Jira functionality with AI agents and other tools, we've implemented a Model Context Protocol (MCP) server that exposes all the key features as a standard API.

### Starting the MCP Server

You can start the MCP server using the following command:

```bash
jayrah mcp-server
```

By default, this starts the server in stdio mode for use with VS Code and the MCP extension.

### Supported Tools

The MCP server supports the following tools that map to CLI commands:

* **browse**: List issues on a specific board
* **create-issue**: Create a new Jira issue
* **view-issue**: View details of a specific issue
* **transition-issue**: Change the status of an issue
* **get-transitions**: Get available transitions for an issue
* **open-issue**: Get URL to open an issue in browser
* **list-boards**: List all available boards

### Using with VS Code

1. Get access to Copilot Chat.
2. Choose the action `MCP: Add server` from the command palette.
3. Choose `Command Stdio`
4. Type the command `jayrah mcp-server` in the input box.
5. Choose where to  save the configuration file (e.g., `.vscode/mcp.json`).
your `.vscode/mcp.json` will look like

```json
{
    "servers": {
        "jayrah": {
            "type": "stdio",
            "command": "jayrah",
            "args": [
                "mcp-server"
            ]
        }
    }
}
```

6. Open the Copilot Chat choose agent and press the Tools button.

### Using with AI Agents (Claude, etc.)

The MCP server can be used by AI agents that support tool-calling over the MCP protocol. For example, with Anthropic Claude:

1. Start the MCP server
2. Configure Claude to use the MCP server
3. Ask Claude to perform Jira tasks like "create a new story for improving error handling" or "show me issues on the myissues board"

Example agent interaction:

```text
me: Show me all issues on my current board
claude: I'll check that for you using the browse tool...

[Tool usage: browse with board="myissues"]

Found 5 issues on board 'myissues':

1. PROJ-123: Implement error handling (In Progress)
2. PROJ-124: Update documentation (To Do)
...
```

## Help

Run `jayrah help` for more information on how to use the tool.

## Copyright

[Apache-2.0](./LICENSE)

## Authors

### Chmouel Boudjnah

* Fediverse - <[@chmouel@chmouel.com](https://fosstodon.org/@chmouel)>
* Twitter - <[@chmouel](https://twitter.com/chmouel)>
* Blog  - <[https://blog.chmouel.com](https://blog.chmouel.com)>
