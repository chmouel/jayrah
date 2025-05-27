import os
import subprocess

import click
from rich.prompt import Prompt

from .. import utils
from ..ui.fzf import fzf_select


def get_smart_defaults(jayrah_obj):
    """Get smart defaults based on context."""
    defaults = {
        "issuetype": jayrah_obj.config.get("default_issuetype", "Story"),
        "assignee": jayrah_obj.config.get("default_assignee"),
        "priority": jayrah_obj.config.get("default_priority"),
        "labels": jayrah_obj.config.get("default_labels", []),
    }

    # Try to get branch name for title suggestion
    try:
        branch = (
            subprocess.check_output(["git", "branch", "--show-current"])
            .decode()
            .strip()
        )
        if branch:
            defaults["title_suggestion"] = branch.replace("-", " ").title()
    except Exception:
        pass

    return defaults


def select_issue_type(jayrah_obj):
    """Select issue type using fzf."""
    issue_types = jayrah_obj.jira.get_issue_types()
    return fzf_select(
        "Select issue type",
        [it["name"] for it in issue_types],
        default=jayrah_obj.config.get("default_issuetype", "Story"),
    )


def select_priority(jayrah_obj):
    """Select priority using fzf."""
    priorities = jayrah_obj.jira.get_priorities()
    return fzf_select(
        "Select priority",
        [p["name"] for p in priorities],
        default=jayrah_obj.config.get("default_priority", "Medium"),
    )


def select_assignee(jayrah_obj):
    """Select assignee using fzf."""
    users = jayrah_obj.jira.get_users()
    return fzf_select(
        "Select assignee",
        [u["displayName"] for u in users],
        default=jayrah_obj.config.get("default_assignee"),
    )


def select_labels(jayrah_obj):
    """Select labels using fzf."""
    labels = jayrah_obj.jira.get_labels()
    return fzf_select(
        "Select labels",
        labels,
        multi=True,
        default="all" if jayrah_obj.config.get("default_labels") else None,
    )


def get_description(jayrah_obj, summary, issuetype=None, template=None):
    """Get issue description using editor or template, supporting per-type config templates."""
    # Try to load template by type from config if not explicitly provided
    if not template and issuetype:
        template = issuetype.lower()
    content = (
        load_template(jayrah_obj, template)
        if template
        else create_default_template(summary, issuetype)
    )
    editor_text = ("---\ntitle: {summary}\ntype: {issuetype}\n---\n\n{content}").format(
        summary=summary, issuetype=issuetype or "", content=content
    )
    return utils.edit_text_with_editor(editor_text, extension=".md")


def create_default_template(summary, issuetype=None):
    """Create a default template with common sections, markdownlint clean."""
    return (
        "\n"
        "## Description\n"
        "\n"
        "(Describe the issue here)\n"
        "\n"
        "## Acceptance Criteria\n"
        "\n"
        "- [ ] (Add acceptance criteria here)\n"
        "\n"
        "## Additional Information\n"
        "\n"
        "(Add any additional information here)\n"
    )


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


def preview_issue(issuetype, summary, description, priority, assignee, labels):
    """Show issue preview before creation."""
    click.echo("\n=== Issue Preview ===")
    click.echo(f"Type: {issuetype}")
    click.echo(f"Title: {summary}")
    click.echo(f"Priority: {priority}")
    click.echo(f"Assignee: {assignee}")
    click.echo(f"Labels: {', '.join(labels)}")
    click.echo("\nDescription:")
    click.echo(description)
    click.echo("===================\n")


def validate_issue(issuetype, summary, description):
    """Validate issue fields."""
    if not summary:
        raise click.UsageError("Title is required")
    if not description:
        raise click.UsageError("Description is required")
    if not issuetype:
        raise click.UsageError("Issue type is required")


def interactive_create(jayrah_obj):
    """Interactive issue creation flow."""
    # Get smart defaults
    defaults = get_smart_defaults(jayrah_obj)

    # 1. Issue Type Selection
    issuetype = select_issue_type(jayrah_obj) or defaults["issuetype"]

    # 2. Title/Summary
    summary = Prompt.ask("Title", default=defaults.get("title_suggestion", ""))

    # 3. Description (pass issuetype)
    description = get_description(jayrah_obj, summary, issuetype=issuetype)

    # 4. Priority
    priority = select_priority(jayrah_obj) or defaults["priority"]

    # 5. Assignee (direct input instead of selection)
    assignee = Prompt.ask("Assignee username", default=defaults.get("assignee", ""))

    # 6. Labels
    labels = select_labels(jayrah_obj) or defaults["labels"]

    # 7. Preview and Confirm
    preview_issue(issuetype, summary, description, priority, assignee, labels)
    if click.confirm("Create issue?"):
        return create_issue(
            jayrah_obj, issuetype, summary, description, priority, assignee, labels
        )
    return None


def create_issue(
    jayrah_obj, issuetype, summary, description, priority, assignee, labels
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
