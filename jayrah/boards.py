#!/usr/bin/env python3
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

    def shell_complete(self, ctx, param, incomplete):
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
    ctx: click.Context = None
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
        start_at = 0
        while True:
            if self.verbose:
                click.echo(f"Fetching batch starting at {start_at}", err=True)

            result = self.jira.search_issues(
                jql,
                start_at=start_at,
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
            if not all_pages or start_at + limit >= total:
                break

            start_at += limit

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
    ):
        """Create a new Jira issue."""
        self.jira.create_issue(
            issuetype=issuetype or "Story",
            summary=summary or click.prompt("Summary"),
            description=description,
            priority=priority,
            assignee=assignee,
            labels=labels,
        )

    def suggest_git_branch(self):
        """Suggest a git branch name based on a selected issue."""
        issues = self.list_issues("assignee = currentUser()")
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
