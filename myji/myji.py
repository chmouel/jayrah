#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import tempfile

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
            utils.log(
                f"Initialized JiraHTTP: server={self.server}, project={self.project}, component={self.component}, no_cache={self.no_cache}",
                "DEBUG",
                verbose_only=True,
                verbose=self.verbose,
            )

        if not self.token:
            self.token = utils.get_pass_key(
                os.environ.get("JIRA_PASS_TOKEN_KEY", "jira/token")
            )

        if not self.token:
            utils.log(
                "No JIRA API token found. Set JIRA_API_TOKEN or pass it explicitly.",
                "ERROR",
            )
            raise ValueError(
                "No JIRA API token found. Set JIRA_API_TOKEN or pass it explicitly."
            )

    def _request(self, method, endpoint, params=None, json=None):
        """Helper method to make HTTP requests."""
        url = f"{self.base_url}/{endpoint}"

        if self.verbose:
            utils.log(
                f"API Request: {method} {url}",
                "DEBUG",
                verbose_only=True,
                verbose=self.verbose,
            )
            if params:
                utils.log(
                    f"Parameters: {params}",
                    "DEBUG",
                    verbose_only=True,
                    verbose=self.verbose,
                )
            if json:
                utils.log(
                    f"Request body: {json}",
                    "DEBUG",
                    verbose_only=True,
                    verbose=self.verbose,
                )

        # Only use cache for GET requests
        if method.upper() == "GET" and not self.no_cache:
            cached_response = self.cache.get(url, params, json)
            if cached_response:
                if not self.verbose:  # Only show basic message if not verbose
                    utils.log(f"Using cached response for: {url}", "DEBUG")
                return cached_response
            elif self.verbose:
                utils.log(
                    f"No cache found for: {url}",
                    "DEBUG",
                    verbose_only=True,
                    verbose=self.verbose,
                )

        try:
            if self.verbose:
                utils.log(
                    f"Sending request to {url}...",
                    "DEBUG",
                    verbose_only=True,
                    verbose=self.verbose,
                )

            response = requests.request(
                method, url, headers=self.headers, params=params, json=json
            )

            if self.verbose:
                utils.log(
                    f"Response status: {response.status_code}",
                    "DEBUG",
                    verbose_only=True,
                    verbose=self.verbose,
                )

            response.raise_for_status()
            response_data = response.json()

            # Cache the response for GET requests
            if method.upper() == "GET" and not self.no_cache:
                if self.verbose:
                    utils.log(
                        f"Caching response for: {url}",
                        "DEBUG",
                        verbose_only=True,
                        verbose=self.verbose,
                    )
                self.cache.set(url, response_data, params, json)

            return response_data
        except requests.exceptions.HTTPError as e:
            utils.log(f"HTTP error occurred: {e}", "ERROR")
            utils.log(f"Response: {response.text}", "ERROR")
            raise

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

        utils.log(
            f"Searching issues with JQL: '{utils.colorize('cyan', jql)}' Params: '{utils.colorize('cyan', params['fields'])}'",
            "DEBUG",
        )

        if self.verbose:
            utils.log(
                f"Start at: {start_at}, Max results: {max_results}",
                "DEBUG",
                verbose_only=True,
                verbose=self.verbose,
            )

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
            utils.log(
                f"Getting issue: {issue_key} with fields: {fields}",
                "DEBUG",
                verbose_only=True,
                verbose=self.verbose,
            )

        return self._request("GET", endpoint, params=params)


class MyJi:
    myj_path: str = ""

    def __init__(self, no_cache=False, verbose=False):
        self.verbose = verbose
        self.jira = JiraHTTP(no_cache=no_cache, verbose=verbose)

        if self.verbose:
            utils.log(
                "MyJi initialized with verbose logging enabled",
                "DEBUG",
                verbose_only=True,
                verbose=self.verbose,
            )

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
            utils.log(
                f"Listing issues with JQL: {jql}",
                "DEBUG",
                verbose_only=True,
                verbose=self.verbose,
            )
            utils.log(
                f"Order by: {order_by}, Limit: {limit}, All pages: {all_pages}",
                "DEBUG",
                verbose_only=True,
                verbose=self.verbose,
            )
            utils.log(
                f"Fields: {fields}", "DEBUG", verbose_only=True, verbose=self.verbose
            )

        issues = []
        start_at = 0
        while True:
            if self.verbose:
                utils.log(
                    f"Fetching batch starting at {start_at}",
                    "DEBUG",
                    verbose_only=True,
                    verbose=self.verbose,
                )

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

        if self.verbose:
            utils.log(
                f"Total issues retrieved: {len(issues)}",
                "SUCCESS",
                verbose_only=True,
                verbose=self.verbose,
            )

        return issues

    def fuzzy_search(self, issues):
        """Use fzf to interactively select an issue."""
        if self.verbose:
            utils.log(
                f"Preparing fuzzy search interface for {len(issues)} issues",
                "DEBUG",
                verbose_only=True,
                verbose=self.verbose,
            )

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
                utils.log(
                    f"Generated temporary file for fzf: {tmp.name}",
                    "DEBUG",
                    verbose_only=True,
                    verbose=self.verbose,
                )
                utils.log(
                    f"Starting fzf with {len(issues)} issues",
                    "DEBUG",
                    verbose_only=True,
                    verbose=self.verbose,
                )

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
                    utils.log(
                        f"User selected: {result.stdout.strip()}",
                        "DEBUG",
                        verbose_only=True,
                        verbose=self.verbose,
                    )

            except subprocess.CalledProcessError as e:
                utils.log(f"Error occurred: {e}", "ERROR")
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
            summary=summary or input("Summary: "),
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
            utils.log("No issue selected", "WARNING")
            sys.exit("No issue selected")

        utils.log(
            f"Getting issue details for {selected}",
            "DEBUG",
            verbose_only=True,
            verbose=self.verbose,
        )
        issue = self.jira.get_issue(selected, fields=["summary"])
        summary = issue["fields"]["summary"]

        branch = f"{selected}-{summary.replace(' ', '-').lower()[:75]}"
        utils.log(f"Suggested branch name: {branch}", "SUCCESS")
        print(branch)

    def run(self):
        self.myj_path = os.path.abspath(sys.argv[0])
        parser = argparse.ArgumentParser(description="Jira Helper")
        subparsers = parser.add_subparsers(dest="command")

        # Add subcommands mirroring the original bash script
        subparsers.add_parser("myissue", help="My current issues")
        subparsers.add_parser("myinprogress", help="My in-progress issues")
        subparsers.add_parser("pac-current", help="Current PAC issues")
        subparsers.add_parser("pac-create", help="Create PAC issue")
        subparsers.add_parser("git-branch", help="Suggest git branch")
        fzfparsers = subparsers.add_parser("fzf", help="fzf preview helper")
        fzf_subparsers = fzfparsers.add_subparsers(dest="fzf_command")
        browser_open = fzf_subparsers.add_parser(
            "browser-open", help="Open issue in browser"
        )
        browser_open.add_argument("ticket", help="Ticket number to open")

        # Add global options
        parser.add_argument(
            "-n",
            "--no-cache",
            action="store_true",
            help="Disable caching of API responses",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="Enable verbose output",
        )

        args = parser.parse_args()

        # Reinitialize jira client with flags if specified
        if args.no_cache or args.verbose:
            self.jira = JiraHTTP(no_cache=args.no_cache, verbose=args.verbose)
            self.verbose = args.verbose

            if self.verbose:
                utils.log(
                    f"Command: {args.command}",
                    "DEBUG",
                    verbose_only=True,
                    verbose=self.verbose,
                )
                utils.log(
                    f"No cache: {args.no_cache}",
                    "DEBUG",
                    verbose_only=True,
                    verbose=self.verbose,
                )

        if args.command == "pac-create":
            self.create_issue()
        elif args.command == "git-branch":
            self.suggest_git_branch()
        elif args.command == "fzf":
            otherargs = sys.argv[2:]
            if otherargs:
                if otherargs[0] == "browser-open":
                    if len(otherargs) > 1:
                        ticket = otherargs[1]
                    else:
                        raise ValueError("Ticket number is required")
                    ticket = otherargs[1]
                    utils.browser_open_ticket(ticket)
        else:
            # Default to listing issues with appropriate JQL
            jql = {
                "myissue": "assignee = currentUser() AND resolution = Unresolved",
                "myinprogress": 'assignee = currentUser() AND status in ("Code Review", "In Progress", "On QA")',
                "pac-current": f'component = "{self.jira.component}" AND fixVersion in unreleasedVersions({self.jira.project})',
            }.get(args.command, "")

            if jql:
                utils.log(
                    f"Running query: {jql}",
                    "DEBUG",
                    verbose_only=True,
                    verbose=self.verbose,
                )
                issues = self.list_issues(jql)
                selected = self.fuzzy_search(issues)
                if selected:
                    utils.log(f"Selected issue: {selected}", "SUCCESS")
            else:
                parser.print_help()
