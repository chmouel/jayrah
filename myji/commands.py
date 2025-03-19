import os
import pathlib
import sys

import click

from . import config, defaults, help, issue_action, issue_view, myji, utils


@click.group()
@click.option("--no-cache", "-n", is_flag=True, help="Disable caching of API responses")
@click.option("--no-fzf", is_flag=True, help="Output directly to stdout without fzf")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option(
    "--jira-server",
    default=os.environ.get("JIRA_SERVER"),
    help="Jira server URL",
)
@click.option(
    "--jira-user",
    default=os.environ.get("JIRA_USER"),
    help="Jira user",
)
@click.option(
    "--jira-component",
    default=os.environ.get("JIRA_COMPONENT"),
    help="Jira user",
)
@click.option(
    "--jira-password",
    default=os.environ.get("JIRA_PASSWORD"),
    help="Jira user",
)
@click.option("--cache-ttl", "-t", help="Cache TTL in seconds")
@click.option(
    "-c",
    "--config-file",
    default=defaults.CONFIG_FILE,
    help="Config file to use",
)
@click.pass_context
def cli(
    ctx,
    no_cache,
    no_fzf,
    verbose,
    jira_user,
    jira_password,
    jira_component,
    jira_server,
    cache_ttl,
    config_file,
):
    """Jira Helper Tool"""

    flag_config = {
        "jira_server": jira_server,
        "jira_user": jira_user,
        "jira_password": jira_password,
        "jira_component": jira_component,
        "cache_ttl": cache_ttl,
        "no_cache": no_cache,
        "verbose": verbose,
        "no_fzf": no_fzf,
        "myj_path": os.path.abspath(sys.argv[0]),
        "ctx": ctx,
    }
    wconfig = config.make_config(flag_config, pathlib.Path(config_file))
    if verbose:
        click.echo(f"Using config: {wconfig}", err=True)
    ctx.obj = myji.MyJi(wconfig)


@cli.command("help")
@click.pass_obj
def help_command(myji_obj):
    """Display help content"""
    # Display help content in a formatted way
    help_text = help.get_help_text()
    click.echo(help_text, err=True)


@cli.command("browse")
@click.argument("board", required=False)
@click.pass_obj
def browse(myji_obj, board):
    """Browse boards"""

    def show_boards():
        click.echo("Available boards:")
        for x in myji_obj.config.get("boards", []):
            click.secho(f"  {x.get('name')}", fg="cyan", nl=False)
            if x.get("description"):
                click.secho(f" - {x.get('description')}", italic=True, nl=False)
            click.echo()

    if not board:
        show_boards()
        return

    chosen_boards = [x for x in myji_obj.config["boards"] if x.get("name") == board]
    if board is not None and board not in [
        x.get("name") for x in chosen_boards if x.get("name") == board
    ]:
        click.secho("Invalid board: ", fg="red", err=True, nl=False)
        click.echo(f"{board}", err=True)
        show_boards()
        return

    jql = chosen_boards[0].get("jql").strip() if chosen_boards else None
    if not jql:
        click.secho(f"Board {board} has no JQL defined", fg="red", err=True)
        return
    order_by = chosen_boards[0].get("order_by", defaults.ORDER_BY)
    if myji_obj.verbose:
        click.echo(f"Running query: {jql} ORDER BY: {order_by}", err=True)

    issues = myji_obj.list_issues(jql, order_by=order_by)
    selected = myji_obj.fuzzy_search(issues)
    if selected:
        click.secho(f"Selected issue: {selected}", fg="green")


@cli.command("create")
@click.option("--type", "-t", "issuetype", default="Story", help="Issue type")
@click.option("--summary", "-s", help="Issue summary")
@click.option("--description", "-d", help="Issue description")
@click.option("--priority", "-p", help="Issue priority")
@click.option("--assignee", "-a", help="Issue assignee")
@click.option("--labels", "-l", multiple=True, help="Issue labels")
@click.pass_obj
# pylint: disable=too-many-positional-arguments
def pac_create(myji_obj, issuetype, summary, description, priority, assignee, labels):
    """Create an issue"""
    myji_obj.command = "create"
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
    """issue commands"""


@issue.command("open")
@click.argument("ticket")
@click.pass_obj
def browser_open(myji_obj, ticket):
    """Open issue in browser"""
    # Use the myji_obj if needed to see server info
    utils.browser_open_ticket(ticket, myji_obj.config)


@issue.command("view")
@click.argument("ticket")
@click.option("--comments", "-c", default=0, help="Number of comments to show")
@click.pass_obj
def view(myji_obj, ticket, comments):
    """View issue in a nice format"""
    # Get detailed information about the issue
    fields = None  # Get all fields
    issue = myji_obj.jira.get_issue(ticket, fields=fields)
    issue_view.display_issue(issue, myji_obj.config, comments)


@issue.command("action")
@click.argument("ticket")
@click.pass_obj
def action(myji_obj, ticket):
    """View issue in a nice format"""
    # Get detailed information about the issue
    fields = None  # Get all fields
    issue = myji_obj.jira.get_issue(ticket, fields=fields)
    issue_action.action_menu(issue, myji_obj)


@issue.command("edit-description")
@click.argument("ticket")
@click.pass_obj
def edit_description(myji_obj, ticket):
    """Edit issue description with system editor"""
    fields = None  # Get all fields
    ticketj = myji_obj.jira.get_issue(ticket, fields=fields)
    edit_success = issue_action.edit_description(ticketj, myji_obj)
    ticket_number = ticketj["key"]
    if edit_success and myji_obj.verbose:
        click.echo(f"Description updated for {ticket_number}", err=True)


@issue.command("transition")
@click.argument("ticket")
@click.pass_obj
def transition(myji_obj, ticket):
    """Transition issue to a new status"""
    ticketj = myji_obj.jira.get_issue(ticket, fields=None)
    issue_action.transition_issue(ticketj, myji_obj)
