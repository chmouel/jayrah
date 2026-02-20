"""
Tests for the gencontext command with --query option.
"""

from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from jayrah.commands import mcli
from jayrah.ui import boards


@pytest.fixture
def runner():
    """Click test runner"""
    return CliRunner()


@pytest.fixture
def mock_context_generator(monkeypatch):
    """Mock the ContextGenerator class"""
    mock_generator = MagicMock()
    mock_generator.generate_board_context.return_value = "Generated Context Content"

    class MockContextGeneratorClass:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def generate_board_context(self, board, jql, order_by):
            mock_generator.generate_board_context(board, jql, order_by)
            return "Generated Context Content"

    monkeypatch.setattr(
        "jayrah.utils.context_generator.ContextGenerator", MockContextGeneratorClass
    )
    return mock_generator


@pytest.fixture
def mock_boards(monkeypatch):
    """Mock the boards module"""

    def mock_check(board, config):
        if board == "my-board":
            return "project = MYBOARD", "updated"
        return None, None

    monkeypatch.setattr(boards, "check", mock_check)


@pytest.fixture
def mock_jayrah_obj():
    """Mock the Jayrah object passed to commands"""
    obj = MagicMock()
    obj.config = {"verbose": False}
    obj.issues_client = MagicMock()
    return obj


def test_gencontext_query_option(
    runner, mock_context_generator, mock_boards, mock_jayrah_obj
):
    """Test the --query option uses the provided JQL directly"""
    # We need to invoke the cli group first, then the command
    result = runner.invoke(
        mcli.cli, ["gencontext", "-q", "assignee = currentUser()"], obj=mock_jayrah_obj
    )

    assert result.exit_code == 0
    assert "Generated Context Content" in result.output

    # Verify generate_board_context was called with correct args
    mock_context_generator.generate_board_context.assert_called_once()
    call_args = mock_context_generator.generate_board_context.call_args
    assert call_args[0][0] == "Custom Query"  # board name
    assert call_args[0][1] == "assignee = currentUser()"  # jql
    assert call_args[0][2] == "updated"  # default order_by


def test_gencontext_query_overrides_board(
    runner, mock_context_generator, mock_boards, mock_jayrah_obj
):
    """Test that --query works even if a board is specified (query takes precedence logic depends on implementation,
    but based on my implementation, if query is present it is used)"""

    result = runner.invoke(
        mcli.cli,
        ["gencontext", "my-board", "-q", "project = OVERRIDE"],
        obj=mock_jayrah_obj,
    )

    assert result.exit_code == 0

    mock_context_generator.generate_board_context.assert_called_once()
    call_args = mock_context_generator.generate_board_context.call_args
    assert call_args[0][0] == "my-board"  # Should keep the board name if provided
    assert call_args[0][1] == "project = OVERRIDE"  # But use the custom JQL


def test_gencontext_missing_args(
    runner, mock_context_generator, mock_boards, mock_jayrah_obj
):
    """Test failure when neither board nor query is provided"""
    result = runner.invoke(mcli.cli, ["gencontext"], obj=mock_jayrah_obj)

    # It shouldn't crash, but print an error message
    assert result.exit_code == 0
    assert "You must specify a board or a JQL query" in result.output
    mock_context_generator.generate_board_context.assert_not_called()
