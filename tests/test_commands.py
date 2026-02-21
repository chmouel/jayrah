"""
Tests for the CLI commands.
"""

from unittest.mock import MagicMock

import click
import pytest
from click.testing import CliRunner

from jayrah import commands
from jayrah.commands import common
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
            self.ui_backend = "textual"
            self.query = None
            self.calls = []
            self.issues_client = MagicMock()

            def _list_issues(jql, order_by=None):
                self.list_issues_called = True
                self.list_issues_jql = jql
                return mock_build_search_jql.issues_return_value

            self.issues_client.list_issues.side_effect = _list_issues
            mock_build_search_jql.last_instance = self

        def fuzzy_search(
            self, issues, auto_choose=False, ui_backend="textual", query=None
        ):
            self.fuzzy_search_called = True
            self.auto_choose = auto_choose
            self.ui_backend = ui_backend
            self.query = query
            self.calls.append(
                {
                    "issues": issues,
                    "auto_choose": auto_choose,
                    "ui_backend": ui_backend,
                    "query": query,
                }
            )
            if mock_build_search_jql.raise_on_rust and ui_backend == "rust":
                raise click.ClickException("rust launcher failed")
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
    mock_build_search_jql.raise_on_rust = False

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


def test_browse_command_rust_ui_skips_python_issue_prefetch(runner, mock_boards):
    """Test --ui rust routes through rust backend query and skips list_issues."""
    mock_boards.fuzzy_search_result = "TEST-456"

    result = runner.invoke(
        commands.cli,
        ["browse", "myboard", "--ui", "rust"],
    )

    assert result.exit_code == 0
    assert mock_boards.last_instance is not None
    assert mock_boards.last_instance.fuzzy_search_called
    assert mock_boards.last_instance.ui_backend == "rust"
    assert mock_boards.last_instance.query == "project = TEST ORDER BY updated"
    assert not mock_boards.last_instance.list_issues_called


def test_browse_command_uses_configured_rust_ui_default(
    runner, mock_boards, monkeypatch
):
    """When config ui_backend=rust, browse should use rust path without --ui."""

    def fake_make_config(flag_config, config_file):
        _ = flag_config, config_file
        return {
            "jira_server": "https://jira.example.com",
            "jira_user": "testuser",
            "jira_password": "testpass",
            "jira_project": "TEST",
            "boards": [{"name": "myboard", "jql": "project = TEST", "order_by": "updated"}],
            "ui_backend": "rust",
            "verbose": False,
            "quiet": False,
            "insecure": False,
            "cache_ttl": 3600,
        }

    monkeypatch.setattr(common.config, "make_config", fake_make_config)

    result = runner.invoke(commands.cli, ["browse", "myboard"])

    assert result.exit_code == 0
    assert mock_boards.last_instance is not None
    assert mock_boards.last_instance.ui_backend == "rust"
    assert not mock_boards.last_instance.list_issues_called


def test_browse_command_global_ui_backend_flag_overrides_config(
    runner, mock_boards, monkeypatch
):
    """Global --ui-backend should override persisted config for this invocation."""

    def fake_make_config(flag_config, config_file):
        _ = flag_config, config_file
        return {
            "jira_server": "https://jira.example.com",
            "jira_user": "testuser",
            "jira_password": "testpass",
            "jira_project": "TEST",
            "boards": [{"name": "myboard", "jql": "project = TEST", "order_by": "updated"}],
            "ui_backend": "textual",
            "verbose": False,
            "quiet": False,
            "insecure": False,
            "cache_ttl": 3600,
        }

    monkeypatch.setattr(common.config, "make_config", fake_make_config)

    result = runner.invoke(
        commands.cli, ["--ui-backend", "rust", "browse", "myboard"]
    )

    assert result.exit_code == 0
    assert mock_boards.last_instance is not None
    assert mock_boards.last_instance.ui_backend == "rust"
    assert not mock_boards.last_instance.list_issues_called


def test_browse_command_falls_back_to_textual_when_config_rust_unavailable(
    runner, mock_boards, monkeypatch
):
    """Config-default rust backend should fall back to textual on launcher errors."""

    def fake_make_config(flag_config, config_file):
        _ = flag_config, config_file
        return {
            "jira_server": "https://jira.example.com",
            "jira_user": "testuser",
            "jira_password": "testpass",
            "jira_project": "TEST",
            "boards": [{"name": "myboard", "jql": "project = TEST", "order_by": "updated"}],
            "ui_backend": "rust",
            "_ui_backend_from_cli": False,
            "verbose": False,
            "quiet": False,
            "insecure": False,
            "cache_ttl": 3600,
        }

    monkeypatch.setattr(common.config, "make_config", fake_make_config)
    mock_boards.raise_on_rust = True
    mock_boards.issues_return_value = [{"key": "TEST-123"}]
    mock_boards.fuzzy_search_result = "TEST-123"

    result = runner.invoke(commands.cli, ["browse", "myboard"])

    assert result.exit_code == 0
    assert "falling back to Textual UI" in result.output
    assert mock_boards.last_instance is not None
    assert mock_boards.last_instance.list_issues_called
    assert len(mock_boards.last_instance.calls) == 2
    assert mock_boards.last_instance.calls[0]["ui_backend"] == "rust"
    assert mock_boards.last_instance.calls[1]["ui_backend"] == "textual"


def test_browse_command_explicit_rust_request_stays_strict(
    runner, mock_boards, monkeypatch
):
    """Explicit rust selection should not fall back silently."""

    def fake_make_config(flag_config, config_file):
        _ = flag_config, config_file
        return {
            "jira_server": "https://jira.example.com",
            "jira_user": "testuser",
            "jira_password": "testpass",
            "jira_project": "TEST",
            "boards": [{"name": "myboard", "jql": "project = TEST", "order_by": "updated"}],
            "ui_backend": "textual",
            "_ui_backend_from_cli": False,
            "verbose": False,
            "quiet": False,
            "insecure": False,
            "cache_ttl": 3600,
        }

    monkeypatch.setattr(common.config, "make_config", fake_make_config)
    mock_boards.raise_on_rust = True

    result = runner.invoke(commands.cli, ["browse", "myboard", "--ui", "rust"])

    assert result.exit_code != 0
    assert "rust launcher failed" in result.output


def test_browse_command_global_explicit_rust_request_stays_strict(
    runner, mock_boards, monkeypatch
):
    """Global explicit rust selection should not fall back silently."""

    def fake_make_config(flag_config, config_file):
        _ = flag_config, config_file
        return {
            "jira_server": "https://jira.example.com",
            "jira_user": "testuser",
            "jira_password": "testpass",
            "jira_project": "TEST",
            "boards": [{"name": "myboard", "jql": "project = TEST", "order_by": "updated"}],
            "ui_backend": "textual",
            "verbose": False,
            "quiet": False,
            "insecure": False,
            "cache_ttl": 3600,
        }

    monkeypatch.setattr(common.config, "make_config", fake_make_config)
    mock_boards.raise_on_rust = True

    result = runner.invoke(commands.cli, ["--ui-backend", "rust", "browse", "myboard"])

    assert result.exit_code != 0
    assert "rust launcher failed" in result.output
