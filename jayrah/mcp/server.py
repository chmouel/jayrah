"""MCP server implementation for Jayrah AI integration."""

import json

import mcp.server.stdio
from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from pydantic import AnyUrl

from jayrah import config
from jayrah.ui import boards

from .. import utils

# Initialize config and boards for Jira access
config_file = config.defaults.CONFIG_FILE
wconfig = config.make_config({}, config_file)
boards_obj = boards.Boards(wconfig)

server = Server("jayrah")


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """
    List all available Jira boards as resources
    """
    return [_create_board_resource(board) for board in wconfig.get("boards", [])]


def _create_board_resource(board: dict) -> types.Resource:
    """Create a resource object for a Jira board."""
    board_name = board.get("name", "")
    description = board.get("description", f"Jira board: {board_name}")

    return types.Resource(
        uri=AnyUrl(f"jira://board/{board_name}"),
        name=f"Board: {board_name}",
        description=description,
        mimeType="application/json",
    )


@server.read_resource()
async def handle_read_resource(uri: AnyUrl) -> str:
    """
    Read a specific resource by its URI.
    """
    if uri.scheme != "jira":
        raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

    parts = uri.path.lstrip("/").split("/")
    if len(parts) < 2:
        raise ValueError(f"Invalid URI format: {uri}")

    resource_type = parts[0]
    resource_id = parts[1]

    if resource_type == "board":
        return await _read_board_resource(resource_id)
    if resource_type == "issue":
        return await _read_issue_resource(resource_id)
    raise ValueError(f"Unsupported resource type: {resource_type}")


async def _read_board_resource(board_name: str) -> str:
    """Read and return issues from a specific board."""
    jql, order_by = boards.check(board_name, wconfig)
    if not jql or not order_by:
        return json.dumps({"error": f"Invalid board or missing JQL: {board_name}"})

    issues = boards_obj.issues_client.list_issues(jql, order_by=order_by)
    return json.dumps({"board": board_name, "issues": issues})


async def _read_issue_resource(issue_key: str) -> str:
    """Read and return details of a specific issue."""
    try:
        issue = boards_obj.jira.get_issue(issue_key)
        return json.dumps(issue)
    except AttributeError as e:
        return json.dumps(
            {"error": f"Attribute error fetching issue {issue_key}: {str(e)}"}
        )
    except Exception as e:  # pylint: disable=W0718
        return json.dumps({"error": f"Error fetching issue {issue_key}: {str(e)}"})


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
        return await _generate_analyze_issue_prompt(arguments or {})

    raise ValueError(f"Unknown prompt: {name}")


async def _generate_analyze_issue_prompt(
    arguments: dict[str, str],
) -> types.GetPromptResult:
    """Generate a prompt to analyze a Jira issue."""
    issue_key = arguments.get("issue_key")
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
        raise ValueError(f"Error fetching issue {issue_key}: {str(e)}") from e


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
                    "search_terms": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of search terms to filter issues by summary and description",
                    },
                    "use_or": {
                        "type": "boolean",
                        "description": "Use OR instead of AND to combine search terms (default: false)",
                    },
                    "filters": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter issues by specific fields (e.g., 'status=In Progress', 'priority=High')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of issues to display (default: 10)",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number to retrieve (starts at 1)",
                    },
                    "page_size": {
                        "type": "integer",
                        "description": "Number of issues to retrieve per page (default: 100)",
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
    tool_handlers = {
        "browse": _handle_browse,
        "create-issue": _handle_create_issue,
        "view-issue": _handle_view_issue,
        "transition-issue": _handle_transition_issue,
        "get-transitions": _handle_get_transitions,
        "open-issue": _handle_open_issue,
        "list-boards": _handle_list_boards,
    }

    try:
        handler = tool_handlers.get(name)
        if not handler:
            raise ValueError(f"Unknown tool: {name}")

        return await handler(arguments or {})
    except Exception as e:  # pylint: disable=W0718
        return [
            types.TextContent(
                type="text", text=f"Error executing tool '{name}': {str(e)}"
            )
        ]


async def _handle_browse(arguments: dict) -> list[types.TextContent]:
    """Handle the browse tool to list issues on a board."""
    board = arguments.get("board")
    limit = arguments.get("limit", 10)  # Default display limit is 10
    page = arguments.get("page", 1)  # Default to first page
    page_size = arguments.get("page_size", 100)  # Default page size is 100
    search_terms = arguments.get("search_terms", [])  # Get search terms if provided
    use_or = arguments.get("use_or", False)  # Get OR/AND flag
    filters = arguments.get("filters", [])  # Get field-specific filters

    # For backward compatibility
    if not search_terms and "search" in arguments and arguments["search"]:
        search_terms = [arguments["search"]]

    if not board:
        raise ValueError("Board name is required")

    jql, order_by = boards.check(board, wconfig)
    if not jql or not order_by:
        return [
            types.TextContent(
                type="text", text=f"Invalid board or missing JQL: {board}"
            )
        ]

    # Use the common function to build the search JQL
    jql = boards.build_search_jql(
        jql, search_terms, use_or, wconfig.get("verbose", False), filters
    )

    # Calculate start_at based on page number (0-indexed for the API)
    start_at = (page - 1) * page_size

    # Always fetch a single page at a time for pagination control
    issues = boards_obj.issues_client.list_issues(
        jql, order_by=order_by, limit=page_size, all_pages=False, start_at=start_at
    )

    # If we have issues returned, try to get the total count from the metadata
    if issues:
        # This is a bit of a hack since Jira API doesn't return total with the issues
        # We need to use search_issues directly to get the total
        try:
            result = boards_obj.jira.search_issues(
                jql,
                start_at=0,
                max_results=1,  # Just need one to get the metadata
                fields=["key"],  # Minimal fields to reduce payload
            )
            total = result.get("total", 0)

            # Add the total to each issue's metadata (or create metadata if it doesn't exist)
            for issue in issues:
                if "metadata" not in issue:
                    issue["metadata"] = {}
                issue["metadata"]["total"] = total
        except Exception:
            # If we can't get the total, just continue without it
            pass

    return [
        types.TextContent(
            type="text",
            text=_format_issues_summary(
                board,
                issues,
                limit,
                page,
                page_size,
                search_terms=search_terms,
                use_or=use_or,
                filters=filters,
            ),
        )
    ]


# pylint: disable=too-many-locals
# pylint: disable=too-many-arguments
def _format_issues_summary(
    board_name: str,
    issues: list[dict],
    limit: int = 10,
    page: int = 1,
    page_size: int = 100,
    search_terms: list | None = None,
    use_or: bool = False,
    filters: list | None = None,
    search_term: str | None = None,  # For backward compatibility
) -> str:
    """Format a list of issues into a readable summary."""
    # Get the total number of issues (from the page)
    total_in_page = len(issues)

    # Calculate pagination info
    start_index = (page - 1) * page_size

    # Get total count if available in the first issue's metadata
    total_count = None
    if issues and "metadata" in issues[0] and "total" in issues[0]["metadata"]:
        total_count = issues[0]["metadata"]["total"]

    # Handle backward compatibility
    if not search_terms and search_term:
        search_terms = [search_term]

    # Create the summary heading with search term info and filters if applicable
    summary_parts = []
    if search_terms:
        # Use the common helper function to format search terms
        terms_text = boards.format_search_terms(search_terms, use_or)
        summary_parts.append(f"matching {terms_text}")

    if filters:
        filter_text = " AND ".join(f"{f}" for f in filters)
        summary_parts.append(f"with filters: {filter_text}")

    search_info = " " + " ".join(summary_parts) if summary_parts else ""

    if total_count:
        summary = f"Found {total_count} total issues{search_info} on board '{board_name}' (Page {page}, showing {total_in_page}):\n\n"
    else:
        summary = f"Found {total_in_page} issues{search_info} on board '{board_name}' (Page {page}):\n\n"

    # Display issues up to the specified limit
    display_count = min(limit, total_in_page)

    for i, issue in enumerate(issues[:display_count]):
        key = issue.get("key", "Unknown")
        fields = issue.get("fields", {})
        summary_text = fields.get("summary", "No summary")
        status = fields.get("status", {}).get("name", "Unknown")

        summary += f"{start_index + i + 1}. {key}: {summary_text} ({status})\n"

    # Add pagination information
    if total_in_page > display_count:
        summary += (
            f"\n... and {total_in_page - display_count} more issues on this page."
        )

    summary += f"\n\nShowing issues {start_index + 1}-{start_index + display_count}"
    if total_count:
        summary += f" of {total_count} total issues (page {page})."
    else:
        summary += f" of page {page}."

    summary += "\nUse the 'page' parameter to navigate between pages and 'limit' to adjust how many issues are displayed."

    return summary


async def _handle_create_issue(arguments: dict) -> list[types.TextContent]:
    """Handle the create-issue tool to create a new Jira issue."""
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


async def _handle_view_issue(arguments: dict) -> list[types.TextContent]:
    """Handle the view-issue tool to view details of a specific Jira issue."""
    ticket = arguments.get("ticket")
    if not ticket:
        raise ValueError("Ticket key is required")

    issue = boards_obj.jira.get_issue(ticket)
    formatted_issue = _format_issue_details(ticket, issue)
    return [types.TextContent(type="text", text=formatted_issue)]


def _format_issue_details(ticket: str, issue: dict) -> str:
    """Format issue details into a readable string."""
    fields = issue.get("fields", {})
    summary = fields.get("summary", "No summary")
    description = fields.get("description", "No description")
    status = fields.get("status", {}).get("name", "Unknown")
    issue_type = fields.get("issuetype", {}).get("name", "Unknown")

    formatted = [
        f"Issue: {ticket}",
        f"Type: {issue_type}",
        f"Status: {status}",
        f"Summary: {summary}",
        "",
        "Description:",
        description,
    ]

    return "\n".join(formatted)


async def _handle_transition_issue(arguments: dict) -> list[types.TextContent]:
    """Handle the transition-issue tool to transition a Jira issue to a new status."""
    ticket = arguments.get("ticket")
    transition_id = arguments.get("transition_id")

    if not ticket or not transition_id:
        raise ValueError("Ticket key and transition ID are required")

    # This could be improved to handle the actual return value of transition_issue
    boards_obj.jira.transition_issue(ticket, transition_id)

    return [
        types.TextContent(
            type="text",
            text=f"Successfully transitioned issue {ticket} with transition ID {transition_id}",
        )
    ]


async def _handle_get_transitions(arguments: dict) -> list[types.TextContent]:
    """Handle the get-transitions tool to get available transitions for a Jira issue."""
    ticket = arguments.get("ticket")
    if not ticket:
        raise ValueError("Ticket key is required")

    transitions = boards_obj.jira.get_transitions(ticket)
    formatted_transitions = _format_transitions(ticket, transitions)

    return [types.TextContent(type="text", text=formatted_transitions)]


def _format_transitions(ticket: str, transitions: dict) -> str:
    """Format transitions data into a readable string."""
    result = f"Available transitions for {ticket}:\n\n"

    for transition in transitions.get("transitions", []):
        transition_id = transition.get("id")
        transition_name = transition.get("name")
        to_status = transition.get("to", {}).get("name")

        result += f"ID: {transition_id}, Name: {transition_name}, To: {to_status}\n"

    return result


async def _handle_open_issue(arguments: dict) -> list[types.TextContent]:
    """Handle the open-issue tool to get URL to open a Jira issue in browser."""
    ticket = arguments.get("ticket")
    if not ticket:
        raise ValueError("Ticket key is required")

    url = utils.make_full_url(ticket, wconfig.get("jira_server"))
    return [types.TextContent(type="text", text=f"URL for {ticket}: {url}")]


async def _handle_list_boards(arguments: dict) -> list[types.TextContent]:
    """Handle the list-boards tool to list all available Jira boards."""
    # Format board information
    formatted_boards = "Available boards:\n\n"
    for board in wconfig.get("boards", []):
        board_name = board.get("name", "Unnamed")
        description = board.get("description", "No description")
        formatted_boards += f"* {board_name}: {description}\n"

    return [types.TextContent(type="text", text=formatted_boards)]


async def main():
    """Start and run the MCP server using stdin/stdout streams."""
    initialization_options = InitializationOptions(
        server_name="jayrah",
        server_version="0.1.0",
        capabilities=server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )

    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, initialization_options)
