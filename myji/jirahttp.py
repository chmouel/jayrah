import json
import os
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import urlencode

import click

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
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get_curl_command(self, method, url, headers, params=None, json_data=None):
        """Generate an equivalent curl command for debugging purposes."""
        curl_parts = [f"curl -X {method}"]

        # Add headers with proper escaping
        for key, value in headers.items():
            # Mask the authorization token for security
            if key == "Authorization":
                value = "Bearer $(pass show jira/token)"  # Mask the actual token
            curl_parts.append(f"-H '{key}: {value}'")

        # Build the final URL with query parameters
        final_url = url
        if params:
            query_string = urlencode(params)
            final_url = f"{url}?{query_string}"

        # Add JSON data if present
        if json_data:
            json_str = json.dumps(json_data)
            curl_parts.append(f"-d '{json_str}'")

        # Add the URL as the last part
        curl_parts.append(f"'{final_url}'")

        return " ".join(curl_parts)

    def _request(self, method, endpoint, params=None, jeez=None):
        """Helper method to make HTTP requests."""
        url = f"{self.base_url}/{endpoint}"

        if self.verbose:
            click.echo(f"API Request: {method} {url}", err=True)
            if params:
                click.echo(f"Parameters: {params}", err=True)
            if jeez:
                click.echo(f"Request body: {jeez}", err=True)

        # Only use cache for GET requests
        if method.upper() == "GET" and not self.no_cache:
            cached_response = self.cache.get(url, params, jeez)
            if cached_response:
                return cached_response

            if self.verbose:
                click.echo(f"No cache found for: {url}", err=True)

        try:
            if self.verbose:
                click.echo(f"Sending request to {url}...", err=True)
                curl_cmd = self._get_curl_command(
                    method, url, self.headers, params, jeez
                )
                click.echo(f"curl command :\n{curl_cmd}", err=True)

            # Construct the full URL with parameters
            if params:
                query_string = urlencode(params)
                full_url = f"{url}?{query_string}"
            else:
                full_url = url

            # Prepare the request
            request = urllib.request.Request(full_url, method=method)

            # Add headers
            for key, value in self.headers.items():
                request.add_header(key, value)

            # Add JSON data if provided
            data = None
            if jeez:
                data = jeez.dumps(jeez).encode("utf-8")

            # Send the request
            with urllib.request.urlopen(request, data=data) as response:
                status_code = response.status
                response_text = response.read().decode("utf-8")
                response_data = json.loads(response_text) if response_text else {}

            if self.verbose:
                click.echo(f"Response status: {status_code}", err=True)

            # Cache the response for GET requests
            if method.upper() == "GET":
                if self.verbose:
                    click.echo(f"Caching response for: {url}", err=True)
                self.cache.set(url, response_data, params, jeez)

            return response_data
        except urllib.error.HTTPError as e:
            click.echo(f"HTTP error occurred: {e}", err=True)
            click.echo(f"Response: {e.read().decode('utf-8')}", err=True)
            raise click.ClickException(f"HTTP error: {e}")
        except urllib.error.URLError as e:
            click.echo(f"URL error occurred: {e}", err=True)
            raise click.ClickException(f"URL error: {e}")

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
        return self._request("POST", endpoint, jeez=payload)

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
