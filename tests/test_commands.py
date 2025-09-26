"""
Tests for the CLI commands.
"""

from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from jayrah import commands
from jayrah.ui import boards


@pytest.fixture
def runner():
    """Click test runner"""
    return CliRunner()


@pytest.fixture
def mock_boards(monkeypatch):
    """Mock the boards module to avoid real API calls"""

    class MockBoards:
        def __init__(self, config, *args, **kwargs):
            self.config = config
            self.command = None
            self.verbose = config.get("verbose", False)
            self.list_issues_called = False
            self.list_issues_jql = None
            self.fuzzy_search_called = False
            self.auto_choose = False
            self.issues_client = MagicMock()

            def _list_issues(jql, order_by=None):
                self.list_issues_called = True
                self.list_issues_jql = jql
                return mock_build_search_jql.issues_return_value

            self.issues_client.list_issues.side_effect = _list_issues
            mock_build_search_jql.last_instance = self

        def fuzzy_search(self, issues, auto_choose=False):
            self.fuzzy_search_called = True
            self.auto_choose = auto_choose
            return mock_build_search_jql.fuzzy_search_result

        def suggest_git_branch(self, search_terms=None, use_or=False, filters=None):
            self.search_terms = search_terms
            self.use_or = use_or
            self.filters = filters

    # Mock check function to return a simple JQL
    def mock_check(*args, **kwargs):
        return "project = TEST", "updated"

    # Mock build_search_jql to verify it's called correctly
    original_build_search_jql = boards.build_search_jql

    def mock_build_search_jql(
        base_jql, search_terms, use_or=False, verbose=False, filters=None
    ):
        mock_build_search_jql.called = True
        mock_build_search_jql.base_jql = base_jql
        mock_build_search_jql.search_terms = search_terms
        mock_build_search_jql.use_or = use_or
        mock_build_search_jql.verbose = verbose
        mock_build_search_jql.filters = filters

        # Call the real function to test its behavior
        return original_build_search_jql(
            base_jql, search_terms, use_or, verbose, filters
        )

    mock_build_search_jql.called = False
    mock_build_search_jql.last_instance = None
    mock_build_search_jql.issues_return_value = []
    mock_build_search_jql.fuzzy_search_result = None

    monkeypatch.setattr(boards, "Boards", MockBoards)
    monkeypatch.setattr(boards, "check", mock_check)
    monkeypatch.setattr(boards, "build_search_jql", mock_build_search_jql)
    monkeypatch.setattr(boards, "show_no_issues_message", lambda *args, **kwargs: None)

    return mock_build_search_jql


def test_browse_command_with_filters(runner, mock_boards):
    """Test the browse command with filters"""
    # Run with a filter
    result = runner.invoke(
        commands.cli, ["browse", "myboard", "--filter", "status=Open"]
    )

    assert result.exit_code == 0
    assert mock_boards.called
    assert mock_boards.base_jql == "project = TEST"
    assert mock_boards.filters == (
        "status=Open",
    )  # Click passes a tuple with multiple=True

    # Run with multiple filters
    result = runner.invoke(
        commands.cli,
        ["browse", "myboard", "--filter", "status=Open", "--filter", "priority=High"],
    )

    assert result.exit_code == 0
    assert mock_boards.called
    assert mock_boards.base_jql == "project = TEST"
    assert mock_boards.filters == ("status=Open", "priority=High")

    # Test filter with spaces in value
    result = runner.invoke(
        commands.cli, ["browse", "myboard", "--filter", "status=Code Review"]
    )

    assert result.exit_code == 0
    assert mock_boards.called
    assert mock_boards.base_jql == "project = TEST"
    assert mock_boards.filters == ("status=Code Review",)

    # Test with both search terms and filters
    result = runner.invoke(
        commands.cli, ["browse", "myboard", "search-term", "--filter", "status=Open"]
    )

    assert result.exit_code == 0
    assert mock_boards.called
    assert mock_boards.base_jql == "project = TEST"
    assert mock_boards.search_terms == (
        "search-term",
    )  # Click nargs=-1 creates a tuple
    assert mock_boards.filters == ("status=Open",)


def test_browse_command_choose_option(runner, mock_boards, monkeypatch):
    """Test the --choose flag automatically selects and prints issue URL"""
    monkeypatch.setenv("JIRA_SERVER", "https://jira.example.com")
    mock_boards.issues_return_value = [{"key": "TEST-123"}]
    mock_boards.fuzzy_search_result = "TEST-123"

    result = runner.invoke(commands.cli, ["browse", "myboard", "--choose"])

    assert result.exit_code == 0
    assert mock_boards.last_instance is not None
    expected_server = mock_boards.last_instance.config.get("jira_server")
    assert expected_server
    assert f"TEST-123 {expected_server}/browse/TEST-123" in result.output
    assert mock_boards.last_instance.fuzzy_search_called
    assert mock_boards.last_instance.auto_choose
