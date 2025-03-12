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
        self, server=None, token=None, project=None, component=None, no_cache=False
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
        self.cache = cache.JiraCache()
        if not self.token:
            raise ValueError(
                "No JIRA API token found. Set JIRA_API_TOKEN or pass it explicitly."
            )

    def _request(self, method, endpoint, params=None, json=None):
        """Helper method to make HTTP requests."""
        url = f"{self.base_url}/{endpoint}"

        # Only use cache for GET requests
        if method.upper() == "GET" and not self.no_cache:
            cached_response = self.cache.get(url, params, json)
            if cached_response:
                print(f"Using cached response for: {url}")
                return cached_response

        try:
            response = requests.request(
                method, url, headers=self.headers, params=params, json=json
            )
            response.raise_for_status()
            response_data = response.json()

            # Cache the response for GET requests
            if method.upper() == "GET" and not self.no_cache:
                self.cache.set(url, response_data, params, json)

            return response_data
        except requests.exceptions.HTTPError as e:
            print(f"HTTP error occurred: {e}")
            print(f"Response: {response.text}")
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
        print(
            f"Searching issues with JQL: '{utils.colorize('cyan', jql)}' Params: '{utils.colorize('cyan', params['fields'])}'"
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
        return self._request("GET", endpoint, params=params)


class MyJi:
    def __init__(self, no_cache=False):
        self.jira = JiraHTTP(no_cache=no_cache)

    def list_issues(
        self,
        jql,
        order_by="updated",
        limit=100,
        all_pages=True,
        fields=defaults.FIELDS,
    ):
        """List issues using JQL query."""
        issues = []
        start_at = 0
        while True:
            result = self.jira.search_issues(
                jql,
                start_at=start_at,
                max_results=limit,
                fields=fields,
            )
            issues.extend(result.get("issues", []))
            total = result.get("total", 0)
            if not all_pages or start_at + limit >= total:
                break
            start_at += limit
        return issues

    def fuzzy_search(self, issues):
        """Use fzf to interactively select an issue."""

        # __import__("pprint").pprint(issues)
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
                "enter:execute(jira open {2})",
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
            except subprocess.CalledProcessError as e:
                print(f"Error occurred: {e}")
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
            sys.exit("No issue selected")

        issue = self.jira.get_issue(selected, fields=["summary"])
        summary = issue["fields"]["summary"]

        branch = f"{selected}-{summary.replace(' ', '-').lower()[:75]}"
        print(branch)

    def run(self):
        parser = argparse.ArgumentParser(description="Jira Helper")
        subparsers = parser.add_subparsers(dest="command")

        # Add subcommands mirroring the original bash script
        subparsers.add_parser("myissue", help="My current issues")
        subparsers.add_parser("myinprogress", help="My in-progress issues")
        subparsers.add_parser("pac-current", help="Current PAC issues")
        subparsers.add_parser("pac-create", help="Create PAC issue")
        subparsers.add_parser("git-branch", help="Suggest git branch")

        # Add global options
        parser.add_argument(
            "-n",
            "--no-cache",
            action="store_true",
            help="Disable caching of API responses",
        )

        args = parser.parse_args()

        # Reinitialize jira client with no_cache flag if specified
        if args.no_cache:
            self.jira = JiraHTTP(no_cache=args.no_cache)

        if args.command == "pac-create":
            self.create_issue()
        elif args.command == "git-branch":
            self.suggest_git_branch()
        else:
            # Default to listing issues with appropriate JQL
            jql = {
                "myissue": "assignee = currentUser() AND resolution = Unresolved",
                "myinprogress": 'assignee = currentUser() AND status in ("Code Review", "In Progress", "On QA")',
                "pac-current": f'component = "{self.jira.component}" AND fixVersion in unreleasedVersions({self.jira.project})',
            }.get(args.command, "")

            if jql:
                issues = self.list_issues(jql)
                selected = self.fuzzy_search(issues)
                if selected:
                    print(f"Selected issue: {selected}")
            else:
                parser.print_help()
