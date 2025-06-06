"""Jira HTTP API client and related utilities for interacting with Jira issues, users, and metadata.

This module provides a client for interacting with Jira's REST API (both v2 and v3).
The JiraHTTP class handles authentication, request/response formatting, and caching.
Supports both Bearer token and Basic authentication methods, automatically selecting
the appropriate method based on the API version.

Authentication:
- API v2 uses Bearer token authentication by default
- API v3 uses Basic authentication by default
- Authentication method can be explicitly set via the auth_method parameter

Examples:
    # Create a client with API v2 (Bearer token auth by default)
    client_v2 = JiraHTTP(config, api_version="2")

    # Create a client with API v3 (Basic auth by default)
    client_v3 = JiraHTTP(config, api_version="3")

    # Override the default authentication method
    client_v3_bearer = JiraHTTP(config, api_version="3", auth_method="bearer")
"""

import base64
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
    def __init__(self, config, api_version="2", auth_method=None):
        """Initialize the Jira HTTP client.

        Args:
            config (dict): Configuration dictionary with Jira settings
            api_version (str): Jira API version to use. Default is "2". Use "3" for the newer API.
            auth_method (str, optional): Authentication method to use.
                Options are "basic" or "bearer". If None, will use "bearer" for v2 and "basic" for v3.
        """
        self.config = config
        server = self.config.get("jira_server")
        self.api_version = api_version
        self.base_url = f"{server}/rest/api/{self.api_version}"
        self.cache = cache.JiraCache(config)
        self.verbose = self.config.get("verbose", False)
        self.insecure = self.config.get("insecure", False)

        # Determine authentication method based on API version if not explicitly specified
        if auth_method is None:
            # Default to basic auth for v3, bearer for v2
            self.auth_method = "basic" if str(self.api_version) == "3" else "bearer"
        else:
            self.auth_method = auth_method.lower()

        if self.verbose:
            log(
                f"Initialized JiraHTTP: server={server}, api_version={self.api_version}, auth_method={self.auth_method}, project={self.config.get('jira_component')}, no_cache={self.config.get('no_cache')}, insecure={self.insecure}",
            )

        # Set up headers based on authentication method
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Apply the appropriate authentication header
        if self.auth_method == "basic":
            # Basic authentication: base64(username:password)
            username = self.config.get("jira_user")
            password = self.config.get("jira_password")
            if not username or not password:
                raise click.ClickException(
                    "Basic authentication requires both jira_user and jira_password in config"
                )

            # Create the basic auth header
            auth_string = f"{username}:{password}"
            encoded_auth = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
            self.headers["Authorization"] = f"Basic {encoded_auth}"
        else:
            # Bearer token authentication (default for v2)
            self.headers["Authorization"] = f"Bearer {self.config.get('jira_password')}"

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
                if value.startswith("Bearer"):
                    value = "Bearer ${JIRA_API_TOKEN}"  # Mask the bearer token
                elif value.startswith("Basic"):
                    value = (
                        "Basic ${JIRA_BASIC_AUTH}"  # Mask the basic auth credentials
                    )
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
                try:
                    with urllib.request.urlopen(request, data=data) as response:
                        status_code = response.status
                        response_text = response.read().decode("utf-8")
                        response_data = (
                            json.loads(response_text) if response_text else {}
                        )
                except urllib.error.HTTPError as e:
                    log(f"HTTP error occurred: {e}")
                    raise click.ClickException("HTTP error: {e}") from e
                except json.JSONDecodeError as e:
                    log(f"Failed to parse JSON response: {e}")
                    log(f"Response text: {response_text[1:100]}")
                    raise click.ClickException("Failed to parse JSON response") from e
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
            raise click.ClickException(f"HTTP error: {e}") from e
        except urllib.error.URLError as e:
            log(f"URL error occurred: {e}")
            raise click.ClickException(f"URL error: {e}") from e

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
        components=None,
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
            components (list): List of components.
        Returns:
            dict: JSON response containing the created issue.
        """
        if components is None:
            components = []
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
            # Handle description differently based on API version
            if self.api_version == "3":
                # In API v3, rich text descriptions use Atlassian Document Format (ADF)
                if isinstance(description, dict) and "content" in description:
                    # If already in ADF format, use as is
                    payload["fields"]["description"] = description
                else:
                    # Simple conversion to ADF format
                    payload["fields"]["description"] = self._convert_to_adf(description)
            else:
                # API v2 uses plain text or wiki markup
                payload["fields"]["description"] = description
        if priority:
            payload["fields"]["priority"] = {"name": priority}
        if assignee:
            # Handle assignee differently based on API version
            if self.api_version == "3":
                # In API v3, assignee needs an accountId rather than username
                # But fall back to username if that's what we have
                if "@" in assignee:  # Looks like an email, likely an accountId
                    payload["fields"]["assignee"] = {"accountId": assignee}
                else:
                    payload["fields"]["assignee"] = {"name": assignee}
            else:
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

        ret = self._request("GET", endpoint, params=params, use_cache=use_cache)
        return ret

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

        # Handle API version-specific field formats
        if (
            self.api_version == "3"
            and "description" in fields
            and isinstance(fields["description"], str)
        ):
            # Convert plain text description to ADF format for API v3
            fields["description"] = self._convert_to_adf(fields["description"])

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
            conn = self.cache.get_connection()
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
        # Different endpoint for API v2 vs v3
        if self.api_version == "3":
            endpoint = "issuetypes"
        else:
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

    def get_labels(self, max_results=100):
        """Get all available labels."""
        # Search for issues with labels and extract unique labels
        jql = "project = " + self.config.get("jira_project")
        response = self._request(
            "GET",
            "search",
            params={"jql": jql, "maxResults": max_results, "fields": "labels"},
        )

        # Extract unique labels from all issues
        labels = set()
        for issue in response.get("issues", []):
            labels.update(issue.get("fields", {}).get("labels", []))

        return sorted(list(labels))

    def get_components(self, max_results=100):
        """Get all available components."""
        # Search for issues with components and extract unique components
        jql = "project = " + self.config.get("jira_project")
        response = self._request(
            "GET",
            "search",
            params={"jql": jql, "maxResults": max_results, "fields": "components"},
        )

        # Extract unique components from all issues
        components = set()
        for issue in response.get("issues", []):
            issue_components = issue.get("fields", {}).get("components", [])
            for component in issue_components:
                components.add(component.get("name", ""))

        return sorted(list(filter(None, components)))

    def _convert_to_adf(self, text):
        """
        Convert plain text or basic markup to Atlassian Document Format (ADF).

        This is a simple conversion for API v3 compatibility. For advanced formatting,
        a more sophisticated parser would be needed.

        Args:
            text (str): Plain text or basic markup

        Returns:
            dict: Text in ADF format
        """
        # Simple conversion to ADF format
        return {
            "version": 1,
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": text}]}
            ],
        }

    def _is_adf_format(self, obj):
        """
        Check if an object is already in Atlassian Document Format.

        Args:
            obj: Object to check

        Returns:
            bool: True if the object appears to be in ADF format
        """
        return (
            isinstance(obj, dict)
            and obj.get("version") is not None
            and obj.get("type") == "doc"
            and isinstance(obj.get("content"), list)
        )

    def add_comment(self, issue_key, comment):
        """
        Add a comment to an issue.

        Args:
            issue_key (str): The issue key (e.g., 'PROJ-123')
            comment (str or dict): Comment text or ADF formatted comment

        Returns:
            dict: JSON response containing the created comment
        """
        endpoint = f"issue/{issue_key}/comment"

        # Handle API version-specific comment format
        if self.api_version == "3":
            # In API v3, comments use Atlassian Document Format
            if not self._is_adf_format(comment):
                payload = self._convert_to_adf(comment)
            else:
                payload = comment
        else:
            # API v2 uses plain text
            payload = {"body": comment}

        if self.verbose:
            log(f"Adding comment to issue: {issue_key}")

        return self._request("POST", endpoint, jeez=payload)
