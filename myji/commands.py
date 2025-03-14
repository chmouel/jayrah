import os
import sys

import click

from . import defaults, help, issue_view, myji, utils


@click.group()
@click.option("--no-cache", "-n", is_flag=True, help="Disable caching of API responses")
@click.option("--no-fzf", is_flag=True, help="Output directly to stdout without fzf")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option(
    "--cache-ttl", "-t", default=defaults.CACHE_DURATION, help="Cache TTL in seconds"
)
@click.pass_context
def cli(ctx, no_cache, no_fzf, verbose, cache_ttl):
    """Jira Helper Tool"""
    # If --help-content flag is used, print the help content and exit
    ctx.obj = myji.MyJi(
        no_cache=no_cache, verbose=verbose, cache_ttl=cache_ttl, no_fzf=no_fzf
    )
    ctx.obj.myj_path = os.path.abspath(sys.argv[0])
    ctx.obj.ctx = ctx


@cli.command("help")
@click.pass_obj
def help_command(myji_obj):
    """Display help content"""
    # Display help content in a formatted way
    help_text = help.get_help_text()
    click.echo(help_text, err=True)


@cli.command("myissue")
@click.pass_obj
def my_issue(myji_obj):
    """My current issues"""
    myji_obj.command = "myissue"
    jql = "assignee = currentUser() AND resolution = Unresolved"
    if myji_obj.verbose:
        click.echo(f"Running query: {jql}", err=True)
    issues = myji_obj.list_issues(jql)
    selected = myji_obj.fuzzy_search(issues)
    if selected:
        click.secho(f"Selected issue: {selected}", fg="green")


@cli.command("myinprogress")
@click.pass_obj
def my_inprogress(myji_obj):
    """My in-progress issues"""
    myji_obj.command = "myinprogress"
    jql = (
        'assignee = currentUser() AND status in ("Code Review", "In Progress", "On QA")'
    )
    if myji_obj.verbose:
        click.echo(f"Running query: {jql}", err=True)
    issues = myji_obj.list_issues(jql)
    selected = myji_obj.fuzzy_search(issues)
    if selected:
        click.secho(f"Selected issue: {selected}", fg="green")


@cli.command("pac-current")
@click.pass_obj
def pac_current(myji_obj):
    """Current PAC issues"""
    myji_obj.command = "pac-current"
    jql = f'component = "{myji_obj.jira.component}" AND fixVersion in unreleasedVersions({myji_obj.jira.project})'
    if myji_obj.verbose:
        click.echo(f"Running query: {jql}", err=True)
    issues = myji_obj.list_issues(jql)
    selected = myji_obj.fuzzy_search(issues)
    if selected:
        click.secho(f"Selected issue: {selected}", fg="green")


@cli.command("pac-create")
@click.option("--type", "-t", "issuetype", default="Story", help="Issue type")
@click.option("--summary", "-s", help="Issue summary")
@click.option("--description", "-d", help="Issue description")
@click.option("--priority", "-p", help="Issue priority")
@click.option("--assignee", "-a", help="Issue assignee")
@click.option("--labels", "-l", multiple=True, help="Issue labels")
@click.pass_obj
# pylint: disable=too-many-positional-arguments
def pac_create(myji_obj, issuetype, summary, description, priority, assignee, labels):
    """Create PAC issue"""
    myji_obj.command = "pac-create"
    labels_list = list(labels) if labels else None
    myji_obj.create_issue(
        issuetype=issuetype,
        summary=summary,
        description=description,
        priority=priority,
        assignee=assignee,
        labels=labels_list,
    )


@cli.group("issue")
def issue():
    """Issue manage issues in a given project. See available commands below."""


@issue.command("open")
@click.argument("ticket", required=False)
@click.pass_obj
def browser_open(myji_obj, ticket):
    """Open opens issue in a browser. If the issue key is not given, it will open the project page."""
    server = myji_obj.jira.server if hasattr(myji_obj, "jira") else None
    utils.browser_open_ticket(ticket, server=server)


@issue.command("view")
@click.argument("ticket")
@click.option("--comments", "-c", default=0, help="Number of comments to show")
@click.option(
    "--plain", is_flag=True, help="Display plain output without rich formatting"
)
@click.pass_obj
def view(myji_obj, ticket, comments, plain):
    """View issue in a nice format"""
    # Get detailed information about the issue
    fields = None  # Get all fields
    issue = myji_obj.jira.get_issue(ticket, fields=fields)
    issue_view.display_issue(issue, comments, myji_obj.verbose)
