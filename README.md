# Jayrah - A Jira Helper Tool

Jayrah is a command-line interface (CLI) tool that helps you interact with Jira more efficiently. It provides a fuzzy search interface for browsing issues, creating tickets, and performing various actions on tickets.

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

### Browse issues

```bash
jayrah browse [BOARD]
```

Where `BOARD` is one of the boards defined in your configuration file.

### Create an issue

```bash
jayrah create --type "Story" --summary "Issue summary" --description "Issue description"
```

### Working with issues

```bash
# Open an issue in browser
jayrah issue open TICKET-123

# View issue details
jayrah issue view TICKET-123 [--comments N]

# Perform actions on an issue (transition, edit, etc.)
jayrah issue action TICKET-123

# Edit issue description
jayrah issue edit-description TICKET-123

# Transition an issue to a new status
jayrah issue transition TICKET-123
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
