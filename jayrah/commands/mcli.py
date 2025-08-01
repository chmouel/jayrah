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
