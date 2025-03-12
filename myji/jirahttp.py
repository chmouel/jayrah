import os
import click
import requests

from . import cache, utils


class JiraHTTP:
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-positional-arguments
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

            if self.verbose:
                click.echo(f"No cache found for: {url}", err=True)

        try:
            if self.verbose:
                click.echo(f"Sending request to {url}...", err=True)

            # Add timeout parameter to prevent indefinite hanging
            response = requests.request(
                method, url, headers=self.headers, params=params, json=json, timeout=30
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
            click.echo(f"Start at: {start_at}, Max results: {max_results}", err=True)

        return self._request("GET", endpoint, params=params)

    # pylint: disable=too-many-positional-arguments
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
