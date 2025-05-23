import os
import shutil
import textwrap
from datetime import datetime

import click
import jira2markdown

from jayrah import utils
from jayrah.config import defaults


def get_terminal_width() -> int:
    terminal_width = None
    try:
        # Prefer FZF_PREVIEW_COLUMNS if set
        terminal_width = int(os.getenv("FZF_PREVIEW_COLUMNS", os.getenv("COLUMNS", "")))
    except (TypeError, ValueError):
        # Fallback if FZF_PREVIEW_COLUMNS or COLUMNS is not set or invalid
        terminal_width = None

    # Step 2: Use shutil.get_terminal_size() if FZF variables are not available
    if terminal_width is None:
        try:
            terminal_width = shutil.get_terminal_size((80, 20)).columns
        except OSError:
            # Final fallback to 80 characters if terminal size cannot be determined
            terminal_width = 80
    if terminal_width >= 130:
        terminal_width = 130
    elif terminal_width < 80:
        terminal_width = 80

    return terminal_width


def wrap_markdown(text):
    """Wrap markdown text to terminal width"""
    if not text:
        return ""

    terminal_width = get_terminal_width()
    lines = []
    for line in text.split("\n"):
        # Skip wrapping for code blocks and headers
        if line.endswith("```java"):
            line = "```bash"

        if line.startswith("```") or line.startswith("#"):
            lines.append(line)
        else:
            # Wrap the line to the terminal width
            wrapped_lines = textwrap.wrap(
                line,
                width=terminal_width,
            )
            lines.append("\n".join(wrapped_lines))

    return "\n".join(lines)


def format_with_rich(text):
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console(
        color_system="truecolor",
        force_terminal=True,
        width=get_terminal_width(),
    )
    md = Markdown(text, code_theme="github-dark", justify="left")
    console.print(md)


def build_issue(issue, config, comments_count):
    """Return issue in a pretty formatted view as a string"""
    fields = issue["fields"]

    # Format header
    issue_type = fields["issuetype"]["name"]
    issue_status = fields["status"]["name"]
    issue_priority = fields["priority"]["name"]

    type_emoji = defaults.ISSUE_TYPE_EMOJIS.get(issue_type, ("❓", "??"))[0]
    status_emoji = defaults.STATUS_EMOJI.get(issue_status, "❓")
    priority_emoji = defaults.PRIORITY_EMOJI.get(issue_priority, "⚪")

    plain_title = f"{type_emoji} {issue['key']}: {fields['summary']}"
    output = []

    # Add issue title
    output.append(f"# {plain_title}")

    # Start markdown table

    # Add status, priority, and type
    output.append(f"* Status: {issue_status} {status_emoji}")
    output.append(f"* Priority: {issue_priority} {priority_emoji}")
    output.append(f"* Type: {issue_type} {type_emoji}")

    # Add fix versions if available
    if fields.get("fixVersions"):
        fix_versions = [v["name"] for v in fields["fixVersions"]]
        output.append(f"* Fix Version: 📦 {', '.join(fix_versions)} ")

    # Add components if available
    if fields.get("components"):
        components = [c["name"] for c in fields["components"]]
        output.append(f"* Component: 🧩 {', '.join(components)}")

    # Add labels if available
    if fields.get("labels"):
        output.append(f"* Labels: 🏷️ {', '.join(fields['labels'])} ")

    # Add people information
    if fields.get("assignee"):
        output.append(
            f"* Assignee: 👤 {fields['assignee']['displayName']} <{fields['assignee']['name']}>"
        )

    output.append(
        f"* Reporter: 📣 {fields['reporter']['displayName']} <{fields['reporter']['name']}>"
    )

    # Add dates
    date_format = "%Y-%m-%dT%H:%M:%S.%f%z"
    created_date = datetime.strptime(fields["created"], date_format)
    updated_date = datetime.strptime(fields["updated"], date_format)

    output.append(f"* Created: 📅 {created_date.strftime('%Y-%m-%d %H:%M:%S')}")
    output.append(f"* Updated: 🔄 {updated_date.strftime('%Y-%m-%d %H:%M:%S')}")

    # Description
    if fields.get("description"):
        markdown_description = "\n## Description\n"
        markdown_description += jira2markdown.convert(fields["description"])
        # Replace the first header with a second-level header but only on first line
        markdown_description = markdown_description.split("\n", 1)
        if len(markdown_description) > 1:
            markdown_description = (
                markdown_description[0].replace("#", "")
                + "\n"
                + markdown_description[1]
            )

    else:
        markdown_description = "No description provided"

    # Comments
    if comments_count > 0 and "comment" in fields and fields["comment"]["comments"]:
        comments = fields["comment"]["comments"]
        total = fields["comment"]["total"]
        shown = min(comments_count, total)

        markdown_description += f"\n\n## 💬 Comments ({shown} of {total})"

        for i, comment in enumerate(comments[:comments_count]):
            author = comment["author"]["displayName"]
            created = datetime.strptime(comment["created"], date_format).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            markdown_description += f"\n\n### Comment {i + 1} - {author} ({created})"

            # Convert Jira content to markdown
            comment_content = jira2markdown.convert(comment["body"])
            markdown_description += "\n\n" + comment_content

    return "\n".join(output), markdown_description

    # return "\n".join(output)


def display_issue(issue, config, comments_count):
    """Display issue in a pretty formatted view"""
    fields = issue["fields"]

    # Format header
    issue_type = fields["issuetype"]["name"]
    issue_status = fields["status"]["name"]
    issue_priority = fields["priority"]["name"]

    type_emoji = defaults.ISSUE_TYPE_EMOJIS.get(issue_type, ("❓", "??"))[0]
    status_emoji = defaults.STATUS_EMOJI.get(issue_status, "❓")
    priority_emoji = defaults.PRIORITY_EMOJI.get(issue_priority, "⚪")

    # Plain text version for box dimension calculations
    issue_link = utils.make_osc8_link(
        issue["key"], utils.make_full_url(issue["key"], config.get("jira_server"))
    )
    plain_title = f"{type_emoji} \033[1m\033[36m{issue_type}\033[0m {issue_link} {fields['summary']}"

    # Header with fancy UTF box-drawing characters
    print(plain_title)
    print("─" * 80 + "\n")

    # Calculate correct padding accounting for all displayed elements
    # Left border + space (2) + emoji (typical width 2) + issue key + colon & space (2) + summary

    # Status line
    status_color = (
        "green"
        if issue_status == "Done"
        else "yellow"
        if issue_status == "In Progress"
        else "red"
    )
    click.secho(f"{status_emoji} Status: ", bold=True, nl=False)
    click.secho(issue_status, fg=status_color, nl=False)
    print(" | ", nl=False)
    click.secho(f"{priority_emoji} Priority: ", bold=True, nl=False)
    priority_color = defaults.PRIORITY_COLORS.get(issue_priority, "")
    print(f"{priority_color}{issue_priority}\033[0m", end="")
    print(" | ", nl=False)
    click.secho("🏷️ Type: ", bold=True, nl=False)
    print(issue_type)

    # Fix versions
    if fields.get("fixVersions"):
        fix_versions = [v["name"] for v in fields["fixVersions"]]
        click.secho("📦 Fix Version: ", bold=True, nl=False)
        print(", ".join(fix_versions))

    # Components
    if fields.get("components"):
        components = [c["name"] for c in fields["components"]]
        click.secho("🧩 Component: ", bold=True, nl=False)
        print(", ".join(components))

    # Labels
    if fields.get("labels"):
        click.secho("🏷️ Labels: ", bold=True, nl=False)
        print(", ".join(fields["labels"]))

    # People information
    print("\n" + "─" * 80)
    click.secho("People", fg="cyan", bold=True)
    if fields.get("assignee"):
        click.secho("👤 Assignee: ", fg="cyan", nl=False)
        print(f"{fields['assignee']['displayName']} <{fields['assignee']['name']}>")

    click.secho("📣 Reporter: ", fg="cyan", nl=False)
    print(f"{fields['reporter']['displayName']} <{fields['reporter']['name']}>")

    # Dates
    date_format = "%Y-%m-%dT%H:%M:%S.%f%z"
    created_date = datetime.strptime(fields["created"], date_format)
    updated_date = datetime.strptime(fields["updated"], date_format)

    print("\n" + "─" * 80)
    click.secho("Dates", fg="cyan", bold=True)
    click.secho("📅 Created: ", fg="cyan", nl=False)
    print(created_date.strftime("%Y-%m-%d %H:%M:%S"))
    click.secho("🔄 Updated: ", fg="cyan", nl=False)
    print(updated_date.strftime("%Y-%m-%d %H:%M:%S"))

    # Description
    print("\n" + "─" * 80)
    click.secho("📝 Description:", fg="blue", bold=True)
    print("")
    if fields.get("description"):
        # Convert Jira markdown to standard markdown and format with gum if available
        markdown_description = jira2markdown.convert(fields["description"])
        markdown_description = wrap_markdown(markdown_description)
        format_with_rich(markdown_description)
    else:
        print("No description provided")

    # Comments
    if comments_count > 0 and "comment" in fields and fields["comment"]["comments"]:
        comments = fields["comment"]["comments"]
        total = fields["comment"]["total"]
        shown = min(comments_count, total)

        print("\n" + "─" * 80)
        click.secho(f"💬 Comments ({shown} of {total}):", fg="blue", bold=True)

        for i, comment in enumerate(comments[:comments_count]):
            author = comment["author"]["displayName"]
            created = datetime.strptime(comment["created"], date_format).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            print("┌" + "─" * 78 + "┐")
            print("| ", nl=False)
            click.secho(f"Comment {i + 1}", fg="cyan", nl=False)
            print(" - ", nl=False)
            click.secho(author, fg="yellow", nl=False)
            print(
                f" ({created})"
                + " " * (77 - len(f"Comment {i + 1} - {author} ({created})"))
                + "│"
            )
            print("╚" + "─" * 78 + "╝")

            # Simple formatting for comment body
            format_with_rich(comment["body"])
