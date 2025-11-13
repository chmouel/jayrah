"""Manage command for Jayrah Jira CLI."""

import os

import click

from jayrah.utils import issue_view

from ..ui import boards
from .common import cli as ccli
from .completions import BoardType


@ccli.group()
def cli():
    """CLI for Jira tickets."""


@cli.command("gencontext")
@click.argument("board", type=BoardType())
@click.option("--output", "-o", help="Output file path (default: stdout)")
@click.option(
    "--include-comments", "-c", is_flag=True, help="Include all comments from tickets"
)
@click.option(
    "--include-metadata", "-m", is_flag=True, help="Include custom fields and metadata"
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "plain"]),
    default="markdown",
    help="Output format (default: markdown)",
)
@click.pass_obj
def gencontext(
    jayrah_obj, board, output, include_comments, include_metadata, output_format
):
    """
    Generate comprehensive context file from board tickets for LLM consumption.

    Exports all tickets from the specified board including descriptions,
    comments, and metadata in a format optimized for importing into
    NotebookLM, Gemini, or other LLM contexts.

    Example: jayrah gencontext my-board --include-comments --include-metadata
    """
    from ..utils.context_generator import ContextGenerator

    # Get board configuration
    jql, order_by = boards.check(board, jayrah_obj.config)
    if not jql or not order_by:
        return

    # Initialize context generator
    generator = ContextGenerator(
        jayrah_obj.issues_client,
        jayrah_obj.config,
        include_comments=include_comments,
        include_metadata=include_metadata,
        output_format=output_format,
    )

    # Generate context
    try:
        context_content = generator.generate_board_context(board, jql, order_by)

        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(context_content)
            click.echo(f"Context exported to {output}")
        else:
            click.echo(context_content)

    except Exception as e:
        click.secho(f"Error generating context: {e}", fg="red", err=True)
        raise click.ClickException(str(e))


@cli.command("view")
@click.argument("ticket_number")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_obj
def view(jayrah_obj, ticket_number, as_json):
    """View a specific ticket."""
    try:
        issue = jayrah_obj.jira.get_issue(ticket_number, fields=["*all"])
        if as_json:
            import json

            click.echo(json.dumps(issue.raw, indent=2))
        else:
            header, body = issue_view.build_issue(issue, jayrah_obj.config, 5)
            click.echo(header)
            click.echo(body)
    except Exception as e:
        click.secho(f"Error fetching ticket {ticket_number}: {e}", fg="red")


@cli.command("open")
@click.argument("ticket_number")
@click.pass_obj
def bopen(jayrah_obj, ticket_number):
    """Open a specific ticket in the default web browser."""
    import webbrowser

    try:
        base_url = jayrah_obj.config.get("jira_server")
        if not base_url:
            click.secho("Jira base URL not found in config.", fg="red")
            return
        url = f"{base_url}/browse/{ticket_number}"
        webbrowser.open(url)
        click.secho(f"Opened {url} in your browser.", fg="green")
    except Exception as e:
        click.secho(f"Error opening ticket {ticket_number}: {e}", fg="red")


@cli.command("status")
@click.argument("ticket_number")
@click.argument("status_or_transition_id", required=False)
@click.pass_obj
def status(jayrah_obj, ticket_number, status_or_transition_id):
    """Set status or list available transitions for a ticket."""
    try:
        # Get available transitions for the issue
        transitions_data = jayrah_obj.jira.get_transitions(ticket_number)
        transitions = transitions_data.get("transitions", [])

        if not transitions:
            click.secho(f"No transitions available for {ticket_number}", fg="yellow")
            return

        # If no status/transition provided, list available transitions in CSV format
        if not status_or_transition_id:
            import csv
            import sys

            # Get current issue status
            issue = jayrah_obj.jira.get_issue(ticket_number, fields=["status"])
            current_status = issue.get("fields", {}).get("status", {}).get("name", "")

            writer = csv.writer(sys.stdout)
            writer.writerow(["transition_id", "name", "to_status", "current"])

            for transition in transitions:
                transition_id = transition["id"]
                name = transition["name"]
                to_status = transition["to"]["name"]
                is_current = "selected" if to_status == current_status else ""
                writer.writerow([transition_id, name, to_status, is_current])
            return

        # Try to find transition by ID first (if it's numeric)
        target_transition_id = None
        if status_or_transition_id.isdigit():
            for transition in transitions:
                if transition["id"] == status_or_transition_id:
                    target_transition_id = status_or_transition_id
                    break

        # If not found by ID, try to find by status name
        if not target_transition_id:
            status_name = status_or_transition_id.lower()
            for transition in transitions:
                to_status = transition["to"]["name"].lower()
                transition_name = transition["name"].lower()
                if status_name in to_status or status_name in transition_name:
                    target_transition_id = transition["id"]
                    break

        if not target_transition_id:
            import csv
            import sys

            click.secho(
                f"No transition found for '{status_or_transition_id}' on {ticket_number}",
                fg="red",
            )

            # Get current issue status for error case too
            issue = jayrah_obj.jira.get_issue(ticket_number, fields=["status"])
            current_status = issue.get("fields", {}).get("status", {}).get("name", "")

            writer = csv.writer(sys.stdout)
            writer.writerow(["transition_id", "name", "to_status", "current"])

            for transition in transitions:
                transition_id = transition["id"]
                name = transition["name"]
                to_status = transition["to"]["name"]
                is_current = "selected" if to_status == current_status else ""
                writer.writerow([transition_id, name, to_status, is_current])
            return

        # Apply the transition
        jayrah_obj.jira.transition_issue(ticket_number, target_transition_id)

        # Get the transition name for confirmation
        transition_name = next(
            (t["name"] for t in transitions if t["id"] == target_transition_id),
            "Unknown",
        )
        to_status = next(
            (t["to"]["name"] for t in transitions if t["id"] == target_transition_id),
            "Unknown",
        )

        click.secho(
            f"✅ Issue {ticket_number} transitioned to '{to_status}' via '{transition_name}'",
            fg="green",
        )

    except Exception as e:
        click.secho(f"Error managing status for {ticket_number}: {e}", fg="red")


@cli.command("show")
@click.argument("ticket_number")
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "friendly"]),
    default="friendly",
    help="Output format: friendly (default) or json",
)
@click.pass_obj
def show(jayrah_obj, ticket_number, output):
    """Show current status and details of a ticket."""
    try:
        # Get issue with relevant fields for status display
        base_fields = [
            "key",
            "summary",
            "status",
            "priority",
            "issuetype",
            "assignee",
            "reporter",
            "created",
            "updated",
            "labels",
            "components",
            "fixVersions",
            "description",
        ]

        # Add custom fields from config
        custom_fields = jayrah_obj.config.get("custom_fields", [])
        for cf in custom_fields:
            field_id = cf.get("field")
            if field_id and field_id not in base_fields:
                base_fields.append(field_id)

        issue = jayrah_obj.jira.get_issue(ticket_number, fields=base_fields)

        if output == "json":
            import json

            click.echo(json.dumps(issue, indent=2))
        else:
            # Friendly output similar to TUI display
            fields = issue.get("fields", {})

            # Get basic info
            key = issue.get("key", "Unknown")
            summary = fields.get("summary", "No summary")
            status = fields.get("status", {}).get("name", "Unknown")
            priority = fields.get("priority", {}).get("name", "Unknown")
            issue_type = fields.get("issuetype", {}).get("name", "Unknown")

            # Import defaults for priority colors
            from jayrah.config import defaults

            click.echo(f"Ticket: {key}")
            click.echo(f"Summary: {summary}")
            click.echo(f"Status: {status}")

            # Color priority
            color_code = defaults.PRIORITY_COLORS.get(priority, "")
            reset_code = "\033[0m" if color_code else ""
            click.echo(f"Priority: {color_code}{priority}{reset_code}")
            click.echo(f"Type: {issue_type}")

            # Add assignee if available
            if fields.get("assignee"):
                assignee = fields["assignee"]
                assignee_name = assignee.get("displayName", "Unknown")
                click.echo(f"Assignee: {assignee_name}")
            else:
                click.echo("Assignee: Unassigned")

            # Add reporter
            if fields.get("reporter"):
                reporter = fields["reporter"]
                reporter_name = reporter.get("displayName", "Unknown")
                click.echo(f"Reporter: {reporter_name}")

            # Add labels if available
            if fields.get("labels"):
                click.echo(f"Labels: {', '.join(fields['labels'])}")

            # Add components if available
            if fields.get("components"):
                components = [c["name"] for c in fields["components"]]
                click.echo(f"Components: {', '.join(components)}")

            # Add fix versions if available
            if fields.get("fixVersions"):
                fix_versions = [v["name"] for v in fields["fixVersions"]]
                click.echo(f"Fix Version: {', '.join(fix_versions)}")

            # Add dates
            from datetime import datetime

            date_format = "%Y-%m-%dT%H:%M:%S.%f%z"
            try:
                created_date = datetime.strptime(fields.get("created", ""), date_format)
                click.echo(f"Created: {created_date.strftime('%Y-%m-%d %H:%M:%S')}")
            except (ValueError, TypeError):
                pass

            try:
                updated_date = datetime.strptime(fields.get("updated", ""), date_format)
                click.echo(f"Updated: {updated_date.strftime('%Y-%m-%d %H:%M:%S')}")
            except (ValueError, TypeError):
                pass

            click.echo("")  # Blank line before description
            # Show custom fields if present and not empty
            custom_fields = jayrah_obj.config.get("custom_fields", [])
            for cf in custom_fields:
                field_id = cf.get("field")
                field_name = cf.get("name", field_id)
                field_type = cf.get("type", "string")
                if field_id and fields.get(field_id):
                    value = fields[field_id]
                    # If value is a list, join, else str
                    if isinstance(value, list):
                        value = ", ".join(str(v) for v in value if v)
                    if value:
                        if field_type == "text":
                            click.echo(f"{field_name}:")
                            # Format text fields with the same style as description
                            formatted_value = "\n".join(
                                ["│ " + line for line in str(value).splitlines()]
                            )
                            click.echo(formatted_value)
                        elif field_type == "url":
                            click.echo(f"{field_name}: {value}")
                        else:
                            click.echo(f"{field_name}: {value}")

            # Add description
            click.echo("")  # Blank line before description
            t = "Description:"
            click.echo(t)
            if fields.get("description"):
                # Handle different description formats (similar to issue_view.py)
                description_text = fields["description"]

                # Handle v3 API format with "raw" key
                if isinstance(description_text, dict) and "raw" in description_text:
                    description_text = description_text["raw"]
                # Handle ADF format
                elif (
                    isinstance(description_text, dict)
                    and "type" in description_text
                    and "content" in description_text
                ):
                    from jayrah.utils import adf

                    description_text = adf.extract_text_from_adf(description_text)

                if description_text and isinstance(description_text, str):
                    # Convert Jira markup to markdown and display
                    import jira2markdown

                    markdown_description = jira2markdown.convert(description_text)
                    markdown_description = issue_view.wrap_markdown(
                        markdown_description
                    )
                    # add two spaces to the begin of each lines
                    markdown_description = "\n".join(
                        ["│ " + line for line in markdown_description.splitlines()]
                    )
                    click.echo(markdown_description)
                else:
                    click.echo("No detailed description provided")
            else:
                click.echo("No description provided")

    except Exception as e:
        click.secho(f"Error fetching ticket {ticket_number}: {e}", fg="red")


@cli.command("browse")
@click.argument("board_name")
@click.pass_obj
def browse(jayrah_obj, board_name):
    """List all issues for a specific board in CSV format."""
    import csv
    import sys

    try:
        boards = jayrah_obj.config.get("boards", [])
        target_board = None
        for b in boards:
            if b.get("name") == board_name:
                target_board = b
                break

        if not target_board:
            click.secho(f"Board '{board_name}' not found in configuration.", fg="red")
            sys.exit(1)

        jql = target_board.get("jql")
        order_by = target_board.get("order_by")

        if not jql:
            click.secho(f"Board '{board_name}' has no JQL query defined.", fg="red")
            sys.exit(1)

        if order_by:
            jql = f"{jql} ORDER BY {order_by}"

        issues = jayrah_obj.issues_client.list_issues(jql)

        writer = csv.writer(sys.stdout)
        writer.writerow(["key", "issuetype", "status", "assignee", "summary"])

        for issue in issues:
            fields = issue.get("fields", {})
            assignee_field = fields.get("assignee")
            assignee = (
                assignee_field.get("displayName") if assignee_field else "UNASSIGNED"
            )
            status_field = fields.get("status", {})
            status = status_field.get("name") if status_field else "No Status"
            summary = fields.get("summary")
            issuetype = fields.get("issuetype", {}).get("name", "No Type")
            key = issue.get("key")
            writer.writerow([key, issuetype, status, assignee, summary])

    except Exception as e:
        click.secho(f"Error fetching issues for board {board_name}: {e}", fg="red")
        sys.exit(1)


class CustomCommands(click.MultiCommand):
    def list_commands(self, ctx):
        """Read subcommand groups from `plugins_dir`."""

        custom_commands = ctx.obj.config.get("custom_fields", {})
        if custom_commands:
            return [x["name"].lower().replace(" ", "-") for x in custom_commands]
        return []

    def get_command(self, ctx, cmd_name):
        for command in ctx.obj.config.get("custom_fields", {}):
            command_name = command["name"].lower().replace(" ", "-")
            if command_name == cmd_name:
                return self.create_command(command)

        return None

    def create_command(self, command):
        """Create the command."""

        @click.command(
            name=command["name"].lower().replace(" ", "-"), help=command["description"]
        )
        @click.argument("issue_key")
        @click.argument("value")
        @click.pass_obj
        def callback(jayrah_obj, issue_key, value):
            """Custom command to update a custom field for an issue."""
            import re
            import sys

            issue_key = os.path.basename(issue_key)

            field_id = command.get("field")
            field_type = command.get("type", "string")
            field_name = command.get("name")
            if not field_id:
                click.secho(
                    f"Custom field ID missing for command '{field_name}'", fg="red"
                )
                sys.exit(1)
            # Type validation and conversion
            try:
                if field_type == "number":
                    if value is None:
                        value = 0
                    value_str = str(value)
                    value = float(value_str) if "." in value_str else int(value_str)
                elif field_type == "url":
                    if value and not re.match(
                        r"^(https?|ftp)://[^\s/$.?#].[^\s]*$", str(value)
                    ):
                        click.secho("Invalid URL format", fg="red")
                        sys.exit(1)
                elif field_type in ["string", "text"]:
                    value = str(value) if value is not None else ""
            except (ValueError, TypeError):
                click.secho(f"Invalid value for type '{field_type}'", fg="red")
                sys.exit(1)
            # Update the issue
            try:
                jayrah_obj.jira.update_issue(issue_key, {field_id: value})
                click.secho(
                    f"Custom field '{field_name}' ({field_id}) updated with {value} for {issue_key}",
                    fg="green",
                )
            except Exception as e:
                click.secho(
                    f"Error updating custom field for {issue_key}: {e}", fg="red"
                )
                sys.exit(1)

        return callback


@cli.group("custom", cls=CustomCommands)
@click.pass_context
def custom(ctx):
    """Custom command to view a specific ticket."""
