"""Issue creation utilities for Jayrah."""

import click
import jira2markdown

from .. import utils
from ..utils import adf, issue_view, markdown_to_jira
from . import defaults
from . import template_loader as tpl


def get_description(
    jayrah_obj,
    title,
    issuetype=None,
    template=None,
    components=None,
    labels=None,
    assignee=None,
    priority=None,
    body="",
):
    """Get issue description using editor or template, supporting per-type config templates."""
    # Try to load template by type from config if not explicitly provided
    if body != "":
        # If body is provided, use it directly
        content = body
    else:
        if not template and issuetype:
            template = issuetype.lower()
        content = tpl.load_template(jayrah_obj, template) if template else None
    if not content:
        content = defaults.DEFAULT_CONTENT

    tmpl = content
    if not content.strip().startswith("---"):
        tmpl = defaults.ISSUE_TEMPLATE.format(
            title=title or "",
            issuetype=issuetype or "Story",
            content=content,
            components=",".join(components) if components else "",
            labels=",".join(labels) if labels else "",
            assignee=assignee or "",
            priority=priority or "",
        )

    edited_text = utils.edit_text_with_editor(tmpl, extension=".md")
    if edited_text.strip() == "":
        raise click.ClickException("Issue description cannot be empty.")

    if edited_text.startswith("---"):
        lines = edited_text.splitlines()
        start = lines.index("---")
        end = lines.index("---", start + 1)
        yaml_section = lines[start + 1 : end]
        for line in yaml_section:
            line = line.strip()
            if line.startswith("type"):
                issuetype = line.split(":")[1].strip()
            elif line.startswith("components"):
                components = (
                    line.split(":")[1].strip().split(",") if ":" in line else []
                )
                components = [c.strip() for c in components if c.strip()]
            elif line.startswith("title"):
                title = line.split(":")[1].strip()
            elif line.startswith("labels"):
                labels = line.split(":")[1].strip().split(",") if ":" in line else []
                labels = [label.strip() for label in labels if label.strip()]
            elif line.startswith("assignee"):
                assignee = line.split(":")[1].strip() if ":" in line else ""
            elif line.startswith("priority"):
                priority = line.split(":")[1].strip() if ":" in line else ""
        edited_text = "\n".join(lines[:start] + lines[end + 1 :])

    if not issuetype:
        raise click.ClickException("Issue type must be specified in the template.")

    if title.strip() == "":
        raise click.ClickException("Issue title cannot be empty.")

    dico = {
        "content": edited_text,
        "components": components,
        "title": title,
        "issuetype": issuetype,
        "labels": labels,
        "priority": priority,
        "assignee": assignee,
    }
    return dico


def preview_issue(issuetype, title, content, priority, assignee, labels, components):
    """Show issue preview before creation."""

    def format_list(items):
        return ", ".join(items) if items else "None"

    fields = [
        ("Type", issuetype),
        ("Title", title),
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
    markdown_description = jira2markdown.convert(content)
    markdown_description = issue_view.wrap_markdown(markdown_description)
    issue_view.format_with_rich(markdown_description)
    click.echo("\n")


def interactive_create(jayrah_obj, defaults):
    """Interactive issue creation flow."""

    # 7. Preview and Confirm
    preview_issue(
        issuetype=defaults["issuetype"],
        title=defaults["title"],
        content=defaults["content"],
        priority=defaults["priority"],
        assignee=defaults["assignee"],
        labels=defaults["labels"],
        components=defaults["components"],
    )

    if click.confirm("Create issue?"):
        return create_issue(
            jayrah_obj,
            defaults["issuetype"],
            defaults["title"],
            defaults["content"],
            defaults["priority"],
            defaults["assignee"],
            defaults["labels"],
            defaults["components"],
        )
    return None


def create_issue(
    jayrah_obj, issuetype, summary, description, priority, assignee, labels, components
):
    """Create the issue with the given parameters."""
    try:
        # Convert markdown description to Jira markdown if using API v2
        description = markdown_to_jira.convert(description)

        # Convert markdown description to ADF if using API v3
        if jayrah_obj.config.get("api_version") == "3":
            description = adf.create_adf_from_text(description)

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

    return ""
