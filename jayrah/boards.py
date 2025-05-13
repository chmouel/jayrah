import pathlib
import subprocess
import tempfile
import typing
from functools import reduce

import click
import click.shell_completion

from . import config, defaults, jirahttp, utils


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
        show(config)
        return "", ""
    chosen_boards = [x for x in config["boards"] if x.get("name") == board]
    if board is not None and board not in [
        x.get("name") for x in chosen_boards if x.get("name") == board
    ]:
        click.secho("Invalid board: ", fg="red", err=True, nl=False)
        click.echo(f"{board}", err=True)
        show(config)
        return "", ""

    jql = chosen_boards[0].get("jql", "").strip() if chosen_boards else None
    if not jql:
        click.secho(f"Board {board} has no JQL defined", fg="red", err=True)
        return "", ""
    order_by = chosen_boards[0].get("order_by", defaults.ORDER_BY)
    if config.get("verbose"):
        click.echo(f"Running query: {jql} ORDER BY: {order_by}", err=True)
    return jql, order_by


class Boards:
    ctx: click.Context
    command: str = ""
    obj = None
    verbose: bool = False

    def __init__(self, config: dict):
        self.config = config
        self.jira = jirahttp.JiraHTTP(config)
        self.verbose = self.config.get("verbose", False)

        if self.verbose:
            click.echo("Jayrah initialized with verbose logging enabled", err=True)

    # pylint: disable=too-many-positional-arguments
    def list_issues(
        self,
        jql,
        order_by="updated",
        limit=100,
        all_pages=True,
        fields=None,
        start_at=None,
    ):
        """List issues using JQL query."""
        # Handle the dangerous default value
        if fields is None:
            fields = list(defaults.FIELDS)  # Create a copy of the default list

        if self.verbose:
            click.echo(f"Listing issues with JQL: {jql}", err=True)
            click.echo(
                f"Order by: {order_by}, Limit: {limit}, All pages: {all_pages}",
                err=True,
            )
            click.echo(f"Fields: {fields}", err=True)

        issues = []
        current_start_at = 0 if start_at is None else start_at
        while True:
            if self.verbose:
                click.echo(f"Fetching batch starting at {current_start_at}", err=True)

            result = self.jira.search_issues(
                jql,
                start_at=current_start_at,
                max_results=limit,
                fields=fields,
            )

            batch_issues = result.get("issues", [])
            issues.extend(batch_issues)

            if self.verbose:
                utils.log(
                    f"Retrieved {len(batch_issues)} issues (total: {len(issues)})",
                    "DEBUG",
                    verbose_only=True,
                    verbose=self.verbose,
                )

            total = result.get("total", 0)
            if not all_pages or current_start_at + limit >= total:
                break

            current_start_at += limit

        return issues

    def _build_issue_table(
        self,
        issue,
        max_ticket_length,
        max_summary_length,
        max_asignee_length,
        max_reporter_length,
        max_status_length,
    ) -> list:
        it = issue["fields"]["issuetype"]["name"]
        if it in defaults.ISSUE_TYPE_EMOJIS:
            it = defaults.ISSUE_TYPE_EMOJIS[it][0]
        else:
            it = it[:4]
        ss = [it]
        ss.append(issue["key"].strip().ljust(max_ticket_length))
        ss.append(
            (
                issue["fields"]["summary"].strip()[: defaults.SUMMARY_MAX_LENGTH - 3]
                + "…"
                if len(issue["fields"]["summary"].strip()) > defaults.SUMMARY_MAX_LENGTH
                else issue["fields"]["summary"].strip()
            ).ljust(max_summary_length)
        )
        if "assignee" in issue["fields"]:
            kk = "None"
            if issue["fields"]["assignee"]:
                kk = utils.parse_email(issue["fields"]["assignee"])
            ss += [kk.ljust(max_asignee_length)]
        if "reporter" in issue["fields"]:
            kk = utils.parse_email(issue["fields"]["reporter"])
            ss += [kk.ljust(max_reporter_length)]
        if "created" in issue["fields"]:
            kk = utils.show_time(issue["fields"]["created"])
            ss += [kk.ljust(10)]
        if "updated" in issue["fields"]:
            kk = utils.show_time(issue["fields"]["updated"])
            ss += [kk.ljust(10)]
        if "status" in issue["fields"]:
            ss += [issue["fields"]["status"]["name"].ljust(max_status_length)]
        return ss

    def fuzzy_search(self, issues):
        """Use fzf to interactively select an issue."""
        if self.verbose:
            utils.log(
                f"Preparing fuzzy search interface for {len(issues)} issues",
                "DEBUG",
                verbose_only=True,
                verbose=self.verbose,
            )

        if not issues:
            return None

        with tempfile.NamedTemporaryFile("w+") as tmp:
            tmp.write(
                f"Press {click.style('F1', fg='red')} for help -- {click.style('Ctrl-v', fg='red')} for preview -- {click.style('Ctrl-r', fg='red')} to reload -- {click.style('Ctrl-a', fg='red')} for actions\n"
            )

            def get_max_length(field_path, default_value=0):
                return max(
                    (len(value) if value else default_value)
                    for issue in issues
                    if (
                        value := reduce(
                            lambda obj, key: obj.get(key)
                            if isinstance(obj, dict)
                            else None,
                            field_path.split("."),
                            issue,
                        )
                    )
                    is not None
                )

            max_summary_length = min(
                get_max_length("fields.summary", 0), defaults.SUMMARY_MAX_LENGTH
            )
            max_ticket_length = get_max_length("key")
            max_asignee_length = get_max_length("fields.assignee")
            max_reporter_length = get_max_length("fields.reporter")
            max_status_length = get_max_length("fields.status.name")
            fields = [
                "IT",
                "TICKET".center(max_ticket_length),
                "SUMMARY".center(max_summary_length),
                "ASSIGNEE".center(max_asignee_length),
                "REPORTER".center(max_reporter_length),
                "CREATED".center(10),
                "UPDATED".center(10),
                "STATUS".center(max_status_length),
            ]
            tmp.write(utils.colorize("cyan", "|").join(fields) + "\n")
            for issue in issues:
                ss = self._build_issue_table(
                    issue,
                    max_ticket_length,
                    max_summary_length,
                    max_asignee_length,
                    max_reporter_length,
                    max_status_length,
                )
                tmp.write(utils.colorize("cyan", "|").join(ss) + "\n")
            tmp.flush()

            if self.verbose:
                utils.log(
                    f"Temporary file created at {tmp.name}",
                    "DEBUG",
                    verbose_only=True,
                    verbose=self.verbose,
                )

            if self.config.get("no_fzf"):
                with open(tmp.name, encoding="utf-8") as tmp_file:
                    print(tmp_file.read().strip())
                return None

            preview_cmd = f"{self.config.get('jayrah_path')} issue view {{2}}"
            help_cmd = f"clear;{self.config.get('jayrah_path')} help;bash -c \"read -n1 -p 'Press a key to exit'\""
            fzf_cmd = [
                "fzf",
                "-d",
                "|",
                "--ansi",
                "--header-lines=2",
                "--reverse",
                "--preview",
                preview_cmd,
                "--preview-window",
                "right:hidden:wrap",
                "--bind",
                # TODO: arguments
                f"ctrl-r:reload({self.config.get('jayrah_path')} --no-fzf -n browse {self.command})",
                "--bind",
                f"enter:execute({self.config.get('jayrah_path')} issue open {{2}})",
                "--bind",
                f"ctrl-a:execute({self.config.get('jayrah_path')} issue action {{2}})",
                "--bind",
                f"f1:execute({help_cmd})",
            ]
            fzf_cmd += defaults.FZFOPTS

            try:
                # Add check parameter and use with statement for file opening
                with open(tmp.name, encoding="utf-8") as tmp_file:
                    result = subprocess.run(
                        fzf_cmd,
                        stdin=tmp_file,
                        capture_output=True,
                        text=True,
                        check=False,
                    )

                if self.verbose and result.stdout:
                    click.echo(f"User selected: {result.stdout.strip()}", err=True)

            except subprocess.CalledProcessError as e:
                click.secho(f"Error occurred: {e}", fg="red", err=True)
                return None

            return result.stdout.strip().split("\t")[0] if result.stdout else None

    # pylint: disable=too-many-positional-arguments
    def create_issue(
        self,
        issuetype=None,
        summary=None,
        description=None,
        priority=None,
        assignee=None,
        labels=None,
        components: list = [],
    ):
        """Create a new Jira issue."""
        summary = summary or click.prompt("Summary")
        if not description:
            editor_text = (
                "\n\n"
                "# Edit description for the new issue with summary:\n"
                "# {description}\n"
                "# The first lines starting with # will be ignored\n"
                "# Save and exit the editor to submit changes, or exit without saving to cancel\n"
            )
            description = utils.edit_text_with_editor(editor_text, extension=".jira")
        if not components and self.config.get("default_component"):
            components = [self.config.get("default_component")]
        ret = self.jira.create_issue(
            issuetype=issuetype or "Story",
            summary=summary,
            description=description,
            priority=priority,
            assignee=assignee,
            labels=labels,
            components=components,
        )

        print(
            f"Issue created: {utils.make_full_url(ret.get('key'), self.config.get('jira_server'))}"
        )

    def suggest_git_branch(self, search_terms=None, use_or=False, filters=None):
        """Suggest a git branch name based on a selected issue.

        Args:
            search_terms: Optional list of search terms to filter issues by summary or description
            use_or: Whether to combine search terms with OR instead of AND
            filters: Optional list of field-specific filters
        """
        base_jql = "assignee = currentUser()"

        # Use the common function to build the search JQL
        jql = build_search_jql(base_jql, search_terms, use_or, self.verbose, filters)

        issues = self.list_issues(jql)

        if not issues:
            show_no_issues_message(search_terms, use_or, filters)
            raise click.Abort("No issues found")

        selected = self.fuzzy_search(issues)
        if not selected:
            click.secho("No issue selected", fg="yellow", err=True)
            raise click.Abort("No issue selected")

        if self.verbose:
            click.echo(f"Getting issue details for {selected}", err=True)

        issue = self.jira.get_issue(selected, fields=["summary"])
        summary = issue["fields"]["summary"]

        branch = f"{selected}-{summary.replace(' ', '-').lower()[:75]}"
        click.secho(f"Suggested branch name: {branch}", fg="blue")
        click.echo(branch)


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
                        err=True,
                    )

        if filter_conditions:
            # Combine filter conditions with AND and add to the query
            filter_jql = " AND ".join(filter_conditions)
            extended_jql = f"({extended_jql}) AND ({filter_jql})"

            # Show filter message if verbose
            if verbose:
                click.secho(f"Applied filters: {filter_jql}", fg="blue", err=True)

    # Show search message if verbose
    if verbose and search_terms:
        terms_text = format_search_terms(search_terms, use_or)
        click.secho(f"Searching for: {terms_text}", fg="blue", err=True)

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
