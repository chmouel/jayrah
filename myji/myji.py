#!/usr/bin/env python3
import subprocess
import tempfile
import click

from . import defaults, utils, jirahttp


class MyJi:
    myj_path: str = ""

    def __init__(self, no_cache=False, verbose=False):
        self.verbose = verbose
        self.jira = jirahttp.JiraHTTP(no_cache=no_cache, verbose=verbose)

        if self.verbose:
            click.echo("MyJi initialized with verbose logging enabled", err=True)

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
                click.echo(
                    f"Retrieved {len(batch_issues)} issues (total: {len(issues)})",
                    err=True,
                )

            total = result.get("total", 0)
            if not all_pages or start_at + limit >= total:
                break

            start_at += limit

        if self.verbose:
            click.secho(f"Total issues retrieved: {len(issues)}", fg="blue", err=True)

        return issues

    def fuzzy_search(self, issues):
        """Use fzf to interactively select an issue."""
        if self.verbose:
            click.echo(
                f"Preparing fuzzy search interface for {len(issues)} issues", err=True
            )

        if not issues:
            return None

        with tempfile.NamedTemporaryFile("w+") as tmp:
            max_summary_length = max(
                min(
                    len(issue["fields"]["summary"].strip()), defaults.SUMMARY_MAX_LENGTH
                )
                for issue in issues
            )
            max_ticket_length = max(len(issue["key"]) for issue in issues)
            max_asignee_length = max(
                len(issue["fields"]["assignee"])
                for issue in issues
                if "assignee" in issue["fields"] and issue["fields"]["assignee"]
            )
            max_reporter_length = max(
                len(issue["fields"]["reporter"])
                for issue in issues
                if "reporter" in issue["fields"] and issue["fields"]["reporter"]
            )
            fields = [
                "IT",
                "TICKET".center(max_ticket_length),
                "SUMMARY".center(max_summary_length),
                "ASSIGNEE".center(max_asignee_length),
                "REPORTER".center(max_reporter_length),
                "CREATED".center(10),
                "UPDATED".center(10),
                "RESOLUTION".rjust(10),
            ]
            tmp.write(utils.colorize("cyan", "|").join(fields) + "\n")
            for issue in issues:
                it = issue["fields"]["issuetype"]["name"]
                if it in defaults.ISSUE_TYPE_EMOJIS:
                    it = defaults.ISSUE_TYPE_EMOJIS[it][0]
                else:
                    it = it[:4]
                ss = [it]
                ss.append(issue["key"].strip().ljust(max_ticket_length))
                ss.append(
                    (
                        issue["fields"]["summary"].strip()[
                            : defaults.SUMMARY_MAX_LENGTH - 3
                        ]
                        + "…"
                        if len(issue["fields"]["summary"].strip())
                        > defaults.SUMMARY_MAX_LENGTH
                        else issue["fields"]["summary"].strip()
                    ).ljust(max_summary_length)
                )
                if "assignee" in issue["fields"]:
                    kk = "None"
                    if issue["fields"]["assignee"]:
                        kk = utils.parse_email(
                            issue["fields"]["assignee"]["emailAddress"]
                        )
                    ss += [kk.ljust(max_asignee_length)]
                if "reporter" in issue["fields"]:
                    kk = utils.parse_email(issue["fields"]["reporter"]["emailAddress"])
                    ss += [kk.ljust(max_reporter_length)]
                if "created" in issue["fields"]:
                    kk = utils.show_time(issue["fields"]["created"])
                    ss += [kk.ljust(10)]
                if "updated" in issue["fields"]:
                    kk = utils.show_time(issue["fields"]["updated"])
                    ss += [kk.ljust(10)]
                if "resolution" in issue["fields"]:
                    kk = "Unres"
                    if issue["fields"]["resolution"]:
                        resolution_name = issue["fields"]["resolution"]["name"]
                        kk = defaults.RESOLUTION_EMOJIS.get(
                            resolution_name, resolution_name
                        )
                    ss += [kk.ljust(5)]
                tmp.write(utils.colorize("cyan", "|").join(ss) + "\n")
            tmp.flush()

            if self.verbose:
                click.echo(f"Generated temporary file for fzf: {tmp.name}", err=True)
                click.echo(f"Starting fzf with {len(issues)} issues", err=True)

            preview_cmd = """
                jira issue view {2} --plain|gum format -l markdown --theme=tokyo-night
                """
            fzf_cmd = [
                "fzf",
                "-d",
                "|",
                "--ansi",
                "--header-lines=1",
                "--reverse",
                "--preview",
                preview_cmd,
                "--preview-window",
                "right:hidden:wrap",
                "--bind",
                "ctrl-l:execute(jira issue view {2} --comments 10 | gum format -l markdown)",
                "--bind",
                f"enter:execute({self.myj_path} fzf browser-open {{2}})",
                "--bind",
                "f5:execute:echo 'TODO: Remove labels'",
                "--bind",
                "f8:execute:echo 'TODO: Set sprint'",
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
