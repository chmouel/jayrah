"""Refactored Jira HTTP API client with clean separation of concerns."""

import sqlite3
from typing import Any, Dict, List, Optional

import click

from ..utils import cache, log
from . import auth, formatters, request_handler


class JiraHTTP:
    """Main Jira API client with version-agnostic interface."""

    def __init__(
        self,
        config: Dict[str, Any],
        api_version: str = "2",
        auth_method: Optional[str] = None,
    ):
        """Initialize the Jira client.

        Args:
            config: Configuration dictionary with Jira settings
            api_version: Jira API version ("2" or "3")
            auth_method: Authentication method ("basic" or "bearer")
        """
        self.config = config
        self.api_version = api_version
        self.verbose = config.get("verbose", False)

        # Set up base URL
        server = config.get("jira_server")
        if not server:
            raise click.ClickException("jira_server not configured")

        self.base_url = f"{server}/rest/api/{api_version}"

        # Set up authentication
        if not auth_method:
            # Default to Bearer for v2, Basic for v3
            auth_method = "bearer" if api_version == "2" else "basic"

        self.auth_method = auth_method  # Store for backward compatibility
        self.authenticator = auth.create_authenticator(config, auth_method)
        self.formatter = formatters.create_formatter(api_version)

        # Set up headers
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self.headers.update(self.authenticator.get_headers())

        # Set up cache and request handler
        cache_instance = cache.JiraCache(config)
        self.request_handler = request_handler.JiraRequestHandler(
            base_url=self.base_url,
            headers=self.headers,
            cache_instance=cache_instance,
            verbose=self.verbose,
            insecure=config.get("insecure", False),
        )

        if self.verbose:
            log(
                f"Initialized JiraClient: server={server}, api_version={api_version}, "
                f"auth_method={auth_method}, project={config.get('jira_component')}, "
                f"no_cache={config.get('no_cache')}, insecure={config.get('insecure', False)}"
            )

    @property
    def cache(self):
        """Backward compatibility property to access the cache instance."""
        return self.request_handler.cache

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        jeez: Optional[Dict[str, Any]] = None,
        label: Optional[str] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """Backward compatibility method that delegates to request_handler.request().

        This method maintains the same interface as the original JiraHTTP class
        for compatibility with existing tests and code.
        """
        return self.request_handler.request(
            method=method,
            endpoint=endpoint,
            params=params,
            json_data=jeez,
            label=label,
            use_cache=use_cache,
        )

    def search_issues(
        self,
        jql: str,
        start_at: int = 0,
        max_results: int = 50,
        fields: Optional[List[str]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """Search for issues using JQL."""
        params = {"jql": jql, "startAt": start_at, "maxResults": max_results}
        if fields:
            params["fields"] = ",".join(fields)

        if self.verbose:
            log(
                f"Searching issues with JQL: '{click.style(jql, fg='cyan')}' "
                f"Params: '{click.style(params.get('fields', ''), fg='cyan')}'",
            )
            log(f"Start at: {start_at}, Max results: {max_results}")

        label = "✨ Fetching Jira issues"
        if start_at != 0:
            label += f" from {start_at} to {start_at + max_results}"

        return self._request(
            "GET", "search", params=params, label=label, use_cache=use_cache
        )

    def create_issue(
        self,
        issuetype: str,
        summary: str,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        labels: Optional[List[str]] = None,
        components: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new issue."""
        payload = self._build_create_issue_payload(
            issuetype,
            summary,
            description,
            priority,
            assignee,
            labels,
            components or [],
        )
        return self._request("POST", "issue", jeez=payload)

    def _build_create_issue_payload(
        self,
        issuetype: str,
        summary: str,
        description: Optional[str],
        priority: Optional[str],
        assignee: Optional[str],
        labels: Optional[List[str]],
        components: List[str],
    ) -> Dict[str, Any]:
        """Build the payload for creating an issue."""
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
            payload["fields"]["description"] = self.formatter.format_description(
                description
            )

        if priority:
            payload["fields"]["priority"] = {"name": priority}

        if assignee:
            payload["fields"]["assignee"] = self.formatter.format_assignee(assignee)

        if labels:
            payload["fields"]["labels"] = labels

        return payload

    def get_issue(
        self, issue_key: str, fields: Optional[List[str]] = None, use_cache: bool = True
    ) -> Dict[str, Any]:
        """Get a specific issue by key."""
        params = {}
        if fields:
            params["fields"] = ",".join(fields)

        if self.verbose:
            log(f"Getting issue: {issue_key} with fields: {fields}")

        return self._request(
            "GET", f"issue/{issue_key}", params=params, use_cache=use_cache
        )

    def update_issue(self, issue_key: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing issue's fields."""
        # Handle description formatting if present
        if "description" in fields and isinstance(fields["description"], str):
            fields = fields.copy()  # Don't modify the original dict
            fields["description"] = self.formatter.format_description(
                fields["description"]
            )

        payload = {"fields": fields}

        if self.verbose:
            log(f"Updating issue: {issue_key}")
            log(f"Fields to update: {list(fields.keys())}")

        return self._request("PUT", f"issue/{issue_key}", jeez=payload)

    def get_transitions(self, issue_key: str) -> Dict[str, Any]:
        """Get available transitions for an issue."""
        return self._request(
            "GET", f"issue/{issue_key}/transitions", label="All transitions"
        )

    def transition_issue(self, issue_key: str, transition_id: str) -> Dict[str, Any]:
        """Transition an issue to a new status."""
        payload = {"transition": {"id": transition_id}}

        if self.verbose:
            log(f"Transitioning issue: {issue_key} with transition ID: {transition_id}")

        return self._request("POST", f"issue/{issue_key}/transitions", jeez=payload)

    def add_comment(self, issue_key: str, comment: str) -> Dict[str, Any]:
        """Add a comment to an issue."""
        payload = self.formatter.format_comment(comment)

        if self.verbose:
            log(f"Adding comment to issue: {issue_key}")

        return self._request("POST", f"issue/{issue_key}/comment", jeez=payload)

    def get_issue_types(self) -> Dict[str, Any]:
        """Get all available issue types for the project."""
        endpoint = self.formatter.get_issue_types_endpoint()
        return self._request("GET", endpoint, label="Fetching issue types")

    def get_priorities(self) -> Dict[str, Any]:
        """Get all available priorities."""
        return self._request("GET", "priority", label="Fetching priorities")

    def get_users(self) -> Dict[str, Any]:
        """Get all available users."""
        return self._request(
            "GET", "user/search", params={"maxResults": 1000}, label="Fetching users"
        )

    def get_labels(self, max_results: int = 100) -> List[str]:
        """Get all available labels."""
        jql = f"project = {self.config.get('jira_project')}"
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

    def get_components(self, max_results: int = 100) -> List[str]:
        """Get all available components."""
        jql = f"project = {self.config.get('jira_project')}"
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

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the SQLite cache usage."""
        if self.verbose:
            log("Fetching cache statistics...")

        try:
            # Connect to the SQLite database
            conn = self.request_handler.cache.get_connection()
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
                "cache_ttl": self.request_handler.cache.cache_ttl,
                "db_path": str(self.request_handler.cache.db_path),
                "serialization": "pickle",
            }

            return stats

        except sqlite3.Error as e:
            if self.verbose:
                log(f"Error getting cache stats: {e}")
            return {"error": str(e)}


# Backward compatibility alias
JiraHTTP = JiraHTTP
