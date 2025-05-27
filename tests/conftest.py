from unittest.mock import MagicMock, patch

import pytest
import yaml
import getpass


@pytest.fixture
def sample_config():
    """Return a sample configuration dictionary."""
    return {
        "jira_server": "https://test-jira.example.com",
        "jira_user": "testuser",
        "jira_password": "testpassword",
        "jira_project": "TEST",
        "jira_component": "TestComponent",
        "verbose": True,
        "no_cache": False,
        "insecure": False,
        "cache_ttl": 3600,
        "boards": [
            {
                "name": "myissue",
                "jql": "assignee = currentUser() AND resolution = Unresolved",
                "order_by": "updated",
                "description": "My current issues",
            },
            {
                "name": "testboard",
                "jql": "project = TEST",
                "order_by": "priority",
                "description": "Test board",
            },
        ],
    }


@pytest.fixture
def temp_config_file(tmp_path, sample_config):
    """Create a temporary config file with sample data."""
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump({"general": sample_config, "boards": sample_config["boards"]}, f)
    return config_file


@pytest.fixture
def mock_jira_client():
    """Return a mocked Jira HTTP client."""
    with patch("jayrah.api.jira.JiraHTTP") as mock_jira:
        client_instance = MagicMock()
        mock_jira.return_value = client_instance
        yield client_instance


@pytest.fixture
def sample_issues():
    """Return a list of sample Jira issues."""
    return {
        "issues": [
            {
                "key": "TEST-123",
                "fields": {
                    "summary": "Test issue 1",
                    "issuetype": {"name": "Bug", "iconUrl": "bug.png"},
                    "assignee": {"displayName": "Test User", "name": "testuser"},
                    "reporter": {"displayName": "Reporter User", "name": "reporter"},
                    "status": {"name": "In Progress"},
                    "priority": {"name": "Major"},
                    "created": "2023-01-01T10:00:00.000+0000",
                    "updated": "2023-01-02T11:00:00.000+0000",
                    "description": "Test description for issue 1",
                    "components": [{"name": "TestComponent"}],
                    "labels": ["test", "bug"],
                    "fixVersions": [{"name": "1.0.0"}],
                    "comment": {
                        "comments": [
                            {
                                "author": {
                                    "displayName": "Test User",
                                    "name": "testuser",
                                },
                                "created": "2023-01-02T10:00:00.000+0000",
                                "body": "This is a test comment",
                            }
                        ],
                        "total": 1,
                    },
                },
            },
            {
                "key": "TEST-124",
                "fields": {
                    "summary": "Test issue 2",
                    "issuetype": {"name": "Task", "iconUrl": "task.png"},
                    "assignee": {"displayName": "Test User", "name": "testuser"},
                    "reporter": {"displayName": "Reporter User", "name": "reporter"},
                    "status": {"name": "To Do"},
                    "priority": {"name": "Minor"},
                    "created": "2023-01-03T10:00:00.000+0000",
                    "updated": "2023-01-04T11:00:00.000+0000",
                    "description": "Test description for issue 2",
                },
            },
        ],
        "total": 2,
    }


@pytest.fixture
def mock_subprocess_run():
    """Mock the subprocess.run function."""
    with patch("subprocess.run") as mock_run:
        mock_process = MagicMock()
        mock_process.stdout = "TEST-123\n"
        mock_run.return_value = mock_process
        yield mock_run


@pytest.fixture
def mock_browser_open():
    """Mock the webbrowser.open function."""
    with patch("webbrowser.open") as mock_open:
        yield mock_open


@pytest.fixture(autouse=True)
def mock_getpass(monkeypatch):
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "fakepassword")


@pytest.fixture(autouse=True)
def mock_prompt_ask(monkeypatch):
    try:
        from rich.prompt import Prompt
    except ImportError:
        return
    monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "fakeinput")
