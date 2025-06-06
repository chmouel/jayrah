"""Browse command for Jayrah Jira CLI."""

import click

from ..ui import boards
from .common import cli


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
