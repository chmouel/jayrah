"""Issue creation utilities for Jayrah."""

from datetime import datetime
from pathlib import Path
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
    initial_values=None,
):
    """Open the editor, validate metadata, and return the finalized issue payload."""

    resources = _collect_issue_resources(jayrah_obj)

    values = {
        "title": title or "",
        "issuetype": issuetype or _default_issue_type(resources),
        "components": _normalize_list(components),
        "labels": _normalize_list(labels),
        "assignee": (assignee or "").strip(),
        "priority": (priority or "").strip(),
        "content": body or "",
    }

    if initial_values:
        for key, val in initial_values.items():
            if val is None:
                continue
            if key in {"components", "labels"}:
                values[key] = _normalize_list(val)
            elif key == "content":
                values[key] = val
            else:
                values[key] = val.strip() if isinstance(val, str) else val

    base_content = _resolve_initial_content(
        jayrah_obj, template, values["issuetype"], resources, values["content"]
    )
    if not values["content"]:
        values["content"] = base_content

    while True:
        editor_payload = _build_issue_template(values, resources)
        edited_text = utils.edit_text_with_editor(editor_payload, extension=".md")

        if edited_text.strip() == "":
            raise click.ClickException("Issue description cannot be empty.")

        try:
            values = _parse_editor_submission(edited_text, values)
        except click.ClickException:
            raise
        except Exception as exc:  # pragma: no cover - defensive, should not happen
            raise click.ClickException(f"Unable to parse template: {exc}") from exc

        description = values.pop("__raw_content__", "")
        if not description.strip():
            raise click.ClickException("Issue description cannot be empty.")

        errors = _validate_issue_values(values, resources)
        if errors:
            click.secho("Found issues with the template values:", fg="red")
            for error in errors:
                click.secho(f"- {error}", fg="red")
            if click.confirm("Open editor to fix these values?", default=True):
                values["content"] = description
                continue
            raise click.ClickException(
                "Issue creation aborted due to invalid metadata."
            )

        values["content"] = description
        break

    return {
        "content": values["content"],
        "components": values["components"],
        "title": values["title"],
        "issuetype": values["issuetype"],
        "labels": values["labels"],
        "priority": values["priority"],
        "assignee": values["assignee"],
    }


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


def interactive_create(jayrah_obj, defaults, dry_run=False):
    """Interactive issue creation with optional dry-run and retry support."""

    current = defaults

    while True:
        preview_issue(
            issuetype=current["issuetype"],
            title=current["title"],
            content=current["content"],
            priority=current["priority"],
            assignee=current["assignee"],
            labels=current["labels"],
            components=current["components"],
        )

        if dry_run:
            click.secho(
                "Dry run enabled: no changes will be sent to Jira.", fg="yellow"
            )

        if not click.confirm("Create issue?"):
            if click.confirm("Re-open the editor before aborting?", default=False):
                current = create_edit_issue(
                    jayrah_obj,
                    current["title"],
                    current["issuetype"],
                    components=current["components"],
                    labels=current["labels"],
                    assignee=current["assignee"],
                    priority=current["priority"],
                    body=current["content"],
                    initial_values=current,
                )
                continue
            click.secho("Issue creation cancelled.", fg="yellow")
            return None

        if dry_run:
            click.secho(
                "Dry run complete: review the preview above, then run without --dry-run to submit.",
                fg="green",
            )
            return None

        issue_key = create_issue(
            jayrah_obj,
            current["issuetype"],
            current["title"],
            current["content"],
            current["priority"],
            current["assignee"],
            current["labels"],
            current["components"],
        )

        if issue_key:
            return issue_key

        click.secho("Issue creation failed.", fg="red")
        if click.confirm("Re-open the editor to adjust before retrying?", default=True):
            current = create_edit_issue(
                jayrah_obj,
                current["title"],
                current["issuetype"],
                components=current["components"],
                labels=current["labels"],
                assignee=current["assignee"],
                priority=current["priority"],
                body=current["content"],
                initial_values=current,
            )
            continue

        if click.confirm("Save this issue as a draft file?", default=True):
            draft_path = save_issue_draft(jayrah_obj, current)
            click.secho(f"Draft saved to {draft_path}", fg="yellow")
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


def _collect_issue_resources(jayrah_obj):
    """Gather available issue metadata from Jira and config."""

    issuetypes = jayrah_obj.jira.get_issue_types()

    priorities_raw = jayrah_obj.jira.get_priorities()
    priorities = [item["name"].strip() for item in priorities_raw if item.get("name")]

    labels_exclude = jayrah_obj.config.get("label_excludes", "")
    labels_exclude_re = re.compile(labels_exclude.strip()) if labels_exclude else None

    labels = [
        label
        for label in jayrah_obj.jira.get_labels()
        if label and (not labels_exclude_re or not labels_exclude_re.match(label))
    ]

    components = jayrah_obj.jira.get_components()

    return {
        "issuetypes": issuetypes,
        "priorities": priorities,
        "labels": labels,
        "components": components,
    }


def _build_issue_template(values, resources):
    """Render the issue template with the current values and reference data."""

    issuetype_names = list(resources["issuetypes"].keys())
    issuetype_value = values.get("issuetype") or _default_issue_type(resources)
    components_value = ",".join(values.get("components", []))
    labels_value = ",".join(values.get("labels", []))
    content_value = values.get("content", defaults.DEFAULT_CONTENT)

    allissuetypes_f = [f"- {name.strip()}" for name in issuetype_names]
    allcomponents_f = [f"- {name}" for name in resources["components"]]
    alllabels_f = [f"- {name}" for name in resources["labels"]]
    allpriorities_f = [f"- {name}" for name in resources["priorities"]]

    return defaults.ISSUE_TEMPLATE.format(
        title=values.get("title", ""),
        issuetype=issuetype_value,
        content=content_value.strip() or defaults.DEFAULT_CONTENT,
        components=components_value,
        labels=labels_value,
        assignee=values.get("assignee", ""),
        priority=values.get("priority", ""),
        marker=defaults.MARKER,
        allcomponents="\n".join(allcomponents_f) if allcomponents_f else "- None",
        alllabels="\n".join(alllabels_f) if alllabels_f else "- None",
        allpriorities="\n".join(allpriorities_f) if allpriorities_f else "- None",
        allissuetypes="\n".join(allissuetypes_f) if allissuetypes_f else "- None",
    )


def _parse_editor_submission(edited_text, current_values):
    """Parse the edited template and return updated values with raw content."""

    updated = {
        "title": current_values.get("title", ""),
        "issuetype": current_values.get("issuetype", ""),
        "components": _normalize_list(current_values.get("components")),
        "labels": _normalize_list(current_values.get("labels")),
        "assignee": current_values.get("assignee", ""),
        "priority": current_values.get("priority", ""),
    }

    text = edited_text
    if edited_text.strip().startswith("---"):
        lines = edited_text.splitlines()
        try:
            start = lines.index("---")
            end = lines.index("---", start + 1)
        except ValueError as exc:
            raise click.ClickException(
                "Template front matter is malformed; unable to locate delimiters."
            ) from exc

        yaml_section = lines[start + 1 : end]
        for raw_line in yaml_section:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()

            if key == "type":
                updated["issuetype"] = value
            elif key == "components":
                updated["components"] = _normalize_list(value.split(","))
            elif key == "labels":
                updated["labels"] = _normalize_list(value.split(","))
            elif key == "assignee":
                updated["assignee"] = value
            elif key == "priority":
                updated["priority"] = value
            elif key == "title":
                updated["title"] = value

        text = "\n".join(lines[end + 1 :])

    description = text.split(defaults.MARKER)[0].rstrip()
    updated["__raw_content__"] = description
    return updated


def _validate_issue_values(values, resources):
    """Return a list of validation errors for the supplied issue values."""

    errors = []
    issuetypes = resources["issuetypes"]
    priorities = resources["priorities"]
    components = resources["components"]

    issuetype = values.get("issuetype", "").strip()
    if not issuetype:
        errors.append("Issue type must be provided.")
    elif issuetype not in issuetypes:
        available_types = list(issuetypes.keys())
        available_list = ", ".join(available_types) or "None"
        errors.append(
            f"Issue type '{issuetype}' is not available. Available types: {available_list}"
        )

    title = values.get("title", "").strip()
    if not title:
        errors.append("Issue title cannot be empty.")

    priority = values.get("priority", "").strip()
    if priority and priority not in priorities:
        available_priorities = ", ".join(priorities) or "None"
        errors.append(
            f"Priority '{priority}' is not available. Available priorities: {available_priorities}"
        )

    selected_components = values.get("components", [])
    invalid_components = [c for c in selected_components if c not in components]
    if invalid_components:
        invalid_list = ", ".join(invalid_components)
        available_components = ", ".join(components) or "None"
        errors.append(
            f"Component(s) {invalid_list} are not available. Available components: {available_components}"
        )

    return errors


def _default_issue_type(resources):
    """Return the first available issue type name."""

    issuetypes = list(resources.get("issuetypes", {}).keys())
    return issuetypes[0] if issuetypes else ""


def _normalize_list(value):
    """Normalize a sequence/CSV string into a list of trimmed strings."""

    if not value:
        return []
    if isinstance(value, str):
        items = [segment.strip() for segment in value.split(",")]
    else:
        items = [str(segment).strip() for segment in value]
    return [item for item in items if item]


def _resolve_initial_content(
    jayrah_obj, template, issuetype, resources, current_content
):
    """Determine the initial body content shown in the editor."""

    if current_content:
        return current_content

    selected_template = template
    if not selected_template and issuetype:
        selected_template = issuetype.lower()

    if selected_template:
        loaded = tpl.load_template(jayrah_obj, selected_template)
        if loaded:
            return loaded

    fallback_type = _default_issue_type(resources)
    if fallback_type and fallback_type != issuetype:
        loaded = tpl.load_template(jayrah_obj, fallback_type.lower())
        if loaded:
            return loaded

    return defaults.DEFAULT_CONTENT


def save_issue_draft(jayrah_obj, values):
    """Persist the current issue payload to a timestamped markdown file."""

    resources = _collect_issue_resources(jayrah_obj)
    template_text = _build_issue_template(values, resources)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    draft_path = Path.cwd() / f"jayrah_issue_draft_{timestamp}.md"
    draft_path.write_text(template_text, encoding="utf-8")
    return draft_path
