"""Issue creation utilities for Jayrah."""

import re

import click
import jira2markdown

from .. import utils
from ..utils import issue_view, markdown_to_jira
from . import defaults
from . import template_loader as tpl


def create_edit_issue(
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

    allissuetypes = jayrah_obj.jira.get_issue_types()
    if issuetype and issuetype not in allissuetypes:
        raise click.ClickException(
            f"Issue type '{issuetype}' is not available. Available types: {', '.join(allissuetypes)}"
        )
    allissuetypes_f = [f"- {k.strip()}" for k in allissuetypes]
    allpriorities = [k["name"].strip() for k in jayrah_obj.jira.get_priorities()]
    allpriorities_f = [f"- {k.strip()}" for k in allpriorities]

    labels_exclude = jayrah_obj.config.get("label_excludes", "")
    labels_exclude_re = re.compile(labels_exclude.strip()) if labels_exclude else None

    alllabels = jayrah_obj.jira.get_labels()
    alllabels_f = [
        f"- {k}"
        for k in alllabels
        if k and (not labels_exclude_re or not labels_exclude_re.match(k))
    ]
    allcomponents = jayrah_obj.jira.get_components()
    allcomponents_f = [f"- {k}" for k in allcomponents]

    tmpl = content
    if not content.strip().startswith("---"):
        tmpl = defaults.ISSUE_TEMPLATE.format(
            title=title or "",
            issuetype=issuetype or list(allissuetypes.keys())[0],
            content=content.strip(),
            components=",".join(components) if components else "",
            labels=",".join(labels) if labels else "",
            assignee=assignee or "",
            priority=priority or "",
            marker=defaults.MARKER,
            allcomponents="\n".join(allcomponents_f),
            alllabels="\n".join(alllabels_f),
            allpriorities="\n".join(allpriorities_f),
            allissuetypes="\n".join(allissuetypes_f),
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
                # # pylint: disable=W0511
                # TODO: Offer to choose from available types if not found
                if issuetype not in allissuetypes:
                    raise click.ClickException(
                        f"Issue type '{issuetype}' is not available. Available types: {', '.join(allissuetypes)}"
                    )
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

    # Remove everything after the marker
    edited_text = edited_text.split(defaults.MARKER)[0].strip()

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
        # Convert markdown description to appropriate format based on API version
        if jayrah_obj.config.get("api_version") == "2":
            description = markdown_to_jira.convert(description)
        elif jayrah_obj.config.get("api_version") == "3":
            description = markdown_to_jira.convert_v3(description)
        else:
            raise click.ClickException(
                "Unsupported API version. Please use API v2 or v3."
            )

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
