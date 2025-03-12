#!/usr/bin/env python3
import os
import sys
import subprocess
import tempfile
import click

import requests

from . import cache, defaults, utils


# Import the JiraHTTP class
class JiraHTTP:
    def __init__(
        self,
        server=None,
        token=None,
        project=None,
        component=None,
        no_cache=False,
        verbose=False,
    ):
        self.server = server or os.getenv("JIRA_SERVER", "issues.redhat.com")
        self.token = token or os.getenv("JIRA_API_TOKEN")
        self.project = project or os.getenv("JIRA_PROJECT", "SRVKP")
        self.component = component or os.getenv("JIRA_COMPONENT", "Pipelines as Code")
        self.base_url = f"https://{self.server}/rest/api/2"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self.no_cache = no_cache
        self.verbose = verbose
        self.cache = cache.JiraCache(verbose=self.verbose)

        if self.verbose:
            click.echo(
                f"Initialized JiraHTTP: server={self.server}, project={self.project}, component={self.component}, no_cache={self.no_cache}",
                err=True,
            )

        if not self.token:
            self.token = utils.get_pass_key(
                os.environ.get("JIRA_PASS_TOKEN_KEY", "jira/token")
            )

        if not self.token:
            click.secho(
                "No JIRA API token found. Set JIRA_API_TOKEN or pass it explicitly.",
                fg="red",
                err=True,
            )
            raise click.ClickException(
                "No JIRA API token found. Set JIRA_API_TOKEN or pass it explicitly."
            )

    def _request(self, method, endpoint, params=None, json=None):
        """Helper method to make HTTP requests."""
        url = f"{self.base_url}/{endpoint}"

        if self.verbose:
            click.echo(f"API Request: {method} {url}", err=True)
            if params:
                click.echo(f"Parameters: {params}", err=True)
            if json:
                click.echo(f"Request body: {json}", err=True)

        # Only use cache for GET requests
        if method.upper() == "GET" and not self.no_cache:
            cached_response = self.cache.get(url, params, json)
            if cached_response:
                if not self.verbose:  # Only show basic message if not verbose
                    click.echo(f"Using cached response for: {url}", err=True)
                return cached_response
            elif self.verbose:
                click.echo(f"No cache found for: {url}", err=True)

        try:
            if self.verbose:
                click.echo(f"Sending request to {url}...", err=True)

            response = requests.request(
                method, url, headers=self.headers, params=params, json=json
            )

            if self.verbose:
                click.echo(f"Response status: {response.status_code}", err=True)

            response.raise_for_status()
            response_data = response.json()

            # Cache the response for GET requests
            if method.upper() == "GET" and not self.no_cache:
                if self.verbose:
                    click.echo(f"Caching response for: {url}", err=True)
                self.cache.set(url, response_data, params, json)

            return response_data
        except requests.exceptions.HTTPError as e:
            click.echo(f"HTTP error occurred: {e}", err=True)
            click.echo(f"Response: {response.text}", err=True)
            raise click.ClickException(f"HTTP error: {e}")

    def search_issues(self, jql, start_at=0, max_results=50, fields=None):
        """
        Search for issues using JQL.

        Args:
            jql (str): JQL query string.
            start_at (int): Index of the first issue to return.
            max_results (int): Maximum number of issues to return.
            fields (list): List of fields to include in the response.

        Returns:
            dict: JSON response containing issues.
        """
        endpoint = "search"
        params = {"jql": jql, "startAt": start_at, "maxResults": max_results}
        if fields:
            params["fields"] = ",".join(fields)

        click.echo(
            f"Searching issues with JQL: '{click.style(jql, fg='cyan')}' "
            f"Params: '{click.style(params.get('fields', ''), fg='cyan')}'",
            err=True,
        )

        if self.verbose:
            click.echo(
                f"Start at: {start_at}, Max results: {max_results}", err=True
            ) if self.verbose else None

        return self._request("GET", endpoint, params=params)

    def create_issue(
        self,
        issuetype,
        summary,
        description=None,
        priority=None,
        assignee=None,
        labels=None,
    ):
        """
        Create a new issue.

        Args:
            issuetype (str): Issue type (e.g., "Story").
            summary (str): Issue summary.
            description (str): Issue description.
            priority (str): Priority level.
            assignee (str): Assignee username.
            labels (list): List of labels.

        Returns:
            dict: JSON response containing the created issue.
        """
        endpoint = "issue"
        payload = {
            "fields": {
                "project": {"key": self.project},
                "summary": summary,
                "issuetype": {"name": issuetype},
                "components": [{"name": self.component}],
            }
        }
        if description:
            payload["fields"]["description"] = description
        if priority:
            payload["fields"]["priority"] = {"name": priority}
        if assignee:
            payload["fields"]["assignee"] = {"name": assignee}
        if labels:
            payload["fields"]["labels"] = labels
        return self._request("POST", endpoint, json=payload)

    def get_issue(self, issue_key, fields=None):
        """
        Get a specific issue by key.

        Args:
            issue_key (str): The issue key (e.g., 'SRVKP-123')
            fields (list): List of fields to include in the response.

        Returns:
            dict: JSON response containing the issue.
        """
        endpoint = f"issue/{issue_key}"
        params = {}
        if fields:
            params["fields"] = ",".join(fields)

        if self.verbose:
            click.echo(f"Getting issue: {issue_key} with fields: {fields}", err=True)

        return self._request("GET", endpoint, params=params)


class MyJi:
    myj_path: str = ""

    def __init__(self, no_cache=False, verbose=False):
        self.verbose = verbose
        self.jira = JiraHTTP(no_cache=no_cache, verbose=verbose)

        if self.verbose:
            click.echo("MyJi initialized with verbose logging enabled", err=True)

    def list_issues(
        self,
        jql,
        order_by="updated",
        limit=100,
        all_pages=True,
        fields=defaults.FIELDS,
    ):
        """List issues using JQL query."""
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
                result = subprocess.run(
                    fzf_cmd, stdin=open(tmp.name), capture_output=True, text=True
                )

                if self.verbose and result.stdout:
                    click.echo(f"User selected: {result.stdout.strip()}", err=True)

            except subprocess.CalledProcessError as e:
                click.secho(f"Error occurred: {e}", fg="red", err=True)
                return None

            return result.stdout.strip().split("\t")[0] if result.stdout else None

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


@click.group()
@click.option("--no-cache", "-n", is_flag=True, help="Disable caching of API responses")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx, no_cache, verbose):
    """Jira Helper Tool"""
    ctx.obj = MyJi(no_cache=no_cache, verbose=verbose)
    ctx.obj.myj_path = os.path.abspath(sys.argv[0])


@cli.command("myissue")
@click.pass_obj
def my_issue(myji):
    """My current issues"""
    jql = "assignee = currentUser() AND resolution = Unresolved"
    if myji.verbose:
        click.echo(f"Running query: {jql}", err=True)
    issues = myji.list_issues(jql)
    selected = myji.fuzzy_search(issues)
    if selected:
        click.secho(f"Selected issue: {selected}", fg="green")


@cli.command("myinprogress")
@click.pass_obj
def my_inprogress(myji):
    """My in-progress issues"""
    jql = (
        'assignee = currentUser() AND status in ("Code Review", "In Progress", "On QA")'
    )
    if myji.verbose:
        click.echo(f"Running query: {jql}", err=True)
    issues = myji.list_issues(jql)
    selected = myji.fuzzy_search(issues)
    if selected:
        click.secho(f"Selected issue: {selected}", fg="green")


@cli.command("pac-current")
@click.pass_obj
def pac_current(myji):
    """Current PAC issues"""
    jql = f'component = "{myji.jira.component}" AND fixVersion in unreleasedVersions({myji.jira.project})'
    if myji.verbose:
        click.echo(f"Running query: {jql}", err=True)
    issues = myji.list_issues(jql)
    selected = myji.fuzzy_search(issues)
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
def pac_create(myji, issuetype, summary, description, priority, assignee, labels):
    """Create PAC issue"""
    labels_list = list(labels) if labels else None
    myji.create_issue(
        issuetype=issuetype,
        summary=summary,
        description=description,
        priority=priority,
        assignee=assignee,
        labels=labels_list,
    )


@cli.command("git-branch")
@click.pass_obj
def git_branch(myji):
    """Suggest git branch"""
    myji.suggest_git_branch()


@cli.group("fzf")
def fzf():
    """FZF preview helper"""
    pass


@fzf.command("browser-open")
@click.argument("ticket")
@click.pass_obj
def browser_open(myji, ticket):
    """Open issue in browser"""
    utils.browser_open_ticket(ticket)
