"""Tests for API version support in JiraHTTP client."""

from unittest.mock import patch

from jayrah.api.jira_client import JiraHTTP


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

        # Verify comment format for v3 (should be ADF wrapped in body)
        assert isinstance(payload, dict)
        assert "body" in payload
        assert payload["body"]["type"] == "doc"
        assert payload["body"]["version"] == 1
        assert payload["body"]["content"][0]["content"][0]["text"] == "Test comment"


def test_v3_assignee_email_uses_name_field(sample_config):
    """Test that API v3 does not treat email as accountId."""
    client = JiraHTTP(sample_config, api_version="3")

    with patch.object(client, "_request") as mock_request:
        client.create_issue(
            issuetype="Story",
            summary="Test issue",
            description="Test description",
            assignee="user@example.com",
        )

        payload = mock_request.call_args[1]["jeez"]
        assert payload["fields"]["assignee"] == {"name": "user@example.com"}


def test_v3_assignee_account_id_uses_account_id_field(sample_config):
    """Test that API v3 uses accountId when value looks like an account ID."""
    client = JiraHTTP(sample_config, api_version="3")
    account_id = "712020:82e09708-6d0a-4bc1-bbac-5ddf6f612345"

    with patch.object(client, "_request") as mock_request:
        client.create_issue(
            issuetype="Story",
            summary="Test issue",
            description="Test description",
            assignee=account_id,
        )

        payload = mock_request.call_args[1]["jeez"]
        assert payload["fields"]["assignee"] == {"accountId": account_id}
