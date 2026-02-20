"""Tests for board-level Jira auth selection."""

from unittest.mock import patch

from jayrah.ui.boards import Boards


def test_boards_defaults_to_basic_when_api_v3_and_auth_missing(sample_config):
    """Boards should default to basic auth for API v3."""
    config = sample_config.copy()
    config["api_version"] = "3"
    config["auth_method"] = ""

    with patch("jayrah.ui.boards.jirahttp.JiraHTTP") as mock_jira:
        Boards(config)
        _, kwargs = mock_jira.call_args
        assert kwargs["api_version"] == "3"
        assert kwargs["auth_method"] == "basic"


def test_boards_defaults_to_bearer_when_api_v2_and_auth_missing(sample_config):
    """Boards should default to bearer auth for API v2."""
    config = sample_config.copy()
    config["api_version"] = "2"
    config["auth_method"] = ""

    with patch("jayrah.ui.boards.jirahttp.JiraHTTP") as mock_jira:
        Boards(config)
        _, kwargs = mock_jira.call_args
        assert kwargs["api_version"] == "2"
        assert kwargs["auth_method"] == "bearer"
