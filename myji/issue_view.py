import click
from datetime import datetime
import subprocess
import re
import shutil


def convert_jira_to_markdown(jira_text):
    """Convert Jira formatted text to standard markdown"""
    if not jira_text:
        return ""

    # Convert headers: h2. *Title* -> ## Title
    def header_replace(match):
        level = int(match.group(1))
        title = match.group(2)
        return "#" * level + " " + title

    markdown = re.sub(r"h([1-6])\.\s*\*(.*?)\*", header_replace, jira_text)

    # Convert Jira code blocks {code} or {noformat} to ```
    markdown = re.sub(
        r"\{code(?::\w+)?\}(.*?)\{code\}", r"```\n\1\n```", markdown, flags=re.DOTALL
    )
    markdown = re.sub(
        r"\{noformat\}(.*?)\{noformat\}", r"```\n\1\n```", markdown, flags=re.DOTALL
    )

    # Process line by line for lists and other formatting
    lines = []
    for line in markdown.split("\n"):
        # Convert bullet lists: " * item" -> "- item"
        line = re.sub(r"^\s*\*\s", "- ", line)

        # Convert numbered lists: " # item" -> "1. item"
        line = re.sub(r"^\s*#\s", "1. ", line)

        # Bold: *text* -> **text**
        line = re.sub(r"\*(.*?)\*", r"**\1**", line)

        lines.append(line)

    return "\n".join(lines)


def format_with_gum(text):
    """Format text with gum if available, otherwise return original text"""
    if not text:
        return "No description provided"

    # Check if gum is available
    if shutil.which("gum"):
        try:
            # Use pipe to send markdown content to gum
            process = subprocess.run(
                # TODO: make the theme configurable
                [
                    "gum",
                    "format",
                    "--type=markdown",
                    "--theme=tokyo-night",
                ],
                input=text,
                capture_output=True,
                text=True,
                check=True,
            )

            # Return formatted output
            return process.stdout

        except (subprocess.SubprocessError, OSError):
            # Fall back to original text if there's an error
            return text

    return text


def display_issue(issue, comments_count=0, verbose=False):
    """Display issue in a pretty formatted view"""
    fields = issue["fields"]

    # Issue type emoji mapping
    issue_type_emoji = {
        "Bug": "🐞",
        "Epic": "🏆",
        "Story": "📖",
        "Task": "📋",
        "Sub-task": "📎",
        "Feature": "🚀",
        "Improvement": "⬆️",
    }

    # Status emoji mapping
    status_emoji = {
        "Open": "🔓",
        "In Progress": "🏗️",
        "Code Review": "👀",
        "On QA": "🧪",
        "Done": "✅",
        "Closed": "🔒",
        "Resolved": "🎯",
        "Reopened": "🔄",
        "New": "🆕",
        "To Do": "📌",
    }

    # Priority emoji mapping
    priority_emoji = {
        "Blocker": "❌",
        "Critical": "🛑",
        "Major": "🔴",
        "Minor": "🟠",
        "Trivial": "🟢",
    }

    # Priority ANSI color mapping
    priority_colors = {
        "Blocker": "\033[91m",  # Bright red
        "Critical": "\033[31m",  # Red
        "Major": "\033[33m",  # Yellow
        "Minor": "\033[36m",  # Cyan
        "Trivial": "\033[32m",  # Green
    }

    # Format header
    issue_type = fields["issuetype"]["name"]
    issue_status = fields["status"]["name"]
    issue_priority = fields["priority"]["name"]

    type_emoji = issue_type_emoji.get(issue_type, "📄")
    status_emoji = status_emoji.get(issue_status, "❓")
    priority_emoji = priority_emoji.get(issue_priority, "⚪")

    # Plain text version for box dimension calculations
    plain_title = f"{type_emoji} {issue_type} {issue['key']} {fields['summary']}"

    # Header with fancy UTF box-drawing characters
    click.echo("╔" + "═" * (len(plain_title) + 3) + "╗")
    click.echo("║ " + type_emoji + " ", nl=False)
    print(f"\033[1m\033[36m{issue_type}\033[0m", end="")
    click.echo(f" {issue['key']} {fields['summary']}" + " ║")
    click.echo("╚" + "═" * (len(plain_title) + 3) + "╝")
    click.echo("")

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
    click.echo(" | ", nl=False)
    click.secho(f"{priority_emoji} Priority: ", bold=True, nl=False)
    priority_color = priority_colors.get(issue_priority, "")
    print(f"{priority_color}{issue_priority}\033[0m", end="")
    click.echo(" | ", nl=False)
    click.secho("🏷️ Type: ", bold=True, nl=False)
    click.echo(issue_type)

    # Fix versions
    if fields.get("fixVersions"):
        fix_versions = [v["name"] for v in fields["fixVersions"]]
        click.secho("📦 Fix Version: ", bold=True, nl=False)
        click.echo(", ".join(fix_versions))

    # Components
    if fields.get("components"):
        components = [c["name"] for c in fields["components"]]
        click.secho("🧩 Component: ", bold=True, nl=False)
        click.echo(", ".join(components))

    # Labels
    if fields.get("labels"):
        click.secho("🏷️ Labels: ", bold=True, nl=False)
        click.echo(", ".join(fields["labels"]))

    # People information
    click.echo("\n" + "─" * 80)
    click.secho("People", fg="cyan", bold=True)
    if fields.get("assignee"):
        click.secho("👤 Assignee: ", fg="cyan", nl=False)
        click.echo(
            f"{fields['assignee']['displayName']} <{fields['assignee']['emailAddress']}>"
        )

    click.secho("📣 Reporter: ", fg="cyan", nl=False)
    click.echo(
        f"{fields['reporter']['displayName']} <{fields['reporter']['emailAddress']}>"
    )

    # Dates
    date_format = "%Y-%m-%dT%H:%M:%S.%f%z"
    created_date = datetime.strptime(fields["created"], date_format)
    updated_date = datetime.strptime(fields["updated"], date_format)

    click.echo("\n" + "─" * 80)
    click.secho("Dates", fg="cyan", bold=True)
    click.secho("📅 Created: ", fg="cyan", nl=False)
    click.echo(created_date.strftime("%Y-%m-%d %H:%M:%S"))
    click.secho("🔄 Updated: ", fg="cyan", nl=False)
    click.echo(updated_date.strftime("%Y-%m-%d %H:%M:%S"))

    # Description
    click.echo("\n" + "─" * 80)
    click.secho("📝 Description:", fg="blue", bold=True)
    if fields.get("description"):
        # Convert Jira markdown to standard markdown and format with gum if available
        markdown_description = convert_jira_to_markdown(fields["description"])
        formatted_description = format_with_gum(markdown_description)
        print(formatted_description)
    else:
        click.echo("No description provided")

    # Comments
    if comments_count > 0 and "comment" in fields and fields["comment"]["comments"]:
        comments = fields["comment"]["comments"]
        total = fields["comment"]["total"]
        shown = min(comments_count, total)

        click.echo("\n" + "─" * 80)
        click.secho(f"💬 Comments ({shown} of {total}):", fg="blue", bold=True)

        for i, comment in enumerate(comments[:comments_count]):
            author = comment["author"]["displayName"]
            created = datetime.strptime(comment["created"], date_format).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            click.echo("┌" + "─" * 78 + "┐")
            click.secho(f"│ Comment {i + 1} - ", fg="cyan", nl=False)
            click.secho(author, fg="yellow", nl=False)
            click.echo(
                f" ({created})"
                + " " * (79 - len(f"Comment {i + 1} - {author} ({created})"))
                + "│"
            )
            click.echo("├" + "─" * 78 + "┤")

            # Simple formatting for comment body
            for line in comment["body"].split("\n"):
                wrapped_lines = [line[i : i + 76] for i in range(0, len(line), 76)]
                for wrapped in wrapped_lines:
                    click.echo("│ " + wrapped + " " * (76 - len(wrapped)) + " │")

            click.echo("└" + "─" * 78 + "┘\n")
