"""Tests for API version support in JiraHTTP client."""

from unittest.mock import patch

from jayrah.api.jira import JiraHTTP


def test_api_version_init(sample_config):
    """Test initialization with different API versions."""
    # Test default version (v2)
    client = JiraHTTP(sample_config)
    assert client.api_version == "2"
    assert client.base_url == f"{sample_config['jira_server']}/rest/api/2"

    # Test with explicit v3
    client_v3 = JiraHTTP(sample_config, api_version="3")
    assert client_v3.api_version == "3"
    assert client_v3.base_url == f"{sample_config['jira_server']}/rest/api/3"


def test_create_issue_description_v2(sample_config):
    """Test creating an issue with description in API v2."""
    client = JiraHTTP(sample_config)

    with patch.object(client, "_request") as mock_request:
        client.create_issue(
            issuetype="Story", summary="Test issue", description="Test description"
        )

        # Extract the payload from the _request call
        args, kwargs = mock_request.call_args
        payload = kwargs.get("jeez", {})

        # Verify description format for v2
        assert payload["fields"]["description"] == "Test description"
        assert isinstance(payload["fields"]["description"], str)


def test_create_issue_description_v3(sample_config):
    """Test creating an issue with description in API v3."""
    client = JiraHTTP(sample_config, api_version="3")

    with patch.object(client, "_request") as mock_request:
        client.create_issue(
            issuetype="Story", summary="Test issue", description="Test description"
        )

        # Extract the payload from the _request call
        args, kwargs = mock_request.call_args
        payload = kwargs.get("jeez", {})

        # Verify description format for v3 (should be ADF)
        assert isinstance(payload["fields"]["description"], dict)
        assert payload["fields"]["description"]["type"] == "doc"
        assert payload["fields"]["description"]["version"] == 1
        assert (
            payload["fields"]["description"]["content"][0]["content"][0]["text"]
            == "Test description"
        )


def test_add_comment_v2(sample_config):
    """Test adding a comment with API v2."""
    client = JiraHTTP(sample_config)

    with patch.object(client, "_request") as mock_request:
        client.add_comment("TEST-123", "Test comment")

        # Extract the payload from the _request call
        args, kwargs = mock_request.call_args
        payload = kwargs.get("jeez", {})

        # Verify comment format for v2
        assert payload["body"] == "Test comment"


def test_add_comment_v3(sample_config):
    """Test adding a comment with API v3."""
    client = JiraHTTP(sample_config, api_version="3")

    with patch.object(client, "_request") as mock_request:
        client.add_comment("TEST-123", "Test comment")

        # Extract the payload from the _request call
        args, kwargs = mock_request.call_args
        payload = kwargs.get("jeez", {})

        # Verify comment format for v3 (should be ADF)
        assert isinstance(payload, dict)
        assert payload["type"] == "doc"
        assert payload["version"] == 1
        assert payload["content"][0]["content"][0]["text"] == "Test comment"
