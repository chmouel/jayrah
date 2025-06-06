import os

import click
import jira2markdown
from rich.prompt import Prompt

from .. import utils
# from ..ui.fzf import select as select
from ..utils import issue_view

issue_template = """---
title: {summary}
type: {issuetype}
components: {components}
---
{content}"""

default_content = """## Description

Please provide a clear and concise description of the issue or feature.

## Steps to Reproduce (for bugs)

1. Step one
2. Step two
3. ...

## Expected Behavior

Describe what you expected to happen.

## Actual Behavior

Describe what actually happened.

## Acceptance Criteria (for stories/features)

- [ ] Clearly defined acceptance criterion
- [ ] ...

## Additional Information

Add any other context, screenshots, or information here.
"""


def get_smart_defaults(jayrah_obj):
    """Get smart defaults based on context."""
    defaults = {
        "issuetype": "Story",
        "assignee": None,
        "priority": None,
        "labels": [],
        "components": [],
    }

    user_config = jayrah_obj.config
    if user_config.get("create") and isinstance(user_config.get("create"), dict):
        defaults["issuetype"] = user_config["create"].get("type", defaults["issuetype"])
        defaults["priority"] = user_config["create"].get("priority")
        defaults["components"] = user_config["create"].get("components", [])
        defaults["labels"] = user_config["create"].get("labels", defaults["labels"])

    cmdline_config = jayrah_obj.cmdline
    if cmdline_config:
        defaults["issuetype"] = cmdline_config.get("issuetype", defaults["issuetype"])
        defaults["priority"] = cmdline_config.get("priority")
        defaults["components"] = cmdline_config.get("component", defaults["components"])
        defaults["labels"] = cmdline_config.get("labels", defaults["labels"])

    return defaults


def get_description(
    jayrah_obj, summary, issuetype=None, template=None, defaults: dict = None, body=""
):
    """Get issue description using editor or template, supporting per-type config templates."""
    # Try to load template by type from config if not explicitly provided
    if not defaults:
        defaults = {}
    if body != "":
        # If body is provided, use it directly
        content = body
    else:
        if not template and issuetype:
            template = issuetype.lower()
        content = load_template(jayrah_obj, template) if template else None
    if not content:
        content = default_content

    tmpl = f"""---
    title: {summary}
    type: {issuetype}
    """
    if defaults.get("components"):
        tmpl += f"components: {','.join(defaults['components'])}\n"

    tmpl += f"---\n\n{content}"

    edited_text = utils.edit_text_with_editor(tmpl, extension=".md")
    if edited_text.startswith("---"):
        lines = edited_text.splitlines()
        start = lines.index("---")
        end = lines.index("---", start + 1)
        edited_text = "\n".join(lines[:start] + lines[end + 1 :])
    return edited_text.strip() if edited_text else ""


def load_template(jayrah_obj, template_name):
    """Load issue template from config (by type, string or file), user templates dir, or repository."""
    config_templates = jayrah_obj.config.get("templates", {})
    # 1. Check local templates in config (by type)
    if template_name and template_name.lower() in config_templates:
        val = config_templates[template_name.lower()]
        # If it's a string and a valid file path, load the file
        if isinstance(val, str) and os.path.isfile(os.path.expanduser(val)):
            with open(os.path.expanduser(val), "r") as f:
                return f.read()
        # Otherwise, treat as inline template
        return val
    # 2. Check ~/.config/jayrah/templates/{type}.md
    if template_name:
        user_template_path = os.path.expanduser(
            f"~/.config/jayrah/templates/{template_name.lower()}.md"
        )
        if os.path.isfile(user_template_path):
            with open(user_template_path, "r") as f:
                return f.read()
    # 3. Check repository templates
    repo_template = find_repo_template(template_name)
    if repo_template:
        return repo_template
    return None


def find_repo_template(template_name):
    """Find template in repository."""
    # Look for templates in .github/ISSUE_TEMPLATE/ or .jira/templates/
    template_paths = [
        ".github/ISSUE_TEMPLATE/",
        ".jira/templates/",
        ".templates/",
    ]

    for path in template_paths:
        if os.path.exists(path):
            template_file = os.path.join(path, f"{template_name}.md")
            if os.path.exists(template_file):
                with open(template_file, "r") as f:
                    return f.read()

    return None


def preview_issue(
    issuetype, summary, description, priority, assignee, labels, components
):
    """Show issue preview before creation."""

    def format_list(items):
        return ", ".join(items) if items else "None"

    click.secho("\n" + "=" * 30, fg="cyan", bold=True)
    click.secho("         Issue Preview", fg="yellow", bold=True)
    click.secho("=" * 30, fg="cyan", bold=True)

    fields = [
        ("Type", issuetype),
        ("Title", summary),
        ("Priority", priority),
        ("Assignee", assignee or "Unassigned"),
        ("Components", format_list(components)),
        ("Labels", format_list(labels)),
    ]

    for label, value in fields:
        click.secho(f"{label:>10}: ", nl=False, fg="green")
        click.echo(f"{value}")

    click.secho("\nDescription:", fg="magenta", bold=True)

    # Convert Jira markdown to standard markdown and format with gum if available
    markdown_description = jira2markdown.convert(description)
    markdown_description = issue_view.wrap_markdown(markdown_description)
    issue_view.format_with_rich(markdown_description)
    click.echo("\n")


def interactive_create(jayrah_obj):
    """Interactive issue creation flow."""
    defaults = get_smart_defaults(jayrah_obj)
    issuetype = select.issue_type(jayrah_obj) or defaults["issuetype"]
    summary = Prompt.ask("Title")
    description = get_description(
        jayrah_obj, summary, issuetype=issuetype, defaults=defaults
    )
    priority = defaults["priority"]
    assignee = defaults.get("assignee", "")
    labels = defaults["labels"]
    components = defaults["components"]

    # 7. Preview and Confirm
    preview_issue(
        issuetype, summary, description, priority, assignee, labels, components
    )
    if click.confirm("Create issue?"):
        return create_issue(
            jayrah_obj,
            issuetype,
            summary,
            description,
            priority,
            assignee,
            labels,
            components=components,
        )
    return None


def create_issue(
    jayrah_obj, issuetype, summary, description, priority, assignee, labels, components
):
    """Create the issue with the given parameters."""
    try:
        result = jayrah_obj.jira.create_issue(
            issuetype=issuetype,
            summary=summary,
            description=description,
            priority=priority,
            assignee=assignee,
            labels=labels,
            components=components,
        )

        issue_key = result.get("key")
        if issue_key:
            click.secho(f"✅ Issue {issue_key} created successfully!", fg="green")
            click.echo(
                f"URL: {utils.make_full_url(issue_key, jayrah_obj.config.get('jira_server'))}"
            )
            return issue_key
    except Exception as e:
        click.secho(f"❌ Error creating issue: {str(e)}", fg="red")
        return None
