"""Board management and selection utilities for Jayrah UI."""

import pathlib
import typing

import click
import click.shell_completion

from .. import config, utils
from ..api import jira as jirahttp
from ..config import defaults
from . import issues
from .tui import run_textual_browser


class BoardType(click.ParamType):
    name = "board"

    def shell_complete(self, ctx, _, incomplete):
        config_file = defaults.CONFIG_FILE
        if ctx.parent.params.get("config_file"):
            config_file = pathlib.Path(ctx.parent.params.get("config_file"))
        cfg = config.read_config({}, config_file)
        return [
            click.shell_completion.CompletionItem(x)
            for x in [x.get("name") for x in cfg.get("boards", [])]
            if x.startswith(incomplete)
        ]


def show(config):
    click.echo("Available boards:")
    for x in config.get("boards", []):
        click.secho(f"  {x.get('name')}", fg="cyan", nl=False)
        if x.get("description"):
            click.secho(f" - {x.get('description')}", italic=True, nl=False)
        click.echo()


def check(board, config) -> typing.Tuple[str, str]:
    if not board:
        if len(config["boards"]) == 0:
            click.secho("no boards has been setup", fg="red")
            raise ValueError("No boards has been setup in your config file")
        chosen_boards = [config["boards"][0]]
        click.secho(f"Using board {chosen_boards[0].get('name')}", fg="green")
    else:
        chosen_boards = [x for x in config["boards"] if x.get("name") == board]
        if board is not None and board not in [
            x.get("name") for x in chosen_boards if x.get("name") == board
        ]:
            click.secho("Invalid board: ", fg="red", nl=False)
            print(f"{board}")
            show(config)
            return "", ""

    jql = chosen_boards[0].get("jql", "").strip() if chosen_boards else None
    if not jql:
        click.secho(f"Board {board} has no JQL defined", fg="red")
        return "", ""
    order_by = chosen_boards[0].get("order_by", defaults.ORDER_BY)
    if config.get("verbose"):
        print(f"Running query: {jql} ORDER BY: {order_by}")
    return jql, order_by


class Boards:
    ctx: click.Context
    command: str = ""
    obj = None
    verbose: bool = False
    jql: str = ""
    order_by: str = ""

    def __init__(self, config: dict):
        self.config = config
        self.jira = jirahttp.JiraHTTP(config)
        self.verbose = self.config.get("verbose", False)

        if self.verbose:
            print("Jayrah initialized with verbose logging enabled")

        self.issues_client = issues.Issues(self.config, self.jira)

    def fuzzy_search(self, issues):
        """Use interactive UI to select an issue."""
        if self.verbose:
            utils.log(
                f"Preparing UI interface for {len(issues)} issues",
                "DEBUG",
                verbose_only=True,
                verbose=self.verbose,
            )

        try:
            selected_key = run_textual_browser(
                issues, self.config, self.command, self.jql, self.order_by
            )
        except Exception as e:
            click.secho(f"Error occurred with Textual UI: {e}", fg="red")
            raise e
        if self.verbose and selected_key:
            print(f"User selected: {selected_key}")

        return selected_key


def build_search_jql(
    base_jql: str,
    search_terms,
    use_or: bool = False,
    verbose: bool = False,
    filters=None,
) -> str:
    """Build a JQL query with search terms and field filters.

    Args:
        base_jql: The base JQL query to extend with search conditions
        search_terms: A list of search terms to filter issues by summary or description
        use_or: Whether to combine search terms with OR instead of AND
        verbose: Whether to display verbose output
        filters: Optional list of field-specific filters in format "field=value"

    Returns:
        The extended JQL query string with search conditions and filters
    """
    extended_jql = base_jql

    # Add search terms if provided
    if search_terms:
        # Create individual search conditions for each term
        search_conditions = []
        for term in search_terms:
            term_condition = f'(summary ~ "{term}" OR description ~ "{term}")'
            search_conditions.append(term_condition)

        # Combine search conditions with AND or OR based on the flag
        operator = " OR " if use_or else " AND "
        combined_condition = operator.join(search_conditions)

        # Add combined condition to existing JQL
        extended_jql = f"({base_jql}) AND ({combined_condition})"

    # Add field-specific filters if provided
    if filters:
        filter_conditions = []
        for filter_expr in filters:
            # Split the filter expression at the first equals sign
            parts = filter_expr.split("=", 1)
            if len(parts) == 2:
                field, value = parts[0].strip(), parts[1].strip()

                # Remove quotes from value if they're already present
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]

                # Add quotes around the value if it contains spaces and isn't already quoted
                if " " in value:
                    value = f'"{value}"'

                filter_conditions.append(f"{field} = {value}")
            else:
                # Invalid filter format, log a warning if verbose
                if verbose:
                    click.secho(
                        f"Warning: Ignoring invalid filter format: {filter_expr}",
                        fg="yellow",
                    )

        if filter_conditions:
            # Combine filter conditions with AND and add to the query
            filter_jql = " AND ".join(filter_conditions)
            extended_jql = f"({extended_jql}) AND ({filter_jql})"

            # Show filter message if verbose
            if verbose:
                click.secho(f"Applied filters: {filter_jql}", fg="blue")

    # Show search message if verbose
    if verbose and search_terms:
        terms_text = format_search_terms(search_terms, use_or)
        click.secho(f"Searching for: {terms_text}", fg="blue")

    return extended_jql


def format_search_terms(search_terms, use_or: bool = False) -> str:
    """Format search terms for display in messages.

    Args:
        search_terms: A list of search terms
        use_or: Whether to combine terms with OR instead of AND

    Returns:
        A formatted string of search terms joined with the appropriate operator
    """
    if not search_terms:
        return ""

    operator = " OR " if use_or else " AND "
    return operator.join(f"'{term}'" for term in search_terms)


def show_no_issues_message(
    search_terms=None, use_or: bool = False, filters=None
) -> None:
    """Display a standardized message when no issues are found.

    Args:
        search_terms: Optional list of search terms that were used
        use_or: Whether OR logic was used instead of AND
        filters: Optional list of field-specific filters that were used
    """
    message_parts = []

    if search_terms:
        terms_text = format_search_terms(search_terms, use_or)
        message_parts.append(terms_text)

    if filters:
        filter_text = " AND ".join(f"{f}" for f in filters)
        message_parts.append(f"filters: {filter_text}")

    if message_parts:
        combined_message = " with " + ", ".join(message_parts)
        click.secho(
            f"No issues found matching{combined_message}", fg="yellow", err=True
        )
    else:
        click.secho("No issues found", fg="yellow", err=True)
