"""Browse command for Jayrah Jira CLI."""

import click

from .. import utils
from ..config import defaults
from ..ui import boards
from .common import cli
from .completions import BoardType


@cli.command("browse")
@click.argument("board", required=False, type=BoardType())
@click.argument("search_terms", nargs=-1)
@click.option("--query", "-q", "jql_query", help="JQL query to use directly")
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
@click.option(
    "--choose",
    is_flag=True,
    help="Automatically select the first matching issue and print its URL",
)
@click.option(
    "--ui",
    "ui_backend",
    type=click.Choice(["textual", "rust"], case_sensitive=False),
    default=None,
    help="UI backend to use (defaults to config `ui_backend`, else textual)",
)
@click.pass_obj
def browse(
    jayrah_obj,
    board,
    search_terms,
    use_or,
    filters,
    list_boards,
    choose,
    jql_query,
    ui_backend,
):
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

    if jql_query:
        jql = jql_query
        order_by = defaults.ORDER_BY
        if board:
            search_terms = (board,) + search_terms
        jayrah_obj.command = "Custom Query"
    else:
        jayrah_obj.command = board
        jql, order_by = boards.check(board, jayrah_obj.config)
        if not jql or not order_by:
            return

    # Use the common function to build the search JQL
    jql = boards.build_search_jql(
        jql, search_terms, use_or, jayrah_obj.verbose, filters
    )

    jayrah_obj.jql = jql
    jayrah_obj.order_by = order_by

    selected_key = None
    explicit_rust_request = bool(ui_backend) or bool(
        jayrah_obj.config.get("_ui_backend_from_cli")
    )
    effective_ui_backend = (
        ui_backend or jayrah_obj.config.get("ui_backend") or defaults.UI_BACKEND
    ).lower()
    if effective_ui_backend not in ("textual", "rust"):
        effective_ui_backend = defaults.UI_BACKEND

    if effective_ui_backend == "rust":
        effective_query = jql
        if order_by and "order by" not in effective_query.lower():
            effective_query = f"{effective_query} ORDER BY {order_by}"
        try:
            selected_key = jayrah_obj.fuzzy_search(
                None,
                auto_choose=choose,
                ui_backend=effective_ui_backend,
                query=effective_query,
            )
        except click.ClickException as rust_error:
            if explicit_rust_request:
                raise
            click.secho(
                f"Rust UI unavailable ({rust_error}); falling back to Textual UI.",
                fg="yellow",
            )
            issues = jayrah_obj.issues_client.list_issues(jql, order_by=order_by)
            if not issues:
                boards.show_no_issues_message(search_terms, use_or, filters)
                return
            selected_key = jayrah_obj.fuzzy_search(
                issues,
                auto_choose=choose,
                ui_backend="textual",
            )
    else:
        issues = jayrah_obj.issues_client.list_issues(jql, order_by=order_by)
        if not issues:
            boards.show_no_issues_message(search_terms, use_or, filters)
            return
        selected_key = jayrah_obj.fuzzy_search(
            issues,
            auto_choose=choose,
            ui_backend=effective_ui_backend,
        )

    if choose:
        if not selected_key:
            return

        server = jayrah_obj.config.get("jira_server")
        if not server:
            raise click.ClickException("jira_server not configured")

        url = utils.make_full_url(selected_key, server)
        if jayrah_obj.config.get("quiet"):
            click.echo(url)
        else:
            click.echo(f"{selected_key} {url}")
