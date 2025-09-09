"""Simplified unit tests for the MCP server implementation."""

from unittest.mock import MagicMock, patch

import pytest
from mcp import types
from pydantic import AnyUrl

from jayrah.mcp import server as mcp_server
from jayrah.mcp.server import (
    ServerContext,
    _create_board_resource,
    _create_project_resource,
    _format_issue_details,
    _format_issues_summary,
    _format_transitions,
    create_server,
)


@pytest.fixture
def mock_context():
    """Create a mock ServerContext."""
    context = MagicMock(spec=ServerContext)
    context.wconfig = {
        "jira_server": "https://test.jira.com",
        "verbose": False,
    }
    context.jira = MagicMock()
    context.jira.formatter = MagicMock()
    return context


class TestServerContext:
    """Test the ServerContext class."""

    @patch("jayrah.mcp.server.config.make_config")
    @patch("jayrah.mcp.server.jirahttp.JiraHTTP")
    def test_init_with_default_config(self, mock_jira, mock_make_config):
        """Test ServerContext initialization with default config file."""
        mock_config = {"boards": [], "jira_server": "https://test.jira.com"}
        mock_make_config.return_value = mock_config
        mock_jira_instance = MagicMock()
        mock_jira.return_value = mock_jira_instance

        context = ServerContext()

        mock_make_config.assert_called_once()
        assert context.wconfig == mock_config
        assert context.jira == mock_jira_instance

    @patch("jayrah.mcp.server.config.make_config")
    @patch("jayrah.mcp.server.jirahttp.JiraHTTP")
    def test_init_with_custom_config(self, mock_jira, mock_make_config):
        """Test ServerContext initialization with custom config file."""
        custom_config_file = "/path/to/custom/config.yaml"
        mock_config = {"boards": [], "jira_server": "https://test.jira.com"}
        mock_make_config.return_value = mock_config

        context = ServerContext(custom_config_file)

        assert context.config_file == custom_config_file
        mock_make_config.assert_called_once_with({}, custom_config_file)


class TestHelperFunctions:
    """Test the helper functions."""

    def test_create_project_resource(self):
        """Test _create_project_resource function."""
        project = {
            "key": "TEST",
            "name": "Test Project",
            "description": "Test project description",
        }

        resource = _create_project_resource(project)

        assert isinstance(resource, types.Resource)
        assert resource.uri == AnyUrl("jira://project/TEST")
        assert resource.name == "Project: Test Project"
        assert resource.description == "Test project description"
        assert resource.mimeType == "application/json"

    def test_create_board_resource_no_description(self):
        """Test _create_board_resource with no description."""
        board = {"name": "test-board"}

        resource = _create_board_resource(board)

        assert resource.description == "Jira board: test-board"

    def test_format_issue_details(self):
        """Test _format_issue_details function."""
        ticket = "TEST-123"
        issue = {
            "fields": {
                "summary": "Test issue summary",
                "description": "Test issue description",
                "status": {"name": "In Progress"},
                "issuetype": {"name": "Bug"},
            }
        }

        result = _format_issue_details(ticket, issue)

        expected_lines = [
            "Issue: TEST-123",
            "Type: Bug",
            "Status: In Progress",
            "Summary: Test issue summary",
            "",
            "Description:",
            "Test issue description",
        ]
        assert result == "\n".join(expected_lines)

    def test_format_issue_details_missing_fields(self):
        """Test _format_issue_details with missing fields."""
        ticket = "TEST-123"
        issue = {"fields": {}}

        result = _format_issue_details(ticket, issue)

        expected_lines = [
            "Issue: TEST-123",
            "Type: Unknown",
            "Status: Unknown",
            "Summary: No summary",
            "",
            "Description:",
            "No description",
        ]
        assert result == "\n".join(expected_lines)

    def test_format_transitions(self):
        """Test _format_transitions function."""
        ticket = "TEST-123"
        transitions = {
            "transitions": [
                {
                    "id": "11",
                    "name": "To Do",
                    "to": {"name": "To Do"},
                },
                {
                    "id": "21",
                    "name": "In Progress",
                    "to": {"name": "In Progress"},
                },
            ]
        }

        result = _format_transitions(ticket, transitions)

        assert "Available transitions for TEST-123:" in result
        assert "ID: 11, Name: To Do, To: To Do" in result
        assert "ID: 21, Name: In Progress, To: In Progress" in result

    def test_format_transitions_empty(self):
        """Test _format_transitions with empty transitions."""
        ticket = "TEST-123"
        transitions = {"transitions": []}

        result = _format_transitions(ticket, transitions)

        assert result == "Available transitions for TEST-123:\n\n"

    def test_format_issues_summary_basic(self):
        """Test _format_issues_summary with basic parameters."""
        board_name = "test-board"
        issues = [
            {
                "key": "TEST-123",
                "fields": {
                    "summary": "Test issue 1",
                    "status": {"name": "In Progress"},
                },
            },
            {
                "key": "TEST-124",
                "fields": {
                    "summary": "Test issue 2",
                    "status": {"name": "To Do"},
                },
            },
        ]

        result = _format_issues_summary(board_name, issues)

        assert "Found 2 issues on board 'test-board'" in result
        assert "1. TEST-123: Test issue 1 (In Progress)" in result
        assert "2. TEST-124: Test issue 2 (To Do)" in result
        assert "Showing issues 1-2" in result

    def test_format_issues_summary_with_search_terms(self):
        """Test _format_issues_summary with search terms."""
        board_name = "test-board"
        issues = [
            {
                "key": "TEST-123",
                "fields": {"summary": "Test", "status": {"name": "Open"}},
            }
        ]
        search_terms = ["bug", "urgent"]

        result = _format_issues_summary(board_name, issues, search_terms=search_terms)

        assert "matching 'bug' AND 'urgent'" in result

    def test_format_issues_summary_with_filters(self):
        """Test _format_issues_summary with filters."""
        board_name = "test-board"
        issues = [
            {
                "key": "TEST-123",
                "fields": {"summary": "Test", "status": {"name": "Open"}},
            }
        ]
        filters = ["status=Open", "priority=High"]

        result = _format_issues_summary(board_name, issues, filters=filters)

        assert "with filters: status=Open AND priority=High" in result

    def test_format_issues_summary_pagination(self):
        """Test _format_issues_summary with pagination."""
        board_name = "test-board"
        issues = [
            {
                "key": "TEST-123",
                "fields": {"summary": "Test 1", "status": {"name": "Open"}},
                "metadata": {"total": 50},
            }
        ]

        result = _format_issues_summary(
            board_name, issues, limit=1, page=2, page_size=10
        )

        assert "Found 50 total issues" in result
        assert "(Page 2, showing 1)" in result
        assert "Showing issues 11-11 of 50 total issues (page 2)" in result

    def test_format_issues_summary_limit_exceeded(self):
        """Test _format_issues_summary when total issues exceed limit."""
        board_name = "test-board"
        issues = [
            {
                "key": f"TEST-{i}",
                "fields": {"summary": f"Test {i}", "status": {"name": "Open"}},
            }
            for i in range(1, 16)  # 15 issues
        ]

        result = _format_issues_summary(board_name, issues, limit=5)

        assert "... and 10 more issues on this page." in result

    def test_format_issues_summary_backward_compatibility(self):
        """Test _format_issues_summary with deprecated search_term parameter."""
        board_name = "test-board"
        issues = [
            {
                "key": "TEST-123",
                "fields": {"summary": "Test", "status": {"name": "Open"}},
            }
        ]
        _format_issues_summary(board_name, issues, search_term="bug")


class TestCreateServer:
    """Test the create_server function."""

    def test_create_server_returns_server(self, mock_context):
        """Test that create_server returns a Server instance."""
        server = create_server(mock_context)
        assert hasattr(server, "get_capabilities")


class TestIntegration:
    """Integration tests for the MCP server components."""

    def test_server_integration_with_context(self, mock_context):
        """Test server creation with context integration."""
        # Test that all components work together
        server = create_server(mock_context)

        # Verify server creation
        assert server is not None

    def test_project_resource_creation_integration(self):
        """Test project resource creation with real-like data."""
        project_data = {
            "key": "INTEG",
            "name": "Integration",
            "description": "Project for integration testing",
        }

        resource = _create_project_resource(project_data)

        assert resource.name == "Project: Integration"
        assert resource.description == "Project for integration testing"
        assert str(resource.uri) == "jira://project/INTEG"

    def test_issue_formatting_integration(self):
        """Test issue formatting with comprehensive issue data."""
        ticket = "INTEGRATION-123"
        comprehensive_issue = {
            "key": ticket,
            "fields": {
                "summary": "Integration test issue",
                "description": "This is a comprehensive test issue for integration testing",
                "status": {"name": "In Progress", "id": "3"},
                "issuetype": {"name": "Story", "id": "10001"},
                "assignee": {"displayName": "Test User", "name": "testuser"},
                "priority": {"name": "High", "id": "2"},
                "created": "2023-01-01T10:00:00.000+0000",
                "updated": "2023-01-02T11:00:00.000+0000",
            },
        }

        formatted = _format_issue_details(ticket, comprehensive_issue)

        assert "Issue: INTEGRATION-123" in formatted
        assert "Type: Story" in formatted
        assert "Status: In Progress" in formatted
        assert "Summary: Integration test issue" in formatted
        assert "This is a comprehensive test issue" in formatted

    def test_transitions_formatting_integration(self):
        """Test transitions formatting with realistic transition data."""
        ticket = "INTEGRATION-456"
        realistic_transitions = {
            "transitions": [
                {
                    "id": "11",
                    "name": "To Do",
                    "to": {"name": "To Do", "id": "1"},
                    "hasScreen": False,
                    "isGlobal": True,
                },
                {
                    "id": "21",
                    "name": "In Progress",
                    "to": {"name": "In Progress", "id": "3"},
                    "hasScreen": True,
                    "isGlobal": False,
                },
                {
                    "id": "31",
                    "name": "Done",
                    "to": {"name": "Done", "id": "10001"},
                    "hasScreen": False,
                    "isGlobal": True,
                },
            ]
        }

        formatted = _format_transitions(ticket, realistic_transitions)

        assert "Available transitions for INTEGRATION-456:" in formatted
        assert "ID: 11, Name: To Do, To: To Do" in formatted
        assert "ID: 21, Name: In Progress, To: In Progress" in formatted
        assert "ID: 31, Name: Done, To: Done" in formatted

    @pytest.mark.asyncio
    async def test_handle_get_comments(self, mock_context):
        """Test the get-comments tool."""
        mock_context.jira._request.return_value = {
            "comments": [
                {
                    "id": "10001",
                    "author": {"displayName": "John Doe"},
                    "body": "This is a comment.",
                }
            ],
            "total": 1,
        }

        result = await mcp_server._handle_get_comments(
            mock_context, {"ticket": "TEST-123", "limit": 1}
        )

        assert len(result) == 1
        text_content = result[0]
        assert isinstance(text_content, types.TextContent)
        assert "Comments for TEST-123" in text_content.text
        assert "ID: 10001 | John Doe: This is a comment." in text_content.text

    @pytest.mark.asyncio
    async def test_handle_edit_comment(self, mock_context):
        """Test the edit-comment tool."""
        mock_context.jira.formatter.format_comment.return_value = "New comment body"

        result = await mcp_server._handle_edit_comment(
            mock_context,
            {"ticket": "TEST-123", "comment_id": "10001", "comment": "New comment"},
        )

        assert len(result) == 1
        text_content = result[0]
        assert isinstance(text_content, types.TextContent)
        assert text_content.text == "Edited comment 10001 on TEST-123"
        mock_context.jira._request.assert_called_once_with(
            "PUT", "issue/TEST-123/comment/10001", jeez={"body": "New comment body"}
        )

    @pytest.mark.asyncio
    async def test_handle_delete_comment(self, mock_context):
        """Test the delete-comment tool."""
        result = await mcp_server._handle_delete_comment(
            mock_context, {"ticket": "TEST-123", "comment_id": "10001"}
        )

        assert len(result) == 1
        text_content = result[0]
        assert isinstance(text_content, types.TextContent)
        assert text_content.text == "Deleted comment 10001 from TEST-123"
        mock_context.jira._request.assert_called_once_with(
            "DELETE", "issue/TEST-123/comment/10001"
        )
