import asyncio
import os
import pathlib
import sys
import time

import click

from .. import config
from .. import utils as utils
from ..api import jira as jirahttp
from ..commands import mcp_server
from ..config import defaults
from ..ui import boards
from ..utils import log


@click.group()
@click.option("--no-cache", "-n", is_flag=True, help="Disable caching of API responses")
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

    flag_config = {
        "jira_server": jira_server,
        "jira_user": jira_user,
        "jira_password": jira_password,
        "jira_component": jira_component,
        "cache_ttl": cache_ttl,
        "no_cache": no_cache,
        "verbose": verbose,
        "insecure": insecure,
        "jayrah_path": os.path.abspath(sys.argv[0]),
        "ctx": ctx,
    }
    wconfig = config.make_config(flag_config, pathlib.Path(config_file))
    log(f"Using config: {wconfig}", verbose=verbose, verbose_only=True)
    ctx.obj = boards.Boards(wconfig)


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
@click.option(
    "--list-boards", "-l", "list_boards", is_flag=True, help="List available boards"
)
@click.pass_obj
def browse(jayrah_obj, board, search_terms, use_or, filters, list_boards):
    """
    Browse boards

    SEARCH_TERMS are optional search terms that filter issues by summary or description.
    Multiple terms are combined with AND by default (or with OR if --or flag is used).

    Example: jayrah browse my-board term1 term2   # Searches for term1 AND term2
    Example: jayrah browse my-board --or term1 term2   # Searches for term1 OR term2
    Example: jayrah browse my-board --filter status="Code Review"   # Filter by status
    """
    if list_boards:
        boards.show(jayrah_obj.config)
        return
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
    jayrah_obj.fuzzy_search(issues)


@cli.command("create")
@click.option("--type", "-T", "issuetype", help="Issue type")
@click.option("--title", "-t", "title", help="Issue title/summary")
@click.option("--body", "-b", "body", help="Issue description")
@click.option(
    "--body-file",
    "-F",
    "body_file",
    type=click.Path(exists=True),
    help="Read description from file",
)
@click.option("--priority", "-p", "priority", help="Issue priority")
@click.option("--assignee", "-a", "assignee", help="Issue assignee")
@click.option("--labels", "-l", "labels", multiple=True, help="Issue labels")
@click.option(
    "--components", "-c", "components", multiple=True, help="Issue components"
)
@click.option("--template", "-T", "template", help="Use a specific template")
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
    if body_file:
        if not os.path.exists(body_file):
            raise Exception(f"{body_file} does not exist")

        with open(body_file, "r") as f:
            body = f.read()

    if jayrah_obj.config.get("create"):
        if not issuetype and jayrah_obj.config["create"].get("issuetype"):
            issuetype = jayrah_obj.config["create"]["issuetype"]
        if not components and jayrah_obj.config["create"].get("components"):
            components = jayrah_obj.config["create"]["components"]
        if not labels and jayrah_obj.config["create"].get("labels"):
            labels = jayrah_obj.config["create"]["labels"]
        if not assignee and jayrah_obj.config["create"].get("assignee"):
            assignee = jayrah_obj.config["create"]["assignee"]
        if not priority and jayrah_obj.config["create"].get("priority"):
            priority = jayrah_obj.config["create"]["priority"]

    from .create import get_description, interactive_create

    defaults = get_description(
        jayrah_obj,
        title,
        issuetype,
        template=template,
        body=body,
        labels=labels,
        components=components,
        assignee=assignee,
        priority=priority,
    )

    # Create the issue
    interactive_create(jayrah_obj, defaults)


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
