from unittest.mock import MagicMock, patch

import pytest

from jayrah import utils


def test_make_osc8_link():
    """Test creating OSC8 terminal links."""
    link = utils.make_osc8_link("JIRA-123", "https://jira.example.com/browse/JIRA-123")
    assert "\033]8;;" in link  # Contains OSC8 escape sequences
    assert "JIRA-123" in link  # Contains the display text
    assert "https://jira.example.com/browse/JIRA-123" in link  # Contains the URL


def test_make_full_url():
    """Test creating full Jira URLs."""
    url = utils.make_full_url("JIRA-123", "https://jira.example.com")
    assert url == "https://jira.example.com/browse/JIRA-123"

    # Test with None server
    with pytest.raises(Exception):
        utils.make_full_url("JIRA-123", None)


@patch("webbrowser.open")
def test_browser_open_ticket(mock_open):
    """Test opening a ticket in the browser."""
    config = {"jira_server": "https://jira.example.com"}
    utils.browser_open_ticket("JIRA-123", config)
    mock_open.assert_called_once_with("https://jira.example.com/browse/JIRA-123")

    # Test with no ticket (should open project page)
    mock_open.reset_mock()
    config["jira_component"] = "TEST"
    utils.browser_open_ticket(None, config)
    mock_open.assert_called_once_with("https://jira.example.com/projects/TEST")

    # Test with exception
    mock_open.reset_mock()
    mock_open.side_effect = Exception("Browser error")
    utils.browser_open_ticket("JIRA-123", config)  # Should not raise exception


def test_show_time():
    """Test date formatting."""
    formatted = utils.show_time("2023-01-01T12:34:56.789+0000")
    assert formatted == "2023-01-01"


def test_parse_email():
    """Test email parsing."""
    # Test with emailAddress
    result = utils.parse_email({"emailAddress": "user@example.com"})
    assert result == "user"

    # Test with key
    result = utils.parse_email({"key": "user@example.com"})
    assert result == "user"

    # Test with plus addressing
    result = utils.parse_email({"emailAddress": "user+tag@example.com"})
    assert result == "user"


@patch("subprocess.run")
@patch("os.environ.get")
def test_edit_text_with_editor(mock_environ_get, mock_run):
    """Test editing text with the system editor."""
    mock_environ_get.return_value = "nano"

    # Create a mock temporary file that will contain the edited content
    edited_content = "Edited text content"

    # Mock open to handle reading the "edited" file
    with patch("builtins.open", create=True) as mock_open:
        # Configure the mock to return the edited content when reading
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = edited_content
        mock_open.return_value = mock_file

        # Call the function
        result = utils.edit_text_with_editor("Initial text", extension=".md")

        # Verify the editor was called
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0][0] == "nano"

        # Verify the file was read
        assert result == edited_content
