"""Tests for machine-friendly mcli endpoints used by the Rust adapter."""

import json
from unittest.mock import MagicMock

from click.testing import CliRunner

from jayrah.commands import mcli


def _mock_issue(
    key="DEMO-1",
    summary="Sample issue",
    status="In Progress",
    issue_type="Bug",
    priority="Major",
):
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "status": {"name": status},
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
            "assignee": {"displayName": "Alice"},
            "reporter": {"displayName": "Bob"},
            "created": "2026-02-20T10:00:00.000+0000",
            "updated": "2026-02-20T11:00:00.000+0000",
            "labels": ["rust", "migration"],
            "components": [{"name": "frontend"}],
            "fixVersions": [{"name": "1.2.3"}],
            "description": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Adapter-ready detail"}],
                    }
                ],
            },
        },
    }


def _mock_obj():
    obj = MagicMock()
    obj.config = {
        "boards": [{"name": "my-board", "jql": "project = DEMO", "order_by": "updated"}]
    }
    obj.issues_client = MagicMock()
    obj.jira = MagicMock()
    return obj


def test_browse_list_machine_json_for_board():
    """browse-list should resolve board JQL and emit stable machine JSON."""
    runner = CliRunner()
    obj = _mock_obj()
    obj.issues_client.list_issues.return_value = [_mock_issue()]

    result = runner.invoke(mcli.cli, ["browse-list", "my-board"], obj=obj)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "1"
    assert payload["source"]["mode"] == "board"
    assert payload["source"]["board"] == "my-board"
    assert payload["source"]["jql"] == "project = DEMO ORDER BY updated"
    assert payload["issue_count"] == 1
    assert payload["issues"][0]["key"] == "DEMO-1"
    assert payload["issues"][0]["summary"] == "Sample issue"


def test_browse_list_machine_json_for_query():
    """browse-list should accept raw JQL query mode without board lookup."""
    runner = CliRunner()
    obj = _mock_obj()
    obj.issues_client.list_issues.return_value = [_mock_issue(key="DEMO-2")]

    result = runner.invoke(mcli.cli, ["browse-list", "-q", "project = DEMO"], obj=obj)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["source"]["mode"] == "query"
    assert payload["source"]["board"] is None
    assert payload["source"]["jql"] == "project = DEMO"
    assert payload["issues"][0]["key"] == "DEMO-2"


def test_browse_list_resolves_current_user_for_board_mode():
    """browse-list should resolve currentUser() from configured jira_user."""
    runner = CliRunner()
    obj = _mock_obj()
    obj.config["jira_user"] = "alice@example.com"
    obj.config["boards"] = [
        {
            "name": "my-board",
            "jql": "assignee = currentUser() AND resolution = Unresolved",
            "order_by": "updated",
        }
    ]
    obj.issues_client.list_issues.return_value = [_mock_issue()]

    result = runner.invoke(mcli.cli, ["browse-list", "my-board"], obj=obj)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert (
        payload["source"]["jql"]
        == 'assignee = "alice@example.com" AND resolution = Unresolved ORDER BY updated'
    )
    called_jql = obj.issues_client.list_issues.call_args.args[0]
    assert (
        called_jql
        == 'assignee = "alice@example.com" AND resolution = Unresolved ORDER BY updated'
    )


def test_issue_show_machine_json_normalizes_adf_description():
    """issue-show should emit a stable detail payload and flatten ADF text."""
    runner = CliRunner()
    obj = _mock_obj()
    obj.jira.get_issue.return_value = _mock_issue()

    result = runner.invoke(mcli.cli, ["issue-show", "DEMO-1"], obj=obj)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == "1"
    assert payload["issue"]["key"] == "DEMO-1"
    assert payload["issue"]["components"] == ["frontend"]
    assert payload["issue"]["fix_versions"] == ["1.2.3"]
    assert payload["issue"]["labels"] == ["rust", "migration"]
    assert payload["issue"]["description"] == "Adapter-ready detail"
