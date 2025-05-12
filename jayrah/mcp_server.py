import json

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from pydantic import AnyUrl

from . import boards, config, defaults, utils

# Initialize config and boards for Jira access
config_file = defaults.CONFIG_FILE
wconfig = config.make_config({}, config_file)
boards_obj = boards.Boards(wconfig)

server = Server("jayrah")


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """
    List all available Jira boards as resources
    """
    board_resources = []

    if wconfig.get("boards"):
        for board in wconfig.get("boards", []):
            board_name = board.get("name", "")
            description = board.get("description", f"Jira board: {board_name}")
            board_resources.append(
                types.Resource(
                    uri=AnyUrl(f"jira://board/{board_name}"),
                    name=f"Board: {board_name}",
                    description=description,
                    mimeType="application/json",
                )
            )

    return board_resources


@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """
    Read a specific resource by its URI.
    """
    if uri.scheme == "jira":
        parts = uri.path.lstrip("/").split("/")
        if len(parts) >= 2 and parts[0] == "board":
            board_name = parts[1]
            jql, order_by = boards.check(board_name, wconfig)
            if not jql or not order_by:
                return json.dumps(
                    {"error": f"Invalid board or missing JQL: {board_name}"}
                )

            issues = boards_obj.list_issues(jql, order_by=order_by)
            return json.dumps({"board": board_name, "issues": issues})

        elif len(parts) >= 2 and parts[0] == "issue":
            issue_key = parts[1]
            try:
                issue = boards_obj.jira.get_issue(issue_key)
                return json.dumps(issue)
            except Exception as e:
                return json.dumps(
                    {"error": f"Error fetching issue {issue_key}: {str(e)}"}
                )

    raise ValueError(f"Unsupported URI scheme or format: {uri}")


@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """
    List available prompts.
    Each prompt can have optional arguments to customize its behavior.
    """
    return [
        types.Prompt(
            name="analyze-jira-issue",
            description="Analyze a Jira issue and provide insights",
            arguments=[
                types.PromptArgument(
                    name="issue_key",
                    description="The Jira issue key (e.g., PROJ-123)",
                    required=True,
                )
            ],
        ),
    ]


@server.get_prompt()
async def handle_get_prompt(
    name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    """
    Generate a prompt by combining arguments with server state.
    """
    if name == "analyze-jira-issue":
        issue_key = (arguments or {}).get("issue_key")
        if not issue_key:
            raise ValueError("Missing required argument: issue_key")

        try:
            issue = boards_obj.jira.get_issue(issue_key)
            issue_data = json.dumps(issue, indent=2)

            return types.GetPromptResult(
                description=f"Analyze Jira issue {issue_key}",
                messages=[
                    types.PromptMessage(
                        role="user",
                        content=types.TextContent(
                            type="text",
                            text=f"Please analyze this Jira issue and provide insights on its status, "
                            f"any blockers, and next steps:\n\n{issue_data}",
                        ),
                    )
                ],
            )
        except Exception as e:
            raise ValueError(f"Error fetching issue {issue_key}: {str(e)}")

    raise ValueError(f"Unknown prompt: {name}")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools, mapping to Jira CLI commands.
    Each tool specifies its arguments using JSON Schema validation.
    """
    return [
        # Jira browse boards
        types.Tool(
            name="browse",
            description="Browse Jira boards and list issues",
            inputSchema={
                "type": "object",
                "properties": {
                    "board": {
                        "type": "string",
                        "description": "Board name as defined in config",
                    },
                },
                "required": ["board"],
            },
        ),
        # Create Jira issue
        types.Tool(
            name="create-issue",
            description="Create a new Jira issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "issuetype": {
                        "type": "string",
                        "description": "Issue type (e.g., Story, Bug)",
                    },
                    "summary": {"type": "string", "description": "Issue summary"},
                    "description": {
                        "type": "string",
                        "description": "Issue description",
                    },
                    "priority": {"type": "string", "description": "Priority level"},
                    "assignee": {"type": "string", "description": "Assignee username"},
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of labels",
                    },
                },
                "required": ["issuetype", "summary"],
            },
        ),
        # View Jira issue
        types.Tool(
            name="view-issue",
            description="View details of a specific Jira issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket": {
                        "type": "string",
                        "description": "Issue key (e.g., PROJ-123)",
                    },
                    "comments": {
                        "type": "integer",
                        "description": "Number of comments to show",
                    },
                },
                "required": ["ticket"],
            },
        ),
        # Transition Jira issue
        types.Tool(
            name="transition-issue",
            description="Transition a Jira issue to a new status",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket": {
                        "type": "string",
                        "description": "Issue key (e.g., PROJ-123)",
                    },
                    "transition_id": {
                        "type": "string",
                        "description": "ID of the transition to perform",
                    },
                },
                "required": ["ticket", "transition_id"],
            },
        ),
        # Get available transitions
        types.Tool(
            name="get-transitions",
            description="Get available transitions for a Jira issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket": {
                        "type": "string",
                        "description": "Issue key (e.g., PROJ-123)",
                    },
                },
                "required": ["ticket"],
            },
        ),
        # Open issue in browser
        types.Tool(
            name="open-issue",
            description="Get URL to open a Jira issue in browser",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket": {
                        "type": "string",
                        "description": "Issue key (e.g., PROJ-123)",
                    },
                },
                "required": ["ticket"],
            },
        ),
        # List available boards
        types.Tool(
            name="list-boards",
            description="List all available Jira boards",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Handle tool execution requests, mapping to Jira CLI commands.
    """
    try:
        if name == "browse":
            board = arguments.get("board")
            if not board:
                raise ValueError("Board name is required")

            jql, order_by = boards.check(board, wconfig)
            if not jql or not order_by:
                return [
                    types.TextContent(
                        type="text", text=f"Invalid board or missing JQL: {board}"
                    )
                ]

            issues = boards_obj.list_issues(jql, order_by=order_by)

            # Format a summary of the issues
            summary = f"Found {len(issues)} issues on board '{board}':\n\n"
            for i, issue in enumerate(issues[:10]):  # Limit to first 10 for readability
                key = issue.get("key", "Unknown")
                summary_text = issue.get("fields", {}).get("summary", "No summary")
                status = (
                    issue.get("fields", {}).get("status", {}).get("name", "Unknown")
                )
                summary += f"{i + 1}. {key}: {summary_text} ({status})\n"

            if len(issues) > 10:
                summary += f"\n... and {len(issues) - 10} more issues."

            return [
                types.TextContent(
                    type="text",
                    text=summary,
                )
            ]

        elif name == "create-issue":
            if not arguments:
                raise ValueError("Missing arguments")

            issuetype = arguments.get("issuetype", "Story")
            summary = arguments.get("summary")
            description = arguments.get("description")
            priority = arguments.get("priority")
            assignee = arguments.get("assignee")
            labels = arguments.get("labels")

            if not summary:
                raise ValueError("Summary is required")

            result = boards_obj.jira.create_issue(
                issuetype=issuetype,
                summary=summary,
                description=description,
                priority=priority,
                assignee=assignee,
                labels=labels,
            )

            issue_key = result.get("key", "Unknown")
            return [
                types.TextContent(
                    type="text",
                    text=f"Created issue {issue_key} successfully.\nSummary: {summary}",
                )
            ]

        elif name == "view-issue":
            ticket = arguments.get("ticket")

            if not ticket:
                raise ValueError("Ticket key is required")

            issue = boards_obj.jira.get_issue(ticket)

            # Format the issue data in a readable way
            fields = issue.get("fields", {})
            summary = fields.get("summary", "No summary")
            description = fields.get("description", "No description")
            status = fields.get("status", {}).get("name", "Unknown")
            issue_type = fields.get("issuetype", {}).get("name", "Unknown")

            formatted_issue = f"Issue: {ticket}\n"
            formatted_issue += f"Type: {issue_type}\n"
            formatted_issue += f"Status: {status}\n"
            formatted_issue += f"Summary: {summary}\n\n"
            formatted_issue += f"Description:\n{description}\n"

            return [types.TextContent(type="text", text=formatted_issue)]

        elif name == "transition-issue":
            ticket = arguments.get("ticket")
            transition_id = arguments.get("transition_id")

            if not ticket or not transition_id:
                raise ValueError("Ticket key and transition ID are required")

            result = boards_obj.jira.transition_issue(ticket, transition_id)

            return [
                types.TextContent(
                    type="text",
                    text=f"Successfully transitioned issue {ticket} with transition ID {transition_id}",
                )
            ]

        elif name == "get-transitions":
            ticket = arguments.get("ticket")

            if not ticket:
                raise ValueError("Ticket key is required")

            transitions = boards_obj.jira.get_transitions(ticket)

            # Format the transitions in a readable way
            formatted_transitions = f"Available transitions for {ticket}:\n\n"

            for transition in transitions.get("transitions", []):
                transition_id = transition.get("id")
                transition_name = transition.get("name")
                to_status = transition.get("to", {}).get("name")

                formatted_transitions += (
                    f"ID: {transition_id}, Name: {transition_name}, To: {to_status}\n"
                )

            return [types.TextContent(type="text", text=formatted_transitions)]

        elif name == "open-issue":
            ticket = arguments.get("ticket")

            if not ticket:
                raise ValueError("Ticket key is required")

            url = utils.make_full_url(ticket, wconfig.get("jira_server"))

            return [types.TextContent(type="text", text=f"URL for {ticket}: {url}")]

        elif name == "list-boards":
            # Format board information
            formatted_boards = "Available boards:\n\n"

            for board in wconfig.get("boards", []):
                board_name = board.get("name", "Unnamed")
                description = board.get("description", "No description")
                formatted_boards += f"* {board_name}: {description}\n"

            return [types.TextContent(type="text", text=formatted_boards)]

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        return [
            types.TextContent(
                type="text", text=f"Error executing tool '{name}': {str(e)}"
            )
        ]


async def main():
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="jayrah",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
