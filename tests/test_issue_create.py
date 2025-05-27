import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest
import click

from jayrah.commands.issue_create import (
    get_smart_defaults,
    select_issue_type,
    select_priority,
    select_assignee,
    select_labels,
    get_description,
    create_default_template,
    load_template,
    find_repo_template,
    preview_issue,
    validate_issue,
    interactive_create,
    create_issue,
)


@pytest.fixture
def mock_jayrah_obj():
    obj = MagicMock()
    obj.config = {
        "default_issuetype": "Story",
        "default_assignee": "john.doe",
        "default_priority": "Medium",
        "default_labels": ["documentation"],
        "jira_project": "TEST",
        "jira_server": "https://test.atlassian.net",
    }
    obj.jira = MagicMock()
    return obj


def test_get_smart_defaults(mock_jayrah_obj):
    with patch("subprocess.check_output") as mock_git:
        mock_git.return_value = b"feature/new-feature"
        defaults = get_smart_defaults(mock_jayrah_obj)
        assert defaults["issuetype"] == "Story"
        assert defaults["assignee"] == "john.doe"
        assert defaults["priority"] == "Medium"
        assert defaults["labels"] == ["documentation"]
        assert defaults["title_suggestion"] == "Feature New Feature"


def test_select_issue_type(mock_jayrah_obj):
    mock_jayrah_obj.jira.get_issue_types.return_value = [
        {"name": "Story"},
        {"name": "Bug"},
        {"name": "Task"},
    ]
    with patch("jayrah.ui.textual.select_from_list") as mock_select:
        mock_select.return_value = "Bug"
        result = select_issue_type(mock_jayrah_obj)
        assert result == "Bug"
        mock_select.assert_called_once_with(
            "Select issue type",
            ["Story", "Bug", "Task"],
            default="Story",
        )


def test_select_priority(mock_jayrah_obj):
    mock_jayrah_obj.jira.get_priorities.return_value = [
        {"name": "High"},
        {"name": "Medium"},
        {"name": "Low"},
    ]
    with patch("jayrah.ui.textual.select_from_list") as mock_select:
        mock_select.return_value = "High"
        result = select_priority(mock_jayrah_obj)
        assert result == "High"
        mock_select.assert_called_once_with(
            "Select priority",
            ["High", "Medium", "Low"],
            default="Medium",
        )


def test_select_assignee(mock_jayrah_obj):
    mock_jayrah_obj.jira.get_users.return_value = [
        {"displayName": "John Doe"},
        {"displayName": "Jane Smith"},
    ]
    with patch("jayrah.ui.textual.select_from_list") as mock_select:
        mock_select.return_value = "John Doe"
        result = select_assignee(mock_jayrah_obj)
        assert result == "John Doe"
        mock_select.assert_called_once_with(
            "Select assignee",
            ["John Doe", "Jane Smith"],
            default="john.doe",
        )


def test_select_labels(mock_jayrah_obj):
    mock_jayrah_obj.jira.get_labels.return_value = [
        "bug",
        "enhancement",
        "documentation",
    ]
    with patch("jayrah.ui.textual.select_from_list") as mock_select:
        mock_select.return_value = ["bug", "documentation"]
        result = select_labels(mock_jayrah_obj)
        assert result == ["bug", "documentation"]
        mock_select.assert_called_once_with(
            "Select labels",
            ["bug", "enhancement", "documentation"],
            multi=True,
            default="all",
        )


def test_create_default_template():
    template = create_default_template("Test Issue")
    assert "## Description" in template
    assert "## Acceptance Criteria" in template
    assert "## Additional Information" in template


def test_load_template(mock_jayrah_obj):
    # Test loading from config
    mock_jayrah_obj.config["templates"] = {"bug": "Bug template content"}
    template = load_template(mock_jayrah_obj, "bug")
    assert template == "Bug template content"

    # Test loading from repository
    with patch("jayrah.commands.issue_create.find_repo_template") as mock_find:
        mock_find.return_value = "Repo template content"
        template = load_template(mock_jayrah_obj, "feature")
        assert template == "Repo template content"


def test_find_repo_template():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test template
        os.makedirs(os.path.join(tmpdir, ".github", "ISSUE_TEMPLATE"))
        template_path = os.path.join(tmpdir, ".github", "ISSUE_TEMPLATE", "bug.md")
        with open(template_path, "w") as f:
            f.write("Test template content")

        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True
            template = find_repo_template("bug")
            assert template == "Test template content"


def test_preview_issue(capsys):
    with patch("jayrah.ui.textual.display_preview") as mock_preview:
        preview_issue(
            "Bug",
            "Test Issue",
            "Test description",
            "High",
            "john.doe",
            ["bug", "documentation"],
        )
        mock_preview.assert_called_once_with(
            "Issue Preview",
            "Type: Bug\nTitle: Test Issue\nPriority: High\nAssignee: john.doe\nLabels: bug, documentation\n\nDescription:\nTest description",
        )


def test_validate_issue():
    # Test valid issue
    validate_issue("Bug", "Test Issue", "Test description")

    # Test missing title
    with pytest.raises(click.UsageError):
        validate_issue("Bug", "", "Test description")

    # Test missing description
    with pytest.raises(click.UsageError):
        validate_issue("Bug", "Test Issue", "")

    # Test missing issue type
    with pytest.raises(click.UsageError):
        validate_issue("", "Test Issue", "Test description")


def test_create_issue(mock_jayrah_obj):
    mock_jayrah_obj.jira.create_issue.return_value = {"key": "TEST-123"}
    result = create_issue(
        mock_jayrah_obj,
        "Bug",
        "Test Issue",
        "Test description",
        "High",
        "john.doe",
        ["bug"],
    )
    assert result == "TEST-123"
    mock_jayrah_obj.jira.create_issue.assert_called_once_with(
        issuetype="Bug",
        summary="Test Issue",
        description="Test description",
        priority="High",
        assignee="john.doe",
        labels=["bug"],
    )


def test_interactive_create(mock_jayrah_obj):
    with patch("jayrah.commands.issue_create.select_issue_type") as mock_type:
        with patch("jayrah.commands.issue_create.select_priority") as mock_priority:
            with patch("jayrah.commands.issue_create.select_assignee") as mock_assignee:
                with patch("jayrah.commands.issue_create.select_labels") as mock_labels:
                    with patch(
                        "jayrah.commands.issue_create.get_description"
                    ) as mock_desc:
                        with patch(
                            "jayrah.commands.issue_create.preview_issue"
                        ) as mock_preview:
                            with patch(
                                "jayrah.ui.textual.confirm_action"
                            ) as mock_confirm:
                                mock_type.return_value = "Bug"
                                mock_priority.return_value = "High"
                                mock_assignee.return_value = "john.doe"
                                mock_labels.return_value = ["bug"]
                                mock_desc.return_value = "Test description"
                                mock_confirm.return_value = True

                                mock_jayrah_obj.jira.create_issue.return_value = {
                                    "key": "TEST-123"
                                }
                                result = interactive_create(mock_jayrah_obj)
                                assert result == "TEST-123"
