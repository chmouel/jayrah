import json
import sqlite3
import ssl
import urllib.error
import urllib.request
from urllib.parse import urlencode

import click

from ..utils import cache, log


class JiraHTTP:
    verbose: bool = False

    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-positional-arguments
    def __init__(self, config):
        self.config = config
        server = self.config.get("jira_server")
        self.base_url = f"{server}/rest/api/2"
        self.cache = cache.JiraCache(config)
        self.verbose = self.config.get("verbose", False)
        self.insecure = self.config.get("insecure", False)

        if self.verbose:
            log(
                f"Initialized JiraHTTP: server={server}, project={self.config.get('jira_component')}, no_cache={self.config.get('no_cache')}, insecure={self.insecure}",
            )

        self.headers = {
            "Authorization": f"Bearer {self.config.get('jira_password')}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Create a custom opener with SSL context if insecure mode is enabled
        if self.insecure:
            # Create a custom SSL context that doesn't verify certificates
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            # Create and install a custom opener with our SSL context
            opener = urllib.request.build_opener(
                urllib.request.HTTPSHandler(context=context)
            )
            urllib.request.install_opener(opener)

            if self.verbose:
                log("WARNING: SSL certificate verification disabled")

    def _get_curl_command(self, method, url, headers, params=None, json_data=None):
        """Generate an equivalent curl command for debugging purposes."""
        curl_parts = [f"curl -X {method}"]

        # Add insecure flag if enabled
        if self.insecure:
            curl_parts.append("-k")

        # Add headers with proper escaping
        for key, value in headers.items():
            # Mask the authorization token for security
            if key == "Authorization":
                value = "Bearer ${JIRA_API_TOKEN}"  # Mask the actual token
            curl_parts.append(f'-H "{key}: {value}"')

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

    def _request(
        self, method, endpoint, params=None, jeez=None, label=None, use_cache=True
    ):
        """Helper method to make HTTP requests."""
        url = f"{self.base_url}/{endpoint}"

        if self.verbose:
            log(f"API call Requested: {method} {url}")
            if params:
                log(f"Parameters: {params}")
            if jeez:
                log(f"Request body: {jeez}")

        # Only use cache for GET requests
        if method.upper() == "GET" and not self.config.get("no_cache"):
            if use_cache:
                cached_response = self.cache.get(url, params, jeez)
                if cached_response:
                    if self.verbose:
                        log("Using cached response from SQLite database")
                    return cached_response

            if self.verbose:
                log(f"No cache found for: {url}")

        try:
            if self.verbose:
                log(f"Sending request to {url}...")
                curl_cmd = self._get_curl_command(
                    method, url, self.headers, params, jeez
                )
                log(f"curl command :\n{curl_cmd}")

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
                data = json.dumps(jeez).encode("utf-8")
            # Show a spinner while making the request (if not in verbose mode)
            if not self.verbose:
                with click.progressbar(
                    length=1,
                    label=label,
                    show_eta=False,
                    show_percent=False,
                    fill_char="⣾⣷⣯⣟⡿⢿⣻⣽"[0],  # Use first char of spinner sequence
                    empty_char=" ",
                ) as bar:
                    # Send the request
                    with urllib.request.urlopen(request, data=data) as response:
                        status_code = response.status
                        response_text = response.read().decode("utf-8")
                        response_data = (
                            json.loads(response_text) if response_text else {}
                        )
                    bar.update(1)
            else:
                # Send the request without spinner in verbose mode
                with urllib.request.urlopen(request, data=data) as response:
                    status_code = response.status
                    response_text = response.read().decode("utf-8")
                    response_data = json.loads(response_text) if response_text else {}
                log(f"Response status: {status_code}")

            # Cache the response for GET requests
            if method.upper() == "GET":
                if self.verbose:
                    log(f"Caching response for: {url}")
                self.cache.set(url, response_data, params, jeez)
            return response_data
        except urllib.error.HTTPError as e:
            log(f"HTTP error occurred: {e}")
            log(f"Response: {e.read().decode('utf-8')}")
            raise click.ClickException(f"HTTP error: {e}")
        except urllib.error.URLError as e:
            log(f"URL error occurred: {e}")
            raise click.ClickException(f"URL error: {e}")

    def search_issues(
        self, jql, start_at=0, max_results=50, fields=None, use_cache: bool = True
    ):
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

        if self.verbose:
            log(
                f"Searching issues with JQL: '{click.style(jql, fg='cyan')}' "
                f"Params: '{click.style(params.get('fields', ''), fg='cyan')}'",
            )

        if self.verbose:
            log(f"Start at: {start_at}, Max results: {max_results}")

        label = "✨ Fetching Jira issues"
        if start_at != 0:
            label += f" from {start_at} to {start_at + max_results}"
        return self._request(
            "GET",
            endpoint,
            params=params,
            label=label,
            use_cache=use_cache,
        )

    # pylint: disable=too-many-positional-arguments
    def create_issue(
        self,
        issuetype,
        summary,
        description=None,
        priority=None,
        assignee=None,
        labels=None,
        components: list = [],
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
                "project": {"key": self.config.get("jira_project")},
                "summary": summary,
                "issuetype": {"name": issuetype},
            }
        }
        if components:
            payload["fields"]["components"] = [
                {"name": component} for component in components
            ]
        if description:
            payload["fields"]["description"] = description
        if priority:
            payload["fields"]["priority"] = {"name": priority}
        if assignee:
            payload["fields"]["assignee"] = {"name": assignee}
        if labels:
            payload["fields"]["labels"] = labels
        return self._request("POST", endpoint, jeez=payload)

    def get_issue(self, issue_key, fields=None, use_cache: bool = True):
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
            log(f"Getting issue: {issue_key} with fields: {fields}")

        return self._request("GET", endpoint, params=params, use_cache=use_cache)

    def update_issue(self, issue_key, fields):
        """
        Update an existing issue's fields.

        Args:
            issue_key (str): The issue key (e.g., 'SRVKP-123')
            fields (dict): Fields to update (e.g., {'description': '...'})

        Returns:
            dict: JSON response containing the updated issue.
        """
        endpoint = f"issue/{issue_key}"
        payload = {"fields": fields}

        if self.verbose:
            log(f"Updating issue: {issue_key}")
            log(f"Fields to update: {list(fields.keys())}")

        return self._request("PUT", endpoint, jeez=payload)

    def get_transitions(self, issue_key):
        endpoint = f"issue/{issue_key}/transitions"

        return self._request("GET", endpoint, label="All transitions")

    def transition_issue(self, issue_key, transition_id):
        """
        Transition an issue to a new status.

        Args:
            issue_key (str): The issue key (e.g., 'SRVKP-123')
            transition_id (str): The ID of the transition to perform

        Returns:
            dict: JSON response from the API (empty for successful transitions)
        """
        endpoint = f"issue/{issue_key}/transitions"
        payload = {"transition": {"id": transition_id}}

        if self.verbose:
            log(
                f"Transitioning issue: {issue_key} with transition ID: {transition_id}",
            )

        return self._request("POST", endpoint, jeez=payload)

    def get_cache_stats(self):
        """
        Get statistics about the SQLite cache usage.

        Returns:
            dict: Statistics about the cache usage
        """
        if self.verbose:
            log("Fetching cache statistics...")

        try:
            # Connect to the SQLite database
            conn = self.cache._get_connection()
            cursor = conn.cursor()

            # Get total number of entries
            cursor.execute("SELECT COUNT(*) FROM cache")
            total_entries = cursor.fetchone()[0]

            # Get total size in bytes (sum of the BLOB sizes)
            cursor.execute("SELECT SUM(length(data)) FROM cache")
            total_size = cursor.fetchone()[0] or 0

            # Get oldest cache entry
            cursor.execute("SELECT MIN(timestamp) FROM cache")
            oldest_timestamp = cursor.fetchone()[0]

            # Get newest cache entry
            cursor.execute("SELECT MAX(timestamp) FROM cache")
            newest_timestamp = cursor.fetchone()[0]

            conn.close()

            # Calculate additional stats
            size_mb = round(total_size / (1024 * 1024), 2) if total_size else 0

            stats = {
                "entries": total_entries,
                "size_bytes": total_size,
                "size_mb": size_mb,
                "oldest_entry": oldest_timestamp,
                "newest_entry": newest_timestamp,
                "cache_ttl": self.cache.cache_ttl,
                "db_path": str(self.cache.db_path),
                "serialization": "pickle",  # Added to show we're using pickle serialization
            }

            return stats

        except sqlite3.Error as e:
            if self.verbose:
                log(f"Error getting cache stats: {e}")
            return {"error": str(e)}

    def get_issue_types(self):
        """Get all available issue types for the project."""
        endpoint = "issuetype"
        return self._request("GET", endpoint, label="Fetching issue types")

    def get_priorities(self):
        """Get all available priorities."""
        endpoint = "priority"
        return self._request("GET", endpoint, label="Fetching priorities")

    def get_users(self):
        """Get all available users."""
        return self._request(
            "GET", "user/search", params={"maxResults": 1000}, label="Fetching users"
        )

    def get_labels(self):
        """Get all available labels."""
        # Search for issues with labels and extract unique labels
        jql = "project = " + self.config.get("jira_project")
        response = self._request(
            "GET",
            "search",
            params={"jql": jql, "maxResults": 1000, "fields": "labels"},
            label="Fetching labels",
        )

        # Extract unique labels from all issues
        labels = set()
        for issue in response.get("issues", []):
            labels.update(issue.get("fields", {}).get("labels", []))

        return sorted(list(labels))

    def get_components(self):
        """Get all available components."""
        # Search for issues with components and extract unique components
        jql = "project = " + self.config.get("jira_project")
        response = self._request(
            "GET",
            "search",
            params={"jql": jql, "maxResults": 1000, "fields": "components"},
            label="Fetching components",
        )

        # Extract unique components from all issues
        components = set()
        for issue in response.get("issues", []):
            issue_components = issue.get("fields", {}).get("components", [])
            for component in issue_components:
                components.add(component.get("name", ""))

        return sorted(list(filter(None, components)))
