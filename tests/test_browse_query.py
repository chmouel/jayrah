"""
Tests for the browse command with --query option.
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
            self.issues_client = MagicMock()

            def _list_issues(jql, order_by=None):
                self.list_issues_called = True
                self.list_issues_jql = jql
                return []

            self.issues_client.list_issues.side_effect = _list_issues
            self.issues_client.list_issues.return_value = []

        def fuzzy_search(self, issues, auto_choose=False):
            return None

    # Mock check function
    def mock_check(*args, **kwargs):
        return "project = TEST", "updated"

    # Mock build_search_jql to act like the real one for our purposes
    # We can just use the real one or a simple pass-through, but let's stick closer to real behavior
    # or just spy on it.
    # Actually, let's use the real build_search_jql since we want to test the integration
    # But if we want to verify arguments passed to it, we can wrap it.

    original_build_search_jql = boards.build_search_jql

    def mock_build_search_jql_wrapper(
        base_jql, search_terms, use_or=False, verbose=False, filters=None
    ):
        mock_build_search_jql_wrapper.base_jql = base_jql
        mock_build_search_jql_wrapper.search_terms = search_terms
        return original_build_search_jql(
            base_jql, search_terms, use_or, verbose, filters
        )

    mock_build_search_jql_wrapper.base_jql = None
    mock_build_search_jql_wrapper.search_terms = None

    monkeypatch.setattr(boards, "Boards", MockBoards)
    monkeypatch.setattr(boards, "check", mock_check)
    monkeypatch.setattr(boards, "build_search_jql", mock_build_search_jql_wrapper)
    monkeypatch.setattr(boards, "show_no_issues_message", lambda *args, **kwargs: None)

    return mock_build_search_jql_wrapper


def test_browse_query_option(runner, mock_boards):
    """Test the --query option uses the provided JQL directly"""
    result = runner.invoke(commands.cli, ["browse", "-q", "assignee = currentUser()"])

    assert result.exit_code == 0
    assert mock_boards.base_jql == "assignee = currentUser()"
    assert not mock_boards.search_terms  # Should be empty tuple or list


def test_browse_query_with_extra_terms(runner, mock_boards):
    """Test --query with extra search terms treated as appending search"""
    # "extra" is captured as 'board' argument because it's positional
    # "term" is captured as 'search_terms'
    result = runner.invoke(
        commands.cli, ["browse", "-q", "assignee = currentUser()", "extra", "term"]
    )

    assert result.exit_code == 0
    assert mock_boards.base_jql == "assignee = currentUser()"
    # The 'board' argument (extra) should be prepended to search_terms
    assert "extra" in mock_boards.search_terms
    assert "term" in mock_boards.search_terms


def test_browse_query_overrides_board_check(runner, mock_boards, monkeypatch):
    """Test that --query skips boards.check"""
    mock_check_called = False

    def spy_check(*args, **kwargs):
        nonlocal mock_check_called
        mock_check_called = True
        return "project = WRONG", "updated"

    monkeypatch.setattr(boards, "check", spy_check)

    result = runner.invoke(commands.cli, ["browse", "-q", "assignee = currentUser()"])

    assert result.exit_code == 0
    assert not mock_check_called
    assert mock_boards.base_jql == "assignee = currentUser()"
