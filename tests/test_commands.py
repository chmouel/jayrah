"""
Tests for the CLI commands.
"""

import pytest
from click.testing import CliRunner
from jayrah import commands
from jayrah.ui import boards
from unittest.mock import MagicMock


@pytest.fixture
def runner():
    """Click test runner"""
    return CliRunner()


@pytest.fixture
def mock_boards(monkeypatch):
    """Mock the boards module to avoid real API calls"""

    class MockBoards:
        def __init__(self, *args, **kwargs):
            self.config = {"verbose": False}
            self.command = None
            self.verbose = False
            self.list_issues_called = False
            self.list_issues_jql = None
            self.fuzzy_search_called = False
            self.issues_client = MagicMock()

        def list_issues(self, jql, order_by=None):
            self.list_issues_called = True
            self.list_issues_jql = jql
            return []

        def fuzzy_search(self, issues):
            self.fuzzy_search_called = True
            return None

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
