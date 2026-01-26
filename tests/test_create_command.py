"""Tests for the create command dry-run behavior."""

from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from jayrah import commands
from jayrah.create import defaults
from jayrah.create.create import _build_issue_template, _parse_editor_submission


@pytest.fixture
def runner():
    """Provide a Click CLI test runner."""

    return CliRunner()


@pytest.fixture
def dummy_context(monkeypatch):
    """Stub the Boards object used by the CLI root."""

    class DummyBoards:
        def __init__(self, config):
            self.config = config

    monkeypatch.setattr("jayrah.commands.common.boards.Boards", DummyBoards)
    return DummyBoards


def test_create_command_passes_dry_run_flag(runner, dummy_context, monkeypatch):
    """Ensure the --dry-run flag is forwarded to the interactive flow."""

    defaults = {
        "title": "Sample",
        "issuetype": "Task",
        "content": "Body",
        "priority": "Medium",
        "assignee": "user",
        "labels": ["foo"],
        "components": ["comp"],
    }

    monkeypatch.setattr(
        "jayrah.commands.create.create_edit_issue",
        lambda *args, **kwargs: defaults,
    )

    received = {}

    def fake_interactive(obj, defaults_dict, dry_run=False):
        received["dry_run"] = dry_run
        received["defaults"] = defaults_dict

    monkeypatch.setattr(
        "jayrah.commands.create.interactive_create",
        fake_interactive,
    )

    monkeypatch.setattr(
        "jayrah.commands.common.config.make_config",
        lambda flags, path: {"boards": [], "create": {}},
    )

    result = runner.invoke(commands.cli, ["create", "--dry-run"])

    assert result.exit_code == 0
    assert received["dry_run"] is True
    assert received["defaults"] == defaults


def test_interactive_create_dry_run_skips_api_call(monkeypatch):
    """Verify interactive_create never calls the API when dry-run is true."""

    from jayrah.create import create as create_module

    called = {"create_issue": False, "confirm_prompts": 0}

    monkeypatch.setattr(create_module, "preview_issue", lambda *args, **kwargs: None)

    def fake_confirm(*args, **kwargs):
        called["confirm_prompts"] += 1
        return True

    monkeypatch.setattr(create_module.click, "confirm", fake_confirm)

    def fake_create_issue(*args, **kwargs):
        called["create_issue"] = True
        return "KEY-1"

    monkeypatch.setattr(create_module, "create_issue", fake_create_issue)

    defaults = {
        "title": "Sample",
        "issuetype": "Task",
        "content": "Body",
        "priority": "Medium",
        "assignee": "user",
        "labels": ["foo"],
        "components": ["comp"],
    }

    jayrah_obj = MagicMock()

    result = create_module.interactive_create(jayrah_obj, defaults, dry_run=True)

    assert result is None
    assert called["confirm_prompts"] == 1
    assert called["create_issue"] is False


def test_build_issue_template_injects_helper_comments():
    """Ensure helper comments listing components and priorities are added for editing."""

    values = {
        "title": "Sample",
        "issuetype": "Task",
        "components": [],
        "labels": [],
        "assignee": "",
        "priority": "",
        "content": "Body text",
    }
    resources = {
        "issuetypes": {"Task": "123"},
        "priorities": ["High", "Medium"],
        "labels": ["team"],
        "components": ["Backend", "Frontend"],
    }

    template = _build_issue_template(values, resources)
    description_section, _ = template.split(defaults.MARKER, maxsplit=1)

    assert (
        "<!-- jayrah-helper: Components: Backend, Frontend -->" in description_section
    )
    assert "<!-- jayrah-helper: Priorities: High, Medium -->" in description_section


def test_parse_editor_submission_strips_helper_comments():
    """Verify helper comments are removed from the returned issue content."""

    values = {
        "title": "Sample",
        "issuetype": "Task",
        "components": [],
        "labels": [],
        "assignee": "",
        "priority": "",
        "content": "Body text",
    }
    resources = {
        "issuetypes": {"Task": "123"},
        "priorities": ["Low"],
        "labels": [],
        "components": ["API"],
    }

    template = _build_issue_template(values, resources)
    updated = _parse_editor_submission(template, values.copy())

    assert updated["__raw_content__"].strip() == "Body text"
    assert "jayrah-helper" not in updated["__raw_content__"]


def test_build_issue_template_handles_quoting():
    """Ensure string values with colons are properly quoted in YAML frontmatter."""

    values = {
        "title": "Bug: Fix something",
        "issuetype": "Bug",
        "components": ["A, B", "C"],
        "labels": [],
        "assignee": "",
        "priority": "",
        "content": "Body text",
    }
    resources = {
        "issuetypes": {"Bug": "1"},
        "priorities": [],
        "labels": [],
        "components": [],
        "required_fields": {},
    }

    template = _build_issue_template(values, resources)

    # Check that it contains the quoted title
    assert (
        "title: 'Bug: Fix something'" in template
        or 'title: "Bug: Fix something"' in template
    )

    # Verify it parses back correctly
    updated = _parse_editor_submission(template, values.copy())
    assert updated["title"] == "Bug: Fix something"
