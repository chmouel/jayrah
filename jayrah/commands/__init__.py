import asyncio
import os
import pathlib
import sys
import time

import click

from .. import config, utils
from ..api import jira as jirahttp
from ..commands import issue_action, issue_view, mcp_server
from ..config import defaults
from ..ui import boards
from ..utils import help, log


@click.group()
@click.option("--no-cache", "-n", is_flag=True, help="Disable caching of API responses")
@click.option(
    "--no-fzf", is_flag=True, help="Output directly to stdout without interactive UI"
)
@click.option("--fzf", is_flag=True, help="Force use of fzf UI for selection")
@click.option(
    "--ui-type",
    type=click.Choice(["fzf", "textual"]),
    default="textual",
    help="Choose UI type (fzf or textual)",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--insecure", is_flag=True, help="Disable SSL verification for requests")
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
    fzf,
    ui_type,
    verbose,
    insecure,
    jira_user,
    jira_password,
    jira_component,
    jira_server,
    cache_ttl,
    config_file,
):
    """Jira Helper Tool"""

    # If --fzf is set, override ui_type and no_fzf
    if fzf:
        ui_type = "fzf"
        no_fzf = False

    flag_config = {
        "jira_server": jira_server,
        "jira_user": jira_user,
        "jira_password": jira_password,
        "jira_component": jira_component,
        "cache_ttl": cache_ttl,
        "no_cache": no_cache,
        "verbose": verbose,
        "no_fzf": no_fzf,
        "ui_type": ui_type,
        "insecure": insecure,
        "jayrah_path": os.path.abspath(sys.argv[0]),
        "ctx": ctx,
    }
    wconfig = config.make_config(flag_config, pathlib.Path(config_file))
    log(f"Using config: {wconfig}", verbose=verbose, verbose_only=True)
    ctx.obj = boards.Boards(wconfig)


@cli.command("help")
@click.pass_obj
def help_command(jayrah_obj):
    """Display help content"""
    # Display help content in a formatted way
    help_text = help.get_help_text()
    click.echo(help_text)


@cli.command("browse")
@click.argument("board", required=False, type=boards.BoardType())
@click.argument("search_terms", nargs=-1)
@click.option(
    "--or", "-o", "use_or", is_flag=True, help="Use OR instead of AND for search terms"
)
@click.option(
    "--filter",
    "-f",
    "filters",
    multiple=True,
    help="Filter issues by specific field (e.g., 'status=\"In Progress\"')",
)
@click.pass_obj
def browse(jayrah_obj, board, search_terms, use_or, filters):
    """
    Browse boards

    SEARCH_TERMS are optional search terms that filter issues by summary or description.
    Multiple terms are combined with AND by default (or with OR if --or flag is used).

    Example: jayrah browse my-board term1 term2   # Searches for term1 AND term2
    Example: jayrah browse my-board --or term1 term2   # Searches for term1 OR term2
    Example: jayrah browse my-board --filter status="Code Review"   # Filter by status
    """
    jayrah_obj.command = board
    jql, order_by = boards.check(board, jayrah_obj.config)
    if not jql or not order_by:
        return

    # Use the common function to build the search JQL
    jql = boards.build_search_jql(
        jql, search_terms, use_or, jayrah_obj.verbose, filters
    )

    issues = jayrah_obj.issues_client.list_issues(jql, order_by=order_by)

    if not issues:
        boards.show_no_issues_message(search_terms, use_or, filters)
        return

    jayrah_obj.jql = jql
    jayrah_obj.order_by = order_by

    selected = jayrah_obj.fuzzy_search(issues)
    if selected:
        click.secho(f"Selected issue: {selected}", fg="green")
        # You can also auto-open the issue if needed
        # utils.browser_open_ticket(selected, jayrah_obj.config)


@cli.command("create")
@click.option("--type", "-t", "issuetype", help="Issue type")
@click.option("--title", "-T", help="Issue title/summary")
@click.option("--body", "-b", help="Issue description")
@click.option(
    "--body-file", "-F", type=click.Path(exists=True), help="Read description from file"
)
@click.option("--priority", "-p", help="Issue priority")
@click.option("--assignee", "-a", help="Issue assignee")
@click.option("--labels", "-l", multiple=True, help="Issue labels")
@click.option("--components", "-c", multiple=True, help="Issue components")
@click.option("--template", "-T", help="Use a specific template")
@click.pass_obj
def create(
    jayrah_obj,
    issuetype,
    title,
    body,
    body_file,
    priority,
    assignee,
    labels,
    template,
    components,
):
    """Create an issue"""
    jayrah_obj.command = "create"

    # Handle body file
    if body_file:
        if not os.path.exists(body_file):
            raise Exception(f"{body_file} does not exist")

        with open(body_file, "r") as f:
            body = f.read()

    from . import issue_create

    body = issue_create.get_description(
        jayrah_obj, title or "New Issue", issuetype, template=template, body=body
    )

    # Convert labels to list
    labels_list = list(labels) if labels else None
    components_list = list(components) if components else None

    jayrah_obj.cmdline = {
        "issuetype": issuetype,
        "title": title,
        "body": body,
        "priority": priority,
        "assignee": assignee,
        "labels": labels_list,
        "components": components_list,
    }

    # Create the issue
    from . import issue_create

    issue_create.interactive_create(jayrah_obj)


@cli.group("issue")
def issue():
    """issue commands"""


@issue.command("open")
@click.argument("ticket")
@click.pass_obj
def browser_open(jayrah_obj, ticket):
    """Open issue in browser"""
    # Use the jayrah_obj if needed to see server info
    utils.browser_open_ticket(ticket, jayrah_obj.config)


@issue.command("view")
@click.argument("ticket")
@click.option("--comments", "-c", default=0, help="Number of comments to show")
@click.pass_obj
def view(jayrah_obj, ticket, comments):
    """View issue in a nice format"""
    # Get detailed information about the issue
    fields = None  # Get all fields
    issue = jayrah_obj.jira.get_issue(ticket, fields=fields)
    issue_view.display_issue(issue, jayrah_obj.config, comments)


@issue.command("action")
@click.argument("ticket")
@click.pass_obj
def action(jayrah_obj, ticket):
    """View issue in a nice format"""
    # Get detailed information about the issue
    fields = None  # Get all fields
    issue = jayrah_obj.jira.get_issue(ticket, fields=fields)
    issue_action.action_menu(issue, jayrah_obj)


@issue.command("edit-description")
@click.argument("ticket")
@click.pass_obj
def edit_description(jayrah_obj, ticket):
    """Edit issue description with system editor"""
    fields = None  # Get all fields
    ticketj = jayrah_obj.jira.get_issue(ticket, fields=fields)
    edit_success = issue_action.edit_description(ticketj, jayrah_obj)
    ticket_number = ticketj["key"]
    if edit_success and jayrah_obj.verbose:
        log(f"Description updated for {ticket_number}")


@issue.command("transition")
@click.argument("ticket")
@click.pass_obj
def transition(jayrah_obj, ticket):
    """Transition issue to a new status"""
    ticketj = jayrah_obj.jira.get_issue(ticket, fields=None)
    issue_action.transition_issue(ticketj, jayrah_obj)


@cli.command("mcp")
@click.option("--host", default="127.0.0.1", help="Host to bind the MCP server")
@click.option("--port", default=8765, type=int, help="Port to bind the MCP server")
@click.pass_context
def mcp_server_cmd(ctx, host, port):
    """Start the MCP server for programmatic access."""

    # Use the config file from the CLI context if available
    # config_file = ctx.parent.params.get("config_file") if ctx.parent else None
    try:
        asyncio.run(mcp_server.main())
    except KeyboardInterrupt:
        click.secho("MCP server stopped by user", fg="yellow")


@cli.command("git-branch")
@click.argument("search_terms", nargs=-1)
@click.option(
    "--or", "-o", "use_or", is_flag=True, help="Use OR instead of AND for search terms"
)
@click.option(
    "--filter",
    "-f",
    "filters",
    multiple=True,
    help="Filter issues by specific field (e.g., 'status=\"In Progress\"')",
)
@click.pass_obj
def git_branch(jayrah_obj, search_terms, use_or, filters):
    """
    Suggest a git branch name based on a selected issue

    SEARCH_TERMS are optional search terms that filter issues by summary or description.
    Multiple terms are combined with AND by default (or with OR if --or flag is used).

    Example: jayrah git-branch term1 term2   # Searches for term1 AND term2
    Example: jayrah git-branch --or term1 term2   # Searches for term1 OR term2
    Example: jayrah git-branch --filter status="Code Review"   # Filter by status
    """
    try:
        jayrah_obj.suggest_git_branch(search_terms, use_or, filters)
    except click.Abort:
        # Already handled by the suggest_git_branch method
        pass


@cli.command(name="cache")
@click.option("--clear", is_flag=True, help="Clear the cache")
@click.option("--prune", is_flag=True, help="Prune expired cache entries")
@click.option("--stats", is_flag=True, help="Show cache statistics")
@click.option(
    "--max-age", type=int, help="Maximum age of cache entries in seconds (for pruning)"
)
@click.pass_obj
def cache_command(jayrah_obj, clear, prune, stats, max_age):
    """Manage Jira API cache."""

    config = jayrah_obj.config
    jira = jirahttp.JiraHTTP(config)

    if clear:
        jira.cache.clear()
        log("Cache cleared")
        return

    if prune:
        pruned_count = jira.cache.prune(max_age)
        log(f"Pruned {pruned_count} cache entries")
        return

    if not clear and not prune:
        cache_stats = jira.get_cache_stats()

        if "error" in cache_stats:
            log(f"Error getting cache stats: {cache_stats['error']}")
            sys.exit(1)

        log("Cache Statistics:")
        log(f"  Entries: {cache_stats['entries']}")
        log(f"  Size: {cache_stats['size_mb']} MB")
        log(f"  Database Path: {cache_stats['db_path']}")
        log(f"  Cache TTL: {cache_stats['cache_ttl']} seconds")
        log(f"  Serialization: {cache_stats.get('serialization', 'pickle')}")

        if cache_stats.get("oldest_entry"):
            oldest_time = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(cache_stats["oldest_entry"])
            )
            log(f"  Oldest Entry: {oldest_time}")

        if cache_stats.get("newest_entry"):
            newest_time = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(cache_stats["newest_entry"])
            )
            log(f"  Newest Entry: {newest_time}")

        return
