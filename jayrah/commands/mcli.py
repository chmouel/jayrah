"""Manage command for Jayrah Jira CLI."""

import click

from jayrah.utils import issue_view

from .common import cli as ccli


@ccli.group()
def cli():
    """CLI for Jira tickets."""


@cli.command("view")
@click.argument("ticket_number")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
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
def open(jayrah_obj, ticket_number):
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
                    f"Custom field '{field_name}' ({field_id}) updated for {issue_key}",
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
