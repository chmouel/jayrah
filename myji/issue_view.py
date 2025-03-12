import click
from datetime import datetime
import os
import tempfile
import subprocess


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

    # Format header
    issue_type = fields["issuetype"]["name"]
    issue_status = fields["status"]["name"]
    issue_priority = fields["priority"]["name"]

    type_emoji = issue_type_emoji.get(issue_type, "📄")
    status_emoji = status_emoji.get(issue_status, "❓")
    priority_emoji = priority_emoji.get(issue_priority, "⚪")

    # Header
    click.echo("╔" + "═" * 78 + "╗")
    click.secho(f"║ {type_emoji} ", nl=False)
    click.secho(f"{issue['key']}: ", fg="yellow", bold=True, nl=False)
    click.secho(fields["summary"], bold=True, nl=False)
    click.echo(" " * (77 - len(issue["key"]) - len(fields["summary"])) + "║")
    click.echo("╚" + "═" * 78 + "╝")

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
    click.echo(issue_priority, nl=False)
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

    # Display Avatar in Kitty if available
    if (
        fields.get("assignee")
        and fields["assignee"].get("avatarUrls")
        and os.environ.get("TERM") == "xterm-kitty"
    ):
        avatar_url = fields["assignee"]["avatarUrls"]["48x48"]
        # If the avatar is an SVG, convert it to PNG for display
        if avatar_url.endswith(".svg"):
            try:
                # Only try to display if we're in a Kitty terminal
                click.secho("\nAssignee Avatar:", bold=True)
                with tempfile.NamedTemporaryFile(
                    suffix=".png", delete=False
                ) as tmp_file:
                    # Download SVG and convert to PNG using rsvg-convert if available
                    subprocess.run(
                        f"curl -s '{avatar_url}' | rsvg-convert -h 48 > {tmp_file.name}",
                        shell=True,
                        check=True,
                    )
                    # Display the PNG in the terminal
                    subprocess.run(
                        f"kitty icat --align left {tmp_file.name}",
                        shell=True,
                        check=True,
                    )
                    os.unlink(tmp_file.name)
            except Exception as e:
                if verbose:
                    click.echo(f"Failed to display avatar: {e}", err=True)

    # Description
    click.echo("\n" + "─" * 80)
    click.secho("📝 Description:", fg="blue", bold=True)
    if fields.get("description"):
        click.echo(fields["description"])
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
