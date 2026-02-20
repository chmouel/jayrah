"""Issue creation utilities for Jayrah."""

import difflib
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import click
import jira2markdown
import yaml

from .. import utils
from ..utils import issue_view, markdown_to_jira
from . import defaults
from . import template_loader as tpl

HELPER_COMMENT_PREFIX = "<!-- jayrah-helper:"


def _suggest_epic_name(title):
    """Suggest an epic name based on the title."""
    # Format: lowercase, alphanumeric and dashes only
    epic_name = re.sub(r"[^a-zA-Z0-9\s-]", "", title).lower()
    return re.sub(r"[\s-]+", "-", epic_name).strip("-")


def _choose_priority(priorities):
    """Interactively choose a priority using gum if available."""
    options = ["None"] + priorities

    # Try using gum
    import shutil
    import subprocess
    import sys

    if shutil.which("gum"):
        try:
            # We must NOT capture_output=True because gum needs to draw its TUI
            # to stderr/stdout. We only want to capture the final choice from stdout.
            # We use a context manager or just run it and hope for the best with pipes.
            result = subprocess.run(
                ["gum", "choose"] + options,
                stdout=subprocess.PIPE,
                stderr=sys.stderr,  # UI usually goes to stderr
                stdin=sys.stdin,  # Input from terminal
                text=True,
                check=False,
            )
            if result.returncode == 0:
                choice = result.stdout.strip()
                return "" if choice == "None" else choice
            # If user aborted gum (e.g. Ctrl-C), we treat it as no change/None
            return ""
        except Exception:
            pass

    # Fallback to click.prompt

    click.echo("\nAvailable Priorities:")
    for i, p in enumerate(options):
        click.echo(f"{i}) {p}")

    choice_idx = click.prompt(
        "Select a priority (number)",
        type=click.IntRange(0, len(options) - 1),
        default=0,
    )
    choice = options[choice_idx]
    return "" if choice == "None" else choice


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

    resources = _collect_issue_resources(jayrah_obj, issuetype=issuetype)

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

    # If it's an epic and we don't have an epic name, suggest one from title
    if values["issuetype"].lower() == "epic" and not values.get("epic_name"):
        values["epic_name"] = _suggest_epic_name(values["title"])

    while True:
        editor_payload = _build_issue_template(values, resources)
        edited_text = utils.edit_text_with_editor(editor_payload, extension=".md")

        if edited_text.strip() == "":
            raise click.ClickException("Issue description cannot be empty.")

        try:
            values = _parse_editor_submission(edited_text, values)

            # If priority is missing, ask the user to choose one
            if not values.get("priority") and resources.get("priorities"):
                if click.confirm(
                    "Priority is missing. Would you like to select one?", default=True
                ):
                    values["priority"] = _choose_priority(resources["priorities"])

            if values["issuetype"].lower() == "epic" and not values.get("epic_name"):
                suggested = _suggest_epic_name(values["title"])
                if click.confirm(
                    f"Epic Name is missing. Use suggested name '{suggested}'?",
                    default=True,
                ):
                    values["epic_name"] = suggested
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

    ret = {
        "content": values["content"],
        "components": values["components"],
        "title": values["title"],
        "issuetype": values["issuetype"],
        "labels": values["labels"],
        "priority": values["priority"],
        "assignee": values["assignee"],
    }
    if "epic_name" in values:
        ret["epic_name"] = values["epic_name"]

    # Include any custom fields
    ret.update(
        {key: value for key, value in values.items() if key.startswith("customfield_")}
    )

    return ret


def preview_issue(
    issuetype, title, content, priority, assignee, labels, components, extra_fields=None
):
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

    if extra_fields:
        if "epic_name" in extra_fields:
            fields.insert(2, ("Epic Name", extra_fields["epic_name"]))
        for key, value in extra_fields.items():
            if key.startswith("customfield_"):
                fields.append((key, value))

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
        # Separate extra fields (epic_name and customfields) from base fields
        base_keys = {
            "issuetype",
            "title",
            "content",
            "priority",
            "assignee",
            "labels",
            "components",
        }
        extra_fields = {k: v for k, v in current.items() if k not in base_keys}

        preview_issue(
            issuetype=current["issuetype"],
            title=current["title"],
            content=current["content"],
            priority=current["priority"],
            assignee=current["assignee"],
            labels=current["labels"],
            components=current["components"],
            extra_fields=extra_fields,
        )

        if dry_run:
            click.secho(
                "Dry run enabled: no changes will be sent to Jira.", fg="yellow"
            )

        if not click.confirm("Create issue?", default=True):
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
            extra_fields=extra_fields,
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
    jayrah_obj,
    issuetype,
    summary,
    description,
    priority,
    assignee,
    labels,
    components,
    extra_fields=None,
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

        # Handle epic_name mapping
        final_extra_fields = {}
        if extra_fields:
            for key, value in extra_fields.items():
                if key == "epic_name":
                    field_id = _get_epic_name_field_id(jayrah_obj)
                    if field_id:
                        final_extra_fields[field_id] = value
                    else:
                        click.secho(
                            "Warning: Could not find 'Epic Name' field ID. Skipping epic name.",
                            fg="yellow",
                        )
                else:
                    final_extra_fields[key] = value

        result = jayrah_obj.jira.create_issue(
            issuetype=issuetype,
            summary=summary,
            description=description,
            priority=priority,
            assignee=assignee,
            labels=labels,
            components=components,
            extra_fields=final_extra_fields,
        )

        issue_key = result.get("key")
        if issue_key:
            click.secho(f"✅ Issue {issue_key} created successfully!", fg="green")
            click.echo(
                f"URL: {utils.make_full_url(issue_key, jayrah_obj.config.get('jira_server'))}"
            )
            return issue_key
    except Exception as e:
        click.secho(f"❌ Error creating issue: {e!s}", fg="red")

    return ""


def _get_epic_name_field_id(jayrah_obj):
    """Try to find the custom field ID for 'Epic Name'."""
    # Check config first
    config_field = jayrah_obj.config.get("epic_name_field")
    if config_field:
        return config_field

    # Try to find it in the internal cache
    cached_id = jayrah_obj.jira.cache.get("internal://epic_name_field_id")
    if cached_id:
        return cached_id

    # Try to find it in the fields list
    try:
        fields = jayrah_obj.jira.get_fields()
        for field in fields:
            if field.get("name") == "Epic Name":
                field_id = field.get("id")
                if field_id:
                    jayrah_obj.jira.cache.set("internal://epic_name_field_id", field_id)
                return field_id
    except Exception:
        pass

    return None


def _collect_issue_resources(jayrah_obj, issuetype=None):
    """Gather available issue metadata from Jira and config."""

    project_key = jayrah_obj.config.get("jira_project")

    # Fetch issue types once BEFORE parallel requests to enable reuse
    issuetypes = jayrah_obj.jira.get_issue_types(use_cache=True)

    with ThreadPoolExecutor() as executor:
        # Pass cached issue types to avoid duplicate API calls
        future_priorities = executor.submit(
            jayrah_obj.jira.get_project_priorities,
            issuetype=issuetype,
            issue_types_cache=issuetypes,
        )
        future_labels = executor.submit(jayrah_obj.jira.get_labels)
        future_components = executor.submit(jayrah_obj.jira.get_components)
        future_meta = (
            executor.submit(jayrah_obj.jira.get_createmeta, project_key, issuetype)
            if project_key and issuetype
            else None
        )

        # Collect results with error handling for non-critical failures
        priorities = []
        raw_labels = []
        components = []
        meta = {}

        try:
            priorities = future_priorities.result()
        except Exception as e:
            if jayrah_obj.verbose:
                utils.log(f"Warning: Failed to fetch priorities: {e}")
            # Continue with empty priorities

        try:
            raw_labels = future_labels.result()
        except Exception as e:
            if jayrah_obj.verbose:
                utils.log(f"Warning: Failed to fetch labels: {e}")
            # Continue with empty labels

        try:
            components = future_components.result()
        except Exception as e:
            if jayrah_obj.verbose:
                utils.log(f"Warning: Failed to fetch components: {e}")
            # Continue with empty components

        if future_meta:
            try:
                meta = future_meta.result()
            except Exception as e:
                if jayrah_obj.verbose:
                    utils.log(f"Warning: Failed to fetch metadata: {e}")
                # Continue with empty meta

    required_fields = {}
    if meta and "projects" in meta:
        for project in meta["projects"]:
            if project["key"] == project_key:
                for it in project.get("issuetypes", []):
                    if it["name"] == issuetype:
                        fields = it.get("fields", {})
                        for field_key, field_info in fields.items():
                            if field_info.get("required"):
                                # Skip standard fields we already handle
                                if field_key in {
                                    "summary",
                                    "issuetype",
                                    "project",
                                    "priority",
                                    "components",
                                    "description",
                                    "assignee",
                                    "labels",
                                    "reporter",
                                }:
                                    continue
                                required_fields[field_key] = field_info.get("name")

    labels_exclude = jayrah_obj.config.get("label_excludes", "")
    labels_exclude_re = re.compile(labels_exclude.strip()) if labels_exclude else None

    labels = [
        label
        for label in raw_labels
        if label and (not labels_exclude_re or not labels_exclude_re.match(label))
    ]

    return {
        "issuetypes": issuetypes,
        "priorities": priorities,
        "labels": labels,
        "components": components,
        "required_fields": required_fields,
    }


def _issue_helper_comments(resources):
    """Return inline helper comments listing available components and priorities."""

    available_components = ", ".join(resources.get("components", [])) or "None"
    available_priorities = ", ".join(resources.get("priorities", [])) or "None"

    lines = [
        f"{HELPER_COMMENT_PREFIX} Components: {available_components} -->",
        f"{HELPER_COMMENT_PREFIX} Priorities: {available_priorities} -->",
    ]
    return "\n".join(lines)


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

    # Build the YAML front matter using safe_dump to handle quoting
    frontmatter_data = {
        "title": values.get("title", ""),
        "type": issuetype_value,
    }

    if issuetype_value.lower() == "epic":
        frontmatter_data["epic-name"] = values.get("epic_name", values.get("title", ""))

    frontmatter_data["components"] = components_value
    frontmatter_data["labels"] = labels_value
    frontmatter_data["assignee"] = values.get("assignee", "")
    frontmatter_data["priority"] = values.get("priority", "")

    # Add any other custom fields
    frontmatter_data.update(
        {key: value for key, value in values.items() if key.startswith("customfield_")}
    )

    # Dump the main part preserving order
    yaml_str = yaml.safe_dump(
        frontmatter_data,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    ).strip()

    # Add required fields that are not yet in values (appended manually to include comments)
    missing_required_lines = []
    required_fields = resources.get("required_fields", {})
    for field_id, field_name in required_fields.items():
        if field_id not in values and field_id not in {
            k.replace("-", "_") for k in values
        }:
            missing_required_lines.append(f"{field_id}: <required> # {field_name}")

    template = "---\n" + yaml_str
    if missing_required_lines:
        template += "\n" + "\n".join(missing_required_lines)
    template += "\n---\n"
    template += f"{content_value.strip() or defaults.DEFAULT_CONTENT}\n\n"
    template += f"{_issue_helper_comments(resources)}\n\n"
    template += f"{defaults.MARKER}\n\n"
    template += "## Available Fields (just for reference to copy and paste easily)\n\n"
    template += "### Issue Types\n\n" + "\n".join(allissuetypes_f) + "\n\n"
    template += "### Components\n\n" + "\n".join(allcomponents_f) + "\n\n"
    template += "### Labels\n\n" + "\n".join(alllabels_f) + "\n\n"
    template += "### Priorities\n\n" + "\n".join(allpriorities_f) + "\n"

    return template


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
            # Find the indices of the first two --- delimiters
            indices = [i for i, line in enumerate(lines) if line.strip() == "---"]
            if len(indices) < 2:
                raise click.ClickException(
                    "Template front matter is malformed; unable to locate delimiters."
                )

            start, end = indices[0], indices[1]
            yaml_section = "\n".join(lines[start + 1 : end])
            text = "\n".join(lines[end + 1 :])

            data = yaml.safe_load(yaml_section)
            if isinstance(data, dict):
                mapping = {
                    "type": "issuetype",
                    "epic-name": "epic_name",
                }
                for key, value in data.items():
                    key_lower = str(key).lower()
                    target_key = mapping.get(key_lower, key_lower)

                    if target_key in {"components", "labels"}:
                        updated[target_key] = _normalize_list(value)
                    elif target_key:
                        updated[target_key] = str(value) if value is not None else ""
        except yaml.YAMLError as exc:
            raise click.ClickException(
                f"Error parsing YAML front matter: {exc}"
            ) from exc

    description = text.split(defaults.MARKER)[0].rstrip()
    description = _strip_helper_comments(description)
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
        matches = difflib.get_close_matches(priority, priorities)
        if matches:
            errors.append(
                f"Priority '{priority}' is not available. Did you mean '{matches[0]}'?"
            )
        else:
            available_priorities = ", ".join(priorities) or "None"
            errors.append(
                f"Priority '{priority}' is not available. Available priorities: {available_priorities}"
            )

    selected_components = values.get("components", [])
    for comp in selected_components:
        if comp not in components:
            matches = difflib.get_close_matches(comp, components)
            if matches:
                errors.append(
                    f"Component '{comp}' is not available. Did you mean '{matches[0]}'?"
                )
            else:
                available_components = ", ".join(components) or "None"
                errors.append(
                    f"Component '{comp}' is not available. Available components: {available_components}"
                )

    if issuetype.lower() == "epic":
        # Check if epic_name is present or any customfield that might be epic name
        has_epic_name = values.get("epic_name")
        if not has_epic_name:
            for key in values:
                if key.startswith("customfield_"):
                    has_epic_name = True
                    break

        if not has_epic_name:
            errors.append("Epic Name is required for Epic issues.")

    # Check for missing required fields
    for key, value in values.items():
        if str(value).strip() == "<required>":
            errors.append(f"Field '{key}' is required.")

    return errors


def _strip_helper_comments(description):
    """Remove inline helper comments injected for editor guidance."""

    lines = description.splitlines()
    filtered = [
        line for line in lines if not line.strip().startswith(HELPER_COMMENT_PREFIX)
    ]

    while filtered and filtered[-1].strip() == "":
        filtered.pop()

    return "\n".join(filtered).rstrip()


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

    resources = _collect_issue_resources(jayrah_obj, issuetype=values.get("issuetype"))
    template_text = _build_issue_template(values, resources)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    draft_path = Path.cwd() / f"jayrah_issue_draft_{timestamp}.md"
    draft_path.write_text(template_text, encoding="utf-8")
    return draft_path
