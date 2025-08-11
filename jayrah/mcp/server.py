"""MCP server exposing Jira primitives (projects, issues, search, etc.)."""
# pylint: disable=protected-access

import json
from typing import Dict, List, Sequence, TypeVar, Union

import mcp.server.stdio
from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from pydantic import AnyUrl

from jayrah import config
from jayrah.api import jira_client as jirahttp

from .. import utils

# Type definition for content return types
ContentType = Union[types.TextContent, types.ImageContent, types.EmbeddedResource]
T = TypeVar("T")


class ServerContext:
    """Context class holding config and a Jira client."""

    def __init__(self, config_file=None):
        """Initialize the server context with config and Jira client."""
        self.config_file = config_file or config.defaults.CONFIG_FILE
        self.wconfig = config.make_config({}, self.config_file)

        api_version = self.wconfig.get("api_version") or config.defaults.API_VERSION
        auth_method = self.wconfig.get("auth_method") or "bearer"
        self.jira = jirahttp.JiraHTTP(
            self.wconfig, api_version=api_version, auth_method=auth_method
        )


def _create_project_resource(project: Dict) -> types.Resource:
    """Create a resource object for a Jira project."""
    key = project.get("key", "")
    name = project.get("name", key)
    description = project.get("description", f"Jira project: {key}")

    return types.Resource(
        uri=AnyUrl(f"jira://project/{key}"),
        name=f"Project: {name}",
        description=description,
        mimeType="application/json",
    )


def _create_board_resource(board: Dict) -> types.Resource:
    """Backward-compat resource for a Jira board.

    Kept to satisfy existing tests; new server exposes projects instead.
    """
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
        # Format terms with AND/OR for display
        operator = " OR " if use_or else " AND "
        terms_text = operator.join(f"'{t}'" for t in search_terms)
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
    """Create and configure the MCP server exposing Jira primitives."""
    server = Server("jayrah")

    @server.list_resources()
    async def handle_list_resources() -> List[types.Resource]:
        """List Jira projects as resources."""
        # Try v3 project search first; fallback to v2 projects list
        resources: List[types.Resource] = []
        try:
            projects = context.jira._request(
                "GET", "project/search", params={"maxResults": 1000}
            )
            values = projects.get("values") or projects.get("projects") or []
            for p in values:
                resources.append(_create_project_resource(p))
        except Exception:
            # Fallback: v2 returns an array for GET /project
            try:
                projects = context.jira._request("GET", "project")
                if isinstance(projects, list):
                    for p in projects:
                        resources.append(_create_project_resource(p))
            except Exception:
                pass
        return resources

    @server.read_resource()
    async def handle_read_resource(uri: AnyUrl) -> str:
        """Read a specific resource by its URI."""
        if uri.scheme != "jira":
            raise ValueError(f"Unsupported URI scheme: {uri.scheme}")

        path = uri.path or ""
        parts = path.lstrip("/").split("/")
        if len(parts) < 2:
            raise ValueError(f"Invalid URI format: {uri}")

        resource_type = parts[0]
        resource_id = parts[1]

        if resource_type == "project":
            return await _read_project_resource(context, resource_id)
        if resource_type == "issue":
            return await _read_issue_resource(context, resource_id)
        raise ValueError(f"Unsupported resource type: {resource_type}")

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
            return await _generate_analyze_issue_prompt(context, arguments or {})

        raise ValueError(f"Unknown prompt: {name}")

    @server.list_tools()
    async def handle_list_tools() -> List[types.Tool]:
        """
        List Jira-native tools mapping to common REST operations.
        Each tool specifies its arguments using JSON Schema validation.
        """
        return [
            # List projects
            types.Tool(
                name="list-projects",
                description="List Jira projects",
                inputSchema={"type": "object", "properties": {}},
            ),
            # Create Jira issue
            types.Tool(
                name="create-issue",
                description="Create a new Jira issue",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project key (defaults to config if omitted)",
                        },
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
                        "components": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of components",
                        },
                    },
                    "required": ["issuetype", "summary"],
                },
            ),
            # Update Jira issue
            types.Tool(
                name="update-issue",
                description="Update fields on a Jira issue",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticket": {"type": "string", "description": "Issue key"},
                        "fields": {
                            "type": "object",
                            "description": "Fields to update as key-value pairs",
                            "additionalProperties": True,
                        },
                    },
                    "required": ["ticket", "fields"],
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
            # Add a comment to an issue
            types.Tool(
                name="add-comment",
                description="Add a comment to a Jira issue",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticket": {"type": "string", "description": "Issue key"},
                        "comment": {"type": "string", "description": "Comment text"},
                    },
                    "required": ["ticket", "comment"],
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
            # Metadata helpers
            types.Tool(
                name="list-issue-types",
                description="List available issue types",
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="list-priorities",
                description="List available priorities",
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="list-users",
                description="List Jira users (first 1000)",
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="list-labels",
                description="List labels in project (from config)",
                inputSchema={"type": "object", "properties": {}},
            ),
            types.Tool(
                name="list-components",
                description="List components in project (from config)",
                inputSchema={"type": "object", "properties": {}},
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
            # New: Assign issue
            types.Tool(
                name="assign-issue",
                description="Assign an issue to a user",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticket": {"type": "string", "description": "Issue key"},
                        "assignee": {
                            "type": "string",
                            "description": "User identifier (name or accountId)",
                        },
                    },
                    "required": ["ticket", "assignee"],
                },
            ),
            # New: Add labels to an issue
            types.Tool(
                name="add-labels",
                description="Add labels to an issue (keeps existing)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticket": {"type": "string", "description": "Issue key"},
                        "labels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Labels to add",
                        },
                    },
                    "required": ["ticket", "labels"],
                },
            ),
            # New: Remove labels from an issue
            types.Tool(
                name="remove-labels",
                description="Remove labels from an issue",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticket": {"type": "string", "description": "Issue key"},
                        "labels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Labels to remove",
                        },
                    },
                    "required": ["ticket", "labels"],
                },
            ),
            # New: Link two issues
            types.Tool(
                name="link-issues",
                description="Create an issue link between two issues",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "inward": {"type": "string", "description": "Inward issue key"},
                        "outward": {
                            "type": "string",
                            "description": "Outward issue key",
                        },
                        "link_type": {
                            "type": "string",
                            "description": "Link type (e.g., Relates, Blocks)",
                        },
                        "comment": {
                            "type": "string",
                            "description": "Optional comment for the link",
                        },
                    },
                    "required": ["inward", "outward"],
                },
            ),
            # New: Get issue comments
            types.Tool(
                name="get-comments",
                description="List comments on an issue",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticket": {"type": "string", "description": "Issue key"},
                        "limit": {"type": "integer", "description": "Max comments"},
                        "page": {"type": "integer", "description": "Page number (1)"},
                        "page_size": {
                            "type": "integer",
                            "description": "Comments per page",
                        },
                    },
                    "required": ["ticket"],
                },
            ),
            # New: Edit a comment
            types.Tool(
                name="edit-comment",
                description="Edit an existing comment on an issue",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticket": {"type": "string", "description": "Issue key"},
                        "comment_id": {
                            "type": "string",
                            "description": "ID of the comment to edit",
                        },
                        "comment": {
                            "type": "string",
                            "description": "The new comment text",
                        },
                    },
                    "required": ["ticket", "comment_id", "comment"],
                },
            ),
            # New: Delete a comment
            types.Tool(
                name="delete-comment",
                description="Delete a comment from an issue",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticket": {"type": "string", "description": "Issue key"},
                        "comment_id": {
                            "type": "string",
                            "description": "ID of the comment to delete",
                        },
                    },
                    "required": ["ticket", "comment_id"],
                },
            ),
            # New: Log work on an issue
            types.Tool(
                name="log-work",
                description="Add a worklog entry to an issue",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticket": {"type": "string", "description": "Issue key"},
                        "time_spent": {
                            "type": "string",
                            "description": "Time spent, e.g., '1h 30m'",
                        },
                        "comment": {
                            "type": "string",
                            "description": "Optional worklog comment",
                        },
                        "started": {
                            "type": "string",
                            "description": "Optional start time (YYYY-MM-DDTHH:MM:SS.sssZ)",
                        },
                    },
                    "required": ["ticket", "time_spent"],
                },
            ),
            # New: Get issue changelog
            types.Tool(
                name="get-changelog",
                description="Retrieve an issue's change history",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "ticket": {"type": "string", "description": "Issue key"},
                        "limit": {
                            "type": "integer",
                            "description": "Max items to display",
                        },
                        "page": {"type": "integer", "description": "Page number (1)"},
                        "page_size": {
                            "type": "integer",
                            "description": "Items per page",
                        },
                    },
                    "required": ["ticket"],
                },
            ),
        ]

    tool_handlers = {
        "list-projects": _handle_list_projects,
        "create-issue": _handle_create_issue,
        "update-issue": _handle_update_issue,
        "view-issue": _handle_view_issue,
        "transition-issue": _handle_transition_issue,
        "get-transitions": _handle_get_transitions,
        "add-comment": _handle_add_comment,
        "open-issue": _handle_open_issue,
        "search": _handle_search,
        "list-issue-types": _handle_list_issue_types,
        "list-priorities": _handle_list_priorities,
        "list-users": _handle_list_users,
        "list-labels": _handle_list_labels,
        "list-components": _handle_list_components,
        "assign-issue": _handle_assign_issue,
        "add-labels": _handle_add_labels,
        "remove-labels": _handle_remove_labels,
        "link-issues": _handle_link_issues,
        "get-comments": _handle_get_comments,
        "edit-comment": _handle_edit_comment,
        "delete-comment": _handle_delete_comment,
        "log-work": _handle_log_work,
        "get-changelog": _handle_get_changelog,
    }

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: Dict | None
    ) -> Sequence[ContentType]:
        """Handle tool execution requests."""
        try:
            handler = tool_handlers.get(name)
            if not handler:
                raise ValueError(f"Unknown tool: {name}")

            return await handler(context, arguments or {})
        except Exception as e:  # pylint: disable=W0718
            return [
                types.TextContent(
                    type="text", text=f"Error executing tool '{name}': {str(e)}"
                )
            ]

    return server


async def _read_project_resource(context: ServerContext, project_key: str) -> str:
    """Read and return details of a specific project."""
    try:
        project = context.jira._request("GET", f"project/{project_key}")
        return json.dumps(project)
    except Exception as e:  # pylint: disable=W0718
        return json.dumps({"error": f"Error fetching project {project_key}: {str(e)}"})


async def _read_issue_resource(context: ServerContext, issue_key: str) -> str:
    """Read and return details of a specific issue."""
    try:
        issue = context.jira.get_issue(issue_key)
        return json.dumps(issue)
    except AttributeError as e:
        return json.dumps(
            {"error": f"Attribute error fetching issue {issue_key}: {str(e)}"}
        )
    except Exception as e:  # pylint: disable=W0718
        return json.dumps({"error": f"Error fetching issue {issue_key}: {str(e)}"})


async def _generate_analyze_issue_prompt(
    context: ServerContext,
    arguments: Dict[str, str],
) -> types.GetPromptResult:
    """Generate a prompt to analyze a Jira issue."""
    issue_key = arguments.get("issue_key")
    if not issue_key:
        raise ValueError("Missing required argument: issue_key")

    try:
        issue = context.jira.get_issue(issue_key)
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


async def _handle_list_projects(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """List Jira projects."""
    try:
        projects = context.jira._request(
            "GET", "project/search", params={"maxResults": 1000}
        )
        values = projects.get("values") or projects.get("projects") or []
    except Exception:
        values = context.jira._request("GET", "project")
        if not isinstance(values, list):
            values = []

    lines = ["Projects:"]
    for p in values:
        key = p.get("key", "")
        name = p.get("name", key)
        lines.append(f"- {key}: {name}")
    return [types.TextContent(type="text", text="\n".join(lines))]


async def _handle_create_issue(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """Handle the create-issue tool to create a new Jira issue."""
    project = arguments.get("project") or context.jira.config.get("jira_project")
    issuetype = arguments.get("issuetype", "Story")
    summary = arguments.get("summary")
    description = arguments.get("description")
    priority = arguments.get("priority")
    assignee = arguments.get("assignee")
    labels = arguments.get("labels")
    components = arguments.get("components") or []

    if not summary:
        raise ValueError("Summary is required")

    # Temporarily override project if provided
    original_project = context.jira.config.get("jira_project")
    if project:
        context.jira.config["jira_project"] = project

    result = context.jira.create_issue(
        issuetype=issuetype,
        summary=summary,
        description=description,
        priority=priority,
        assignee=assignee,
        labels=labels,
        components=components,
    )

    # Restore original project in config
    context.jira.config["jira_project"] = original_project

    issue_key = result.get("key", "Unknown")
    return [
        types.TextContent(
            type="text",
            text=f"Created issue {issue_key} successfully.\nSummary: {summary}",
        )
    ]


async def _handle_update_issue(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """Update fields on an issue."""
    ticket = arguments.get("ticket")
    fields = arguments.get("fields", {})
    if not ticket:
        raise ValueError("Ticket key is required")
    if not isinstance(fields, dict) or not fields:
        raise ValueError("Fields must be a non-empty object")
    context.jira.update_issue(ticket, fields)
    return [
        types.TextContent(
            type="text", text=f"Updated {ticket} fields: {', '.join(fields.keys())}"
        )
    ]


async def _handle_view_issue(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """Handle the view-issue tool to view details of a specific Jira issue."""
    ticket = arguments.get("ticket")
    if not ticket:
        raise ValueError("Ticket key is required")

    issue = context.jira.get_issue(ticket)
    formatted_issue = _format_issue_details(ticket, issue)
    return [types.TextContent(type="text", text=formatted_issue)]


async def _handle_transition_issue(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """Handle the transition-issue tool to transition a Jira issue to a new status."""
    ticket = arguments.get("ticket")
    transition_id = arguments.get("transition_id")

    if not ticket or not transition_id:
        raise ValueError("Ticket key and transition ID are required")

    # This could be improved to handle the actual return value of transition_issue
    context.jira.transition_issue(ticket, transition_id)

    return [
        types.TextContent(
            type="text",
            text=f"Successfully transitioned issue {ticket} with transition ID {transition_id}",
        )
    ]


async def _handle_get_transitions(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """Handle the get-transitions tool to get available transitions for a Jira issue."""
    ticket = arguments.get("ticket")
    if not ticket:
        raise ValueError("Ticket key is required")

    transitions = context.jira.get_transitions(ticket)
    formatted_transitions = _format_transitions(ticket, transitions)

    return [types.TextContent(type="text", text=formatted_transitions)]


async def _handle_add_comment(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """Add a comment to an issue."""
    ticket = arguments.get("ticket")
    comment = arguments.get("comment")
    if not ticket or not comment:
        raise ValueError("Ticket and comment are required")
    context.jira.add_comment(ticket, comment)
    return [types.TextContent(type="text", text=f"Added comment to {ticket}")]


async def _handle_open_issue(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """Handle the open-issue tool to get URL to open a Jira issue in browser."""
    ticket = arguments.get("ticket")
    if not ticket:
        raise ValueError("Ticket key is required")

    url = utils.make_full_url(ticket, context.wconfig.get("jira_server"))
    return [types.TextContent(type="text", text=f"URL for {ticket}: {url}")]


async def _handle_assign_issue(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """Assign an issue to a user (supports accountId/name)."""
    ticket = arguments.get("ticket")
    assignee = arguments.get("assignee")
    if not ticket or not assignee:
        raise ValueError("Ticket and assignee are required")
    assignee_payload = context.jira.formatter.format_assignee(assignee)
    context.jira.update_issue(ticket, {"assignee": assignee_payload})
    return [types.TextContent(type="text", text=f"Assigned {ticket} to {assignee}")]


async def _handle_add_labels(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """Add labels to an issue, preserving existing labels."""
    ticket = arguments.get("ticket")
    labels = arguments.get("labels") or []
    if not ticket or not labels:
        raise ValueError("Ticket and labels are required")
    issue = context.jira.get_issue(ticket, fields=["labels"], use_cache=False)
    current = set(issue.get("fields", {}).get("labels", []) or [])
    updated = sorted(current.union(set(labels)))
    context.jira.update_issue(ticket, {"labels": updated})
    return [
        types.TextContent(
            type="text", text=f"Updated {ticket} labels: {', '.join(updated)}"
        )
    ]


async def _handle_remove_labels(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """Remove labels from an issue."""
    ticket = arguments.get("ticket")
    labels = set(arguments.get("labels") or [])
    if not ticket or not labels:
        raise ValueError("Ticket and labels are required")
    issue = context.jira.get_issue(ticket, fields=["labels"], use_cache=False)
    current = set(issue.get("fields", {}).get("labels", []) or [])
    updated = sorted(current.difference(labels))
    context.jira.update_issue(ticket, {"labels": updated})
    return [
        types.TextContent(
            type="text", text=f"Updated {ticket} labels: {', '.join(updated)}"
        )
    ]


async def _handle_link_issues(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """Link two issues using a link type (default: Relates)."""
    inward = arguments.get("inward")
    outward = arguments.get("outward")
    link_type = arguments.get("link_type") or "Relates"
    comment = arguments.get("comment")
    if not inward or not outward:
        raise ValueError("Both inward and outward issue keys are required")
    payload: Dict = {
        "type": {"name": link_type},
        "inwardIssue": {"key": inward},
        "outwardIssue": {"key": outward},
    }
    if comment:
        payload["comment"] = context.jira.formatter.format_comment(comment)
    context.jira._request("POST", "issueLink", jeez=payload)
    return [
        types.TextContent(
            type="text",
            text=f"Linked {inward} -[{link_type}]-> {outward}",
        )
    ]


async def _handle_get_comments(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """List comments on an issue with pagination."""
    ticket = arguments.get("ticket")
    limit = int(arguments.get("limit", 20))
    page = int(arguments.get("page", 1))
    page_size = int(arguments.get("page_size", 50))
    if not ticket:
        raise ValueError("Ticket key is required")
    start_at = (page - 1) * page_size
    data = context.jira._request(
        "GET",
        f"issue/{ticket}/comment",
        params={"startAt": start_at, "maxResults": page_size},
        use_cache=False,
    )
    comments = data.get("comments", [])
    total = data.get("total", len(comments))
    shown = min(limit, len(comments))
    lines = [f"Comments for {ticket} (showing {shown} of {total}):\n"]
    for c in comments[:shown]:
        comment_id = c.get("id")
        author = (
            c.get("author", {}).get("displayName")
            or c.get("author", {}).get("name")
            or "Unknown"
        )
        body = c.get("body")
        lines.append(f"- ID: {comment_id} | {author}: {body}")
    lines.append(
        f"\nShowing comments {start_at + 1}-{start_at + shown} of {total} (page {page})."
    )
    return [types.TextContent(type="text", text="\n".join(lines))]


async def _handle_edit_comment(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """Edit an existing comment."""
    ticket = arguments.get("ticket")
    comment_id = arguments.get("comment_id")
    comment = arguments.get("comment")
    if not ticket or not comment_id or not comment:
        raise ValueError("Ticket, comment_id, and comment are required")
    body = context.jira.formatter.format_comment(comment)
    context.jira._request(
        "PUT", f"issue/{ticket}/comment/{comment_id}", jeez={"body": body}
    )
    return [
        types.TextContent(type="text", text=f"Edited comment {comment_id} on {ticket}")
    ]


async def _handle_delete_comment(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """Delete a comment."""
    ticket = arguments.get("ticket")
    comment_id = arguments.get("comment_id")
    if not ticket or not comment_id:
        raise ValueError("Ticket and comment_id are required")
    context.jira._request("DELETE", f"issue/{ticket}/comment/{comment_id}")
    return [
        types.TextContent(
            type="text", text=f"Deleted comment {comment_id} from {ticket}"
        )
    ]


async def _handle_log_work(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """Add a worklog entry to an issue."""
    ticket = arguments.get("ticket")
    time_spent = arguments.get("time_spent")
    comment = arguments.get("comment")
    started = arguments.get("started")
    if not ticket or not time_spent:
        raise ValueError("Ticket and time_spent are required")
    payload: Dict = {"timeSpent": time_spent}
    if comment:
        payload["comment"] = context.jira.formatter.format_comment(comment)
    if started:
        payload["started"] = started
    res = context.jira._request("POST", f"issue/{ticket}/worklog", jeez=payload)
    time_str = res.get("timeSpent", time_spent)
    return [
        types.TextContent(
            type="text",
            text=f"Logged {time_str} on {ticket}"
            + (" with comment" if comment else ""),
        )
    ]


async def _handle_get_changelog(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """Retrieve and format an issue's change history."""
    ticket = arguments.get("ticket")
    limit = int(arguments.get("limit", 20))
    page = int(arguments.get("page", 1))
    page_size = int(arguments.get("page_size", 50))
    if not ticket:
        raise ValueError("Ticket key is required")
    start_at = (page - 1) * page_size
    data = context.jira._request(
        "GET",
        f"issue/{ticket}/changelog",
        params={"startAt": start_at, "maxResults": page_size},
        use_cache=False,
    )
    histories = data.get("values") or data.get("histories") or []
    total = data.get("total", len(histories))
    shown = min(limit, len(histories))
    lines = [f"Changelog for {ticket} (showing {shown} of {total}):\n"]
    for h in histories[:shown]:
        author = (
            h.get("author", {}).get("displayName")
            or h.get("author", {}).get("name")
            or "Unknown"
        )
        created = h.get("created", "")
        lines.append(f"- {created} by {author}")
        for item in h.get("items", []):
            field = item.get("field") or item.get("fieldId") or "field"
            from_str = item.get("fromString") or item.get("from") or ""
            to_str = item.get("toString") or item.get("to") or ""
            lines.append(f"    {field}: '{from_str}' -> '{to_str}'")
    lines.append(
        f"\nShowing changes {start_at + 1}-{start_at + shown} of {total} (page {page})."
    )
    return [types.TextContent(type="text", text="\n".join(lines))]


async def _handle_list_issue_types(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """List issue types."""
    its = context.jira.get_issue_types()
    lines = ["Issue types:"]
    for name, _id in its.items():
        lines.append(f"- {name} ({_id})")
    return [types.TextContent(type="text", text="\n".join(lines))]


async def _handle_list_priorities(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """List priorities."""
    prios = context.jira.get_priorities()
    items = prios if isinstance(prios, list) else prios.get("values", [])
    lines = ["Priorities:"]
    for p in items:
        name = p.get("name") if isinstance(p, dict) else str(p)
        lines.append(f"- {name}")
    return [types.TextContent(type="text", text="\n".join(lines))]


async def _handle_list_users(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """List users (first 1000)."""
    users = context.jira.get_users()
    lines = ["Users:"]
    for u in users:
        display = u.get("displayName", "")
        account_id = u.get("accountId", u.get("name", ""))
        lines.append(f"- {display} ({account_id})")
    return [types.TextContent(type="text", text="\n".join(lines))]


async def _handle_list_labels(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """List labels in configured project."""
    labels = context.jira.get_labels()
    lines = ["Labels:"]
    for label in labels:
        lines.append(f"- {label}")
    return [types.TextContent(type="text", text="\n".join(lines))]


async def _handle_list_components(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
    """List components in configured project."""
    comps = context.jira.get_components()
    lines = ["Components:"]
    for c in comps:
        lines.append(f"- {c}")
    return [types.TextContent(type="text", text="\n".join(lines))]


async def _handle_search(
    context: ServerContext, arguments: Dict
) -> Sequence[ContentType]:
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
        result = context.jira.search_issues(
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
