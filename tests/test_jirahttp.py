import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from jayrah.api.jira import JiraHTTP


@pytest.fixture
def mock_urlopen():
    with patch("urllib.request.urlopen") as mock:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"key": "TEST-123"}).encode(
            "utf-8"
        )
        mock_response.__enter__.return_value = mock_response
        mock.return_value = mock_response
        yield mock


def test_init(sample_config):
    """Test initialization of JiraHTTP client."""
    client = JiraHTTP(sample_config)
    assert client.base_url == f"{sample_config['jira_server']}/rest/api/2"
    assert "Authorization" in client.headers
    assert client.headers["Content-Type"] == "application/json"


def test_search_issues(sample_config, mock_urlopen, mock_jira_client):
    """Test searching for issues."""
    client = JiraHTTP(sample_config)

    # Mock the _request method to return sample data
    with patch.object(client, "_request") as mock_request:
        mock_request.return_value = {"issues": [{"key": "TEST-123"}]}

        result = client.search_issues(
            "project = TEST",
            start_at=0,
            max_results=10,
        )

        # Check _request was called with expected arguments
        mock_request.assert_called_once_with(
            "GET",
            "search",
            params={"jql": "project = TEST", "startAt": 0, "maxResults": 10},
            label="✨ Fetching Jira issues",
        )
        assert result["issues"][0]["key"] == "TEST-123"


def test_get_issue(sample_config, mock_urlopen, mock_jira_client):
    """Test getting a specific issue."""
    client = JiraHTTP(sample_config)

    # Mock the _request method to return sample data
    with patch.object(client, "_request") as mock_request:
        mock_request.return_value = {
            "key": "TEST-123",
            "fields": {"summary": "Test issue"},
        }

        result = client.get_issue("TEST-123")

        # Check _request was called with expected arguments
        mock_request.assert_called_once_with("GET", "issue/TEST-123", params={})
        assert result["key"] == "TEST-123"
        assert result["fields"]["summary"] == "Test issue"


def test_create_issue(sample_config, mock_urlopen, mock_jira_client):
    """Test creating an issue."""
    client = JiraHTTP(sample_config)

    # Mock the _request method to return sample data
    with patch.object(client, "_request") as mock_request:
        mock_request.return_value = {"key": "TEST-456"}

        result = client.create_issue(
            issuetype="Story",
            summary="Test story",
            description="Test description",
            priority="Major",
            assignee="testuser",
            labels=["test"],
        )

        # Check _request was called with expected arguments
        mock_request.assert_called_once()
        call_args = mock_request.call_args[0]
        assert call_args[0] == "POST"
        assert call_args[1] == "issue"

        # Check the payload
        payload = mock_request.call_args[1]["jeez"]
        assert payload["fields"]["summary"] == "Test story"
        assert payload["fields"]["issuetype"]["name"] == "Story"
        assert payload["fields"]["description"] == "Test description"
        assert payload["fields"]["priority"]["name"] == "Major"
        assert payload["fields"]["assignee"]["name"] == "testuser"
        assert payload["fields"]["labels"] == ["test"]

        assert result["key"] == "TEST-456"


def test_update_issue(sample_config, mock_urlopen, mock_jira_client):
    """Test updating an issue."""
    client = JiraHTTP(sample_config)

    # Mock the _request method
    with patch.object(client, "_request") as mock_request:
        mock_request.return_value = {}

        fields = {"description": "Updated description"}
        client.update_issue("TEST-123", fields)

        # Check _request was called with expected arguments
        mock_request.assert_called_once_with(
            "PUT", "issue/TEST-123", jeez={"fields": fields}
        )


def test_transition_issue(sample_config, mock_urlopen, mock_jira_client):
    """Test transitioning an issue."""
    client = JiraHTTP(sample_config)

    # Mock the _request method
    with patch.object(client, "_request") as mock_request:
        mock_request.return_value = {}

        client.transition_issue("TEST-123", "5")

        # Check _request was called with expected arguments
        mock_request.assert_called_once_with(
            "POST", "issue/TEST-123/transitions", jeez={"transition": {"id": "5"}}
        )


def test_get_transitions(sample_config, mock_urlopen, mock_jira_client):
    """Test getting available transitions for an issue."""
    client = JiraHTTP(sample_config)

    # Mock the _request method
    with patch.object(client, "_request") as mock_request:
        mock_request.return_value = {
            "transitions": [
                {"id": "5", "name": "In Progress", "to": {"name": "In Progress"}}
            ]
        }

        result = client.get_transitions("TEST-123")

        # Check _request was called with expected arguments
        mock_request.assert_called_once_with(
            "GET", "issue/TEST-123/transitions", label="All transitions"
        )
        assert len(result["transitions"]) == 1
        assert result["transitions"][0]["name"] == "In Progress"


@patch("urllib.request.urlopen")
def test_http_error_handling(mock_urlopen, sample_config):
    """Test handling of HTTP errors."""
    mock_urlopen.side_effect = urllib.error.HTTPError(
        "https://test-jira.example.com", 401, "Unauthorized", {}, None
    )

    client = JiraHTTP(sample_config)

    with pytest.raises(Exception) as excinfo:
        client._request("GET", "issue/TEST-123")

    assert "HTTP error" in str(excinfo.value)


@patch("urllib.request.urlopen")
def test_url_error_handling(mock_urlopen, sample_config):
    """Test handling of URL errors."""
    mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

    client = JiraHTTP(sample_config)

    with pytest.raises(Exception) as excinfo:
        client._request("GET", "issue/TEST-123")

    assert "URL error" in str(excinfo.value)
