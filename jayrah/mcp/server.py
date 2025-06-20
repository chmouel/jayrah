# pylint: disable=too-many-lines,too-many-branches,too-many-statements,too-many-locals
"""MCP server implementation for Jayrah AI integration."""

import json
from typing import Dict, List, Sequence, TypeVar, Union

import mcp.server.stdio
from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from pydantic import AnyUrl

from jayrah import config
from jayrah.ui import boards

from .. import utils

# Type definition for content return types
ContentType = Union[types.TextContent, types.ImageContent, types.EmbeddedResource]
T = TypeVar("T")


class ServerContext:
    """Context class to hold server-wide objects."""

    def __init__(self, config_file=None):
        """Initialize the server context with config and boards."""
        self.config_file = config_file or config.defaults.CONFIG_FILE
        self.wconfig = config.make_config({}, self.config_file)
        self.boards_obj = boards.Boards(self.wconfig)


def _create_board_resource(board: Dict) -> types.Resource:
    """Create a resource object for a Jira board."""
    board_name = board.get("name", "")
    description = board.get("description", f"Jira board: {board_name}")

    return types.Resource(
        uri=AnyUrl(f"jira://board/{board_name}"),
        name=f"Board: {board_name}",
        description=description,
        mimeType="application/json",
    )


def _format_issue_details(ticket: str, issue: Dict) -> str:
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


def _format_transitions(ticket: str, transitions: Dict) -> str:
    """Format transitions data into a readable string."""
    result = f"Available transitions for {ticket}:\n\n"

    for transition in transitions.get("transitions", []):
        transition_id = transition.get("id")
        transition_name = transition.get("name")
        to_status = transition.get("to", {}).get("name")

        result += f"ID: {transition_id}, Name: {transition_name}, To: {to_status}\n"

    return result


# pylint: disable=too-many-arguments
def _format_issues_summary(
    board_name: str,
    issues: List[Dict],
    limit: int = 10,
    page: int = 1,
    page_size: int = 100,
    search_terms: List | None = None,
    use_or: bool = False,
    filters: List | None = None,
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


def _format_search_results(
    jql: str,
    issues: List[Dict],
    total: int,
    limit: int = 10,
    page: int = 1,
    page_size: int = 100,
    start_at: int = 0,
) -> str:
    """Format search results into a readable summary."""
    # Create the summary heading
    summary = f"Found {total} issues matching JQL: {jql}\n"
    summary += f"Page {page} (showing {len(issues)} issues):\n\n"

    # Display issues up to the specified limit
    display_count = min(limit, len(issues))

    for i, issue in enumerate(issues[:display_count]):
        key = issue.get("key", "Unknown")
        fields = issue.get("fields", {})
        summary_text = fields.get("summary", "No summary")
        status = fields.get("status", {}).get("name", "Unknown")
        issue_type = fields.get("issuetype", {}).get("name", "Unknown")
        assignee = fields.get("assignee", {})
        assignee_name = (
            assignee.get("displayName", "Unassigned") if assignee else "Unassigned"
        )

        summary += f"{start_at + i + 1}. {key} [{issue_type}]: {summary_text}\n"
        summary += f"   Status: {status} | Assignee: {assignee_name}\n\n"

    # Add pagination information
    if len(issues) > display_count:
        summary += (
            f"... and {len(issues) - display_count} more issues on this page.\n\n"
        )

    summary += f"Showing issues {start_at + 1}-{start_at + display_count} of {total} total issues (page {page}).\n"
    summary += "Use the 'page' parameter to navigate between pages and 'limit' to adjust how many issues are displayed."

    return summary


def create_server(context: ServerContext) -> Server:
    """Create and configure the MCP server with handlers that use the context."""
    server = Server("jayrah")

    @server.list_resources()
    async def handle_list_resources() -> List[types.Resource]:
        """List all available Jira boards as resources."""
        return [
            _create_board_resource(board) for board in context.wconfig.get("boards", [])
        ]

    @server.read_resource()
    async def handle_read_resource(uri: AnyUrl) -> str:
        """Read a specific resource by its URI."""
        if uri.scheme != "jira":
            raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

        # Ensure uri.path is not None before attempting to use lstrip
        path = uri.path or ""
        parts = path.lstrip("/").split("/")
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
        jql, order_by = boards.check(board_name, context.wconfig)
        if not jql or not order_by:
            return json.dumps({"error": f"Invalid board or missing JQL: {board_name}"})

        issues = context.boards_obj.issues_client.list_issues(jql, order_by=order_by)
        return json.dumps({"board": board_name, "issues": issues})

    async def _read_issue_resource(issue_key: str) -> str:
        """Read and return details of a specific issue."""
        try:
            issue = context.boards_obj.jira.get_issue(issue_key)
            return json.dumps(issue)
        except AttributeError as e:
            return json.dumps(
                {"error": f"Attribute error fetching issue {issue_key}: {str(e)}"}
            )
        except Exception as e:  # pylint: disable=W0718
            return json.dumps({"error": f"Error fetching issue {issue_key}: {str(e)}"})

    @server.list_prompts()
    async def handle_list_prompts() -> List[types.Prompt]:
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
        name: str, arguments: Dict[str, str] | None
    ) -> types.GetPromptResult:
        """Generate a prompt by combining arguments with server state."""
        if name == "analyze-jira-issue":
            return await _generate_analyze_issue_prompt(arguments or {})

        raise ValueError(f"Unknown prompt: {name}")

    async def _generate_analyze_issue_prompt(
        arguments: Dict[str, str],
    ) -> types.GetPromptResult:
        """Generate a prompt to analyze a Jira issue."""
        issue_key = arguments.get("issue_key")
        if not issue_key:
            raise ValueError("Missing required argument: issue_key")

        try:
            issue = context.boards_obj.jira.get_issue(issue_key)
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
    async def handle_list_tools() -> List[types.Tool]:
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
                        "assignee": {
                            "type": "string",
                            "description": "Assignee username",
                        },
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
            # Comprehensive Jira search
            types.Tool(
                name="search",
                description="Comprehensive search across Jira issues with flexible JQL field filtering",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "jql": {
                            "type": "string",
                            "description": "Custom JQL query string (takes precedence over other parameters if provided)",
                        },
                        "text": {
                            "type": "string",
                            "description": "Text to search in summary and description fields",
                        },
                        "project": {
                            "type": "string",
                            "description": "Project key to filter by (e.g., 'PROJ')",
                        },
                        "status": {
                            "type": "string",
                            "description": "Status to filter by (e.g., 'In Progress', 'Done')",
                        },
                        "assignee": {
                            "type": "string",
                            "description": "Assignee username or email to filter by",
                        },
                        "reporter": {
                            "type": "string",
                            "description": "Reporter username or email to filter by",
                        },
                        "priority": {
                            "type": "string",
                            "description": "Priority to filter by (e.g., 'High', 'Critical')",
                        },
                        "issue_type": {
                            "type": "string",
                            "description": "Issue type to filter by (e.g., 'Bug', 'Story')",
                        },
                        "components": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of component names to filter by",
                        },
                        "labels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of labels to filter by",
                        },
                        "created_after": {
                            "type": "string",
                            "description": "Filter issues created after this date (YYYY-MM-DD format)",
                        },
                        "created_before": {
                            "type": "string",
                            "description": "Filter issues created before this date (YYYY-MM-DD format)",
                        },
                        "updated_after": {
                            "type": "string",
                            "description": "Filter issues updated after this date (YYYY-MM-DD format)",
                        },
                        "updated_before": {
                            "type": "string",
                            "description": "Filter issues updated before this date (YYYY-MM-DD format)",
                        },
                        "fix_version": {
                            "type": "string",
                            "description": "Fix version to filter by",
                        },
                        "affects_version": {
                            "type": "string",
                            "description": "Affects version to filter by",
                        },
                        "epic": {
                            "type": "string",
                            "description": "Epic key or name to filter by",
                        },
                        "sprint": {
                            "type": "string",
                            "description": "Sprint name to filter by",
                        },
                        "custom_fields": {
                            "type": "object",
                            "description": "Custom field filters as key-value pairs (e.g., {'customfield_10001': 'value'})",
                            "additionalProperties": {"type": "string"},
                        },
                        "order_by": {
                            "type": "string",
                            "description": "Field to order results by (e.g., 'created', 'updated', 'priority')",
                        },
                        "order_direction": {
                            "type": "string",
                            "enum": ["ASC", "DESC"],
                            "description": "Sort direction (ASC or DESC, default: DESC)",
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
                },
            ),
        ]

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: Dict | None
    ) -> Sequence[ContentType]:
        """Handle tool execution requests, mapping to Jira CLI commands."""
        tool_handlers = {
            "browse": _handle_browse,
            "create-issue": _handle_create_issue,
            "view-issue": _handle_view_issue,
            "transition-issue": _handle_transition_issue,
            "get-transitions": _handle_get_transitions,
            "open-issue": _handle_open_issue,
            "list-boards": _handle_list_boards,
            "search": _handle_search,
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

    async def _handle_browse(arguments: Dict) -> Sequence[ContentType]:
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

        jql, order_by = boards.check(board, context.wconfig)
        if not jql or not order_by:
            return [
                types.TextContent(
                    type="text", text=f"Invalid board or missing JQL: {board}"
                )
            ]

        # Use the common function to build the search JQL
        jql = boards.build_search_jql(
            jql, search_terms, use_or, context.wconfig.get("verbose", False), filters
        )

        # Calculate start_at based on page number (0-indexed for the API)
        start_at = (page - 1) * page_size

        # Always fetch a single page at a time for pagination control
        issues = context.boards_obj.issues_client.list_issues(
            jql, order_by=order_by, limit=page_size, all_pages=False, start_at=start_at
        )

        # If we have issues returned, try to get the total count from the metadata
        if issues:
            # This is a bit of a hack since Jira API doesn't return total with the issues
            # We need to use search_issues directly to get the total
            try:
                result = context.boards_obj.jira.search_issues(
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

    async def _handle_create_issue(arguments: Dict) -> Sequence[ContentType]:
        """Handle the create-issue tool to create a new Jira issue."""
        issuetype = arguments.get("issuetype", "Story")
        summary = arguments.get("summary")
        description = arguments.get("description")
        priority = arguments.get("priority")
        assignee = arguments.get("assignee")
        labels = arguments.get("labels")

        if not summary:
            raise ValueError("Summary is required")

        result = context.boards_obj.jira.create_issue(
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

    async def _handle_view_issue(arguments: Dict) -> Sequence[ContentType]:
        """Handle the view-issue tool to view details of a specific Jira issue."""
        ticket = arguments.get("ticket")
        if not ticket:
            raise ValueError("Ticket key is required")

        issue = context.boards_obj.jira.get_issue(ticket)
        formatted_issue = _format_issue_details(ticket, issue)
        return [types.TextContent(type="text", text=formatted_issue)]

    async def _handle_transition_issue(arguments: Dict) -> Sequence[ContentType]:
        """Handle the transition-issue tool to transition a Jira issue to a new status."""
        ticket = arguments.get("ticket")
        transition_id = arguments.get("transition_id")

        if not ticket or not transition_id:
            raise ValueError("Ticket key and transition ID are required")

        # This could be improved to handle the actual return value of transition_issue
        context.boards_obj.jira.transition_issue(ticket, transition_id)

        return [
            types.TextContent(
                type="text",
                text=f"Successfully transitioned issue {ticket} with transition ID {transition_id}",
            )
        ]

    async def _handle_get_transitions(arguments: Dict) -> Sequence[ContentType]:
        """Handle the get-transitions tool to get available transitions for a Jira issue."""
        ticket = arguments.get("ticket")
        if not ticket:
            raise ValueError("Ticket key is required")

        transitions = context.boards_obj.jira.get_transitions(ticket)
        formatted_transitions = _format_transitions(ticket, transitions)

        return [types.TextContent(type="text", text=formatted_transitions)]

    async def _handle_open_issue(arguments: Dict) -> Sequence[ContentType]:
        """Handle the open-issue tool to get URL to open a Jira issue in browser."""
        ticket = arguments.get("ticket")
        if not ticket:
            raise ValueError("Ticket key is required")

        url = utils.make_full_url(ticket, context.wconfig.get("jira_server"))
        return [types.TextContent(type="text", text=f"URL for {ticket}: {url}")]

    async def _handle_list_boards(arguments: Dict) -> Sequence[ContentType]:
        """Handle the list-boards tool to list all available Jira boards."""
        # Format board information
        formatted_boards = "Available boards:\n\n"
        for board in context.wconfig.get("boards", []):
            board_name = board.get("name", "Unnamed")
            description = board.get("description", "No description")
            formatted_boards += f"* {board_name}: {description}\n"

        return [types.TextContent(type="text", text=formatted_boards)]

    async def _handle_search(arguments: Dict) -> Sequence[ContentType]:
        """Handle the search tool for comprehensive Jira issue searching."""
        # Get search parameters
        custom_jql = arguments.get("jql")
        text = arguments.get("text")
        project = arguments.get("project")
        status = arguments.get("status")
        assignee = arguments.get("assignee")
        reporter = arguments.get("reporter")
        priority = arguments.get("priority")
        issue_type = arguments.get("issue_type")
        components = arguments.get("components", [])
        labels = arguments.get("labels", [])
        created_after = arguments.get("created_after")
        created_before = arguments.get("created_before")
        updated_after = arguments.get("updated_after")
        updated_before = arguments.get("updated_before")
        fix_version = arguments.get("fix_version")
        affects_version = arguments.get("affects_version")
        epic = arguments.get("epic")
        sprint = arguments.get("sprint")
        custom_fields = arguments.get("custom_fields", {})
        order_by = arguments.get("order_by", "updated")
        order_direction = arguments.get("order_direction", "DESC")
        limit = arguments.get("limit", 10)
        page = arguments.get("page", 1)
        page_size = arguments.get("page_size", 100)

        # If custom JQL is provided, use it directly
        if custom_jql:
            jql = custom_jql
        else:
            # Build JQL from individual parameters
            jql_parts = []

            # Project filter
            if project:
                jql_parts.append(f'project = "{project}"')

            # Text search in summary and description
            if text:
                jql_parts.append(f'(summary ~ "{text}" OR description ~ "{text}")')

            # Status filter
            if status:
                jql_parts.append(f'status = "{status}"')

            # Assignee filter
            if assignee:
                jql_parts.append(f'assignee = "{assignee}"')

            # Reporter filter
            if reporter:
                jql_parts.append(f'reporter = "{reporter}"')

            # Priority filter
            if priority:
                jql_parts.append(f'priority = "{priority}"')

            # Issue type filter
            if issue_type:
                jql_parts.append(f'issuetype = "{issue_type}"')

            # Components filter
            if components:
                comp_filters = []
                for comp in components:
                    comp_filters.append(f'component = "{comp}"')
                if comp_filters:
                    jql_parts.append(f"({' OR '.join(comp_filters)})")

            # Labels filter
            if labels:
                label_filters = []
                for label in labels:
                    label_filters.append(f'labels = "{label}"')
                if label_filters:
                    jql_parts.append(f"({' AND '.join(label_filters)})")

            # Date filters
            if created_after:
                jql_parts.append(f'created >= "{created_after}"')
            if created_before:
                jql_parts.append(f'created <= "{created_before}"')
            if updated_after:
                jql_parts.append(f'updated >= "{updated_after}"')
            if updated_before:
                jql_parts.append(f'updated <= "{updated_before}"')

            # Version filters
            if fix_version:
                jql_parts.append(f'fixVersion = "{fix_version}"')
            if affects_version:
                jql_parts.append(f'affectedVersion = "{affects_version}"')

            # Epic filter
            if epic:
                # Try both epic key and epic name formats
                jql_parts.append(f'("Epic Link" = "{epic}" OR "Epic Name" ~ "{epic}")')

            # Sprint filter
            if sprint:
                jql_parts.append(f'Sprint = "{sprint}"')

            # Custom fields
            for field, value in custom_fields.items():
                jql_parts.append(f'{field} = "{value}"')

            # Combine all parts with AND
            if jql_parts:
                jql = " AND ".join(jql_parts)
            else:
                # Default search if no criteria provided
                jql = "order by updated DESC"

        # Add ordering if not already in the JQL
        if "order by" not in jql.lower():
            jql += f" ORDER BY {order_by} {order_direction}"

        # Calculate pagination
        start_at = (page - 1) * page_size

        try:
            # Execute the search
            result = context.boards_obj.jira.search_issues(
                jql, start_at=start_at, max_results=page_size
            )

            issues = result.get("issues", [])
            total = result.get("total", 0)

            # Format the results
            summary_text = _format_search_results(
                jql, issues, total, limit, page, page_size, start_at
            )

            return [types.TextContent(type="text", text=summary_text)]

        except Exception as e:
            return [
                types.TextContent(
                    type="text", text=f"Error executing search: {str(e)}\nJQL: {jql}"
                )
            ]

    return server


async def main(config_file=None):
    """Start and run the MCP server using stdin/stdout streams."""
    # Initialize context with config file
    context = ServerContext(config_file)

    # Create server with the context
    server = create_server(context)

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
