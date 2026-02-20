"""Refactored Jira HTTP API client with clean separation of concerns."""

import sqlite3
import time
from typing import Any

import click

from ..utils import cache, log
from . import auth, exceptions, formatters, request_handler


class JiraHTTP:
    """Main Jira API client with version-agnostic interface."""

    def __init__(
        self,
        config: dict[str, Any],
        api_version: str = "2",
        auth_method: str | None = None,
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
        server = server.rstrip("/")

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
            quiet=config.get("quiet", False),
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
        params: dict[str, Any] | None = None,
        jeez: dict[str, Any] | None = None,
        label: str | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
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

    def _search_endpoint(self) -> str:
        """Return the Jira search endpoint for the configured API version."""
        if self.api_version == "3":
            return "search/jql"
        return "search"

    def search_issues(
        self,
        jql: str,
        start_at: int = 0,
        max_results: int = 50,
        fields: list[str] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
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
            "GET",
            self._search_endpoint(),
            params=params,
            label=label,
            use_cache=use_cache,
        )

    def get_fields(self) -> Any:
        """Get all available fields."""
        return self._request("GET", "field", label="Fetching fields")

    def create_issue(
        self,
        issuetype: str,
        summary: str,
        description: str | None = None,
        priority: str | None = None,
        assignee: str | None = None,
        labels: list[str] | None = None,
        components: list[str] | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new issue."""
        payload = self._build_create_issue_payload(
            issuetype,
            summary,
            description,
            priority,
            assignee,
            labels,
            components or [],
            extra_fields=extra_fields,
        )
        return self._request("POST", "issue", jeez=payload)

    def _build_create_issue_payload(
        self,
        issuetype: str,
        summary: str,
        description: str | None,
        priority: str | None,
        assignee: str | None,
        labels: list[str] | None,
        components: list[str],
        extra_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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

        if extra_fields:
            for key, value in extra_fields.items():
                payload["fields"][key] = value

        return payload

    def get_issue(
        self, issue_key: str, fields: list[str] | None = None, use_cache: bool = True
    ) -> dict[str, Any]:
        """Get a specific issue by key."""
        params = {}
        if fields:
            params["fields"] = ",".join(fields)

        if self.verbose:
            log(f"Getting issue: {issue_key} with fields: {fields}")

        return self._request(
            "GET", f"issue/{issue_key}", params=params, use_cache=use_cache
        )

    def update_issue(self, issue_key: str, fields: dict[str, Any]) -> dict[str, Any]:
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

    def get_transitions(self, issue_key: str) -> dict[str, Any]:
        """Get available transitions for an issue."""
        return self._request(
            "GET", f"issue/{issue_key}/transitions", label="All transitions"
        )

    def transition_issue(self, issue_key: str, transition_id: str) -> dict[str, Any]:
        """Transition an issue to a new status."""
        payload = {"transition": {"id": transition_id}}

        if self.verbose:
            log(f"Transitioning issue: {issue_key} with transition ID: {transition_id}")

        return self._request("POST", f"issue/{issue_key}/transitions", jeez=payload)

    def add_comment(self, issue_key: str, comment: str) -> dict[str, Any]:
        """Add a comment to an issue."""
        payload = self.formatter.format_comment(comment)

        if self.verbose:
            log(f"Adding comment to issue: {issue_key}")

        return self._request("POST", f"issue/{issue_key}/comment", jeez=payload)

    def get_issue_types(self, use_cache: bool = True) -> dict[str, str]:
        """Get all available issue types for the project.

        Args:
            use_cache: Whether to use cached results (default: True)

        Returns:
            Dictionary mapping issue type names to IDs
        """
        project_key = self.config.get("jira_project")
        ret: dict[str, str] = {}
        errors = []  # Track all attempted endpoints and their errors

        # If no project configured, use global endpoint
        if not project_key:
            if self.verbose:
                log("No project key configured, fetching global issue types")
            try:
                response = self._request(
                    "GET",
                    "issuetype",
                    label="Fetching issue types",
                    use_cache=use_cache,
                )
                if isinstance(response, list):
                    for it in response:
                        if isinstance(it, dict):
                            name = it.get("name")
                            iid = it.get("id")
                            if name and iid:
                                ret[str(name)] = str(iid)
                if self.verbose:
                    log(f"Found {len(ret)} global issue types")
                return ret
            except Exception as e:
                if self.verbose:
                    log(f"Failed to fetch global issue types: {e}")
                return ret

        # Try endpoints in order of preference
        endpoints = [
            {
                "name": "Modern Jira DC (8.14+)",
                "endpoint": f"issue/createmeta/{project_key}/issuetypes",
                "label": "Fetching issue types (modern)",
                "parser": self._parse_modern_issue_types,
            },
            {
                "name": "Legacy/Cloud createmeta",
                "endpoint": self.formatter.get_issue_types_endpoint(project_key),
                "label": "Fetching issue types",
                "parser": self._parse_legacy_issue_types,
            },
            {
                "name": "Global fallback",
                "endpoint": "issuetype",
                "label": "Fetching issue types (fallback)",
                "parser": self._parse_global_issue_types,
            },
        ]

        for i, ep_config in enumerate(endpoints):
            try:
                if self.verbose:
                    log(
                        f"Trying endpoint: {ep_config['name']} - {ep_config['endpoint']}"
                    )

                response = self._request(
                    "GET",
                    ep_config["endpoint"],
                    label=ep_config["label"],
                    use_cache=use_cache,
                )

                # Parse response using appropriate parser
                ret = ep_config["parser"](response, project_key)

                if ret:
                    if self.verbose:
                        log(
                            f"✓ Success with {ep_config['name']}: found {len(ret)} issue types"
                        )
                    return ret

                errors.append(f"{ep_config['name']}: No issue types found in response")
                if self.verbose:
                    log(f"No issue types found in {ep_config['name']} response")

            except (
                exceptions.JiraAuthenticationError,
                exceptions.JiraAuthorizationError,
                exceptions.JiraRateLimitError,
            ) as e:
                # Don't retry on auth or rate limit errors
                errors.append(f"{ep_config['name']}: {e!s}")
                if self.verbose:
                    log(
                        f"✗ {ep_config['name']} failed with critical error: {type(e).__name__}"
                    )
                raise

            except exceptions.JiraNotFoundError:
                errors.append(f"{ep_config['name']}: Resource not found (404)")
                if self.verbose:
                    log(f"✗ {ep_config['name']} not found (404)")
                    if "project" in ep_config["endpoint"].lower() and project_key:
                        log(
                            f"  → Check that project '{project_key}' exists and is accessible"
                        )

            except Exception as e:
                errors.append(f"{ep_config['name']}: {type(e).__name__}: {e!s}")
                if self.verbose:
                    log(f"✗ {ep_config['name']} failed: {e}")

            # Add delay between attempts to avoid rate limiting (except after last attempt)
            if i < len(endpoints) - 1:
                if self.verbose:
                    log("Waiting 0.5s before next attempt...")
                time.sleep(0.5)

        # If we got here, all endpoints failed
        if self.verbose:
            log("All endpoints failed to fetch issue types")
            for error in errors:
                log(f"  - {error}")

        return ret

    def _parse_modern_issue_types(
        self, response: dict[str, Any], project_key: str
    ) -> dict[str, str]:
        """Parse issue types from modern Jira DC endpoint."""
        ret: dict[str, str] = {}
        if isinstance(response, dict) and "issueTypes" in response:
            for it in response["issueTypes"]:
                if isinstance(it, dict):
                    name = it.get("name")
                    iid = it.get("id")
                    if name and iid:
                        ret[str(name)] = str(iid)
        return ret

    def _parse_legacy_issue_types(
        self, response: dict[str, Any], project_key: str
    ) -> dict[str, str]:
        """Parse issue types from legacy/Cloud createmeta endpoint."""
        ret: dict[str, str] = {}
        if isinstance(response, list):
            # Some endpoints return a list directly
            for it in response:
                if isinstance(it, dict):
                    name = it.get("name")
                    iid = it.get("id")
                    if name and iid:
                        ret[str(name)] = str(iid)
        elif isinstance(response, dict):
            # createmeta returns projects array
            projects = response.get("projects", [])
            for project in projects:
                if isinstance(project, dict) and project.get("key") == project_key:
                    for it in project.get("issuetypes", []):
                        if isinstance(it, dict):
                            name = it.get("name")
                            iid = it.get("id")
                            if name and iid:
                                ret[str(name)] = str(iid)
        return ret

    def _parse_global_issue_types(
        self, response: dict[str, Any], project_key: str
    ) -> dict[str, str]:
        """Parse issue types from global issuetype endpoint."""
        ret: dict[str, str] = {}
        if isinstance(response, list):
            for it in response:
                if isinstance(it, dict):
                    name = it.get("name")
                    iid = it.get("id")
                    if name and iid:
                        ret[str(name)] = str(iid)
        return ret

    def get_project_priorities(
        self,
        issuetype: str | None = None,
        issue_types_cache: dict[str, str] | None = None,
    ) -> list[str]:
        """Get all available priorities for the project, optionally filtered by issue type.

        Args:
            issuetype: Filter priorities by issue type name
            issue_types_cache: Pre-fetched issue types dict to avoid duplicate API calls

        Returns:
            List of priority names
        """
        project_key = self.config.get("jira_project")
        if not project_key:
            return self._get_global_priorities()

        priorities_set = set()

        # Try modern Jira DC endpoint first if we have an issue type name
        if issuetype:
            try:
                # Use cached issue types or fetch with caching enabled
                if issue_types_cache is None:
                    issue_types_cache = self.get_issue_types(use_cache=True)
                it_id = issue_types_cache.get(issuetype)
                if it_id:
                    endpoint = f"issue/createmeta/{project_key}/issuetypes/{it_id}"
                    response = self._request(
                        "GET", endpoint, label=f"Fetching {issuetype} metadata (modern)"
                    )
                    if isinstance(response, dict) and "values" in response:
                        for field in response["values"]:
                            if (
                                isinstance(field, dict)
                                and field.get("fieldId") == "priority"
                            ):
                                for v in field.get("allowedValues", []):
                                    if isinstance(v, dict) and v.get("name"):
                                        priorities_set.add(str(v.get("name")))
                        if priorities_set:
                            return sorted(priorities_set)
            except Exception:
                pass

        # Try legacy/Cloud createmeta endpoint
        params: dict[str, Any] = {
            "projectKeys": project_key,
            "expand": "projects.issuetypes.fields",
        }
        if issuetype:
            params["issuetypeNames"] = issuetype

        try:
            meta = self._request(
                "GET",
                "issue/createmeta",
                params=params,
                label="Fetching project metadata",
            )

            if isinstance(meta, dict):
                projects = meta.get("projects", [])
                for project in projects:
                    if isinstance(project, dict) and project.get("key") == project_key:
                        issuetypes = project.get("issuetypes", [])
                        for it in issuetypes:
                            if isinstance(it, dict):
                                fields = it.get("fields", {})
                                priority_field = fields.get("priority", {})
                                allowed_values = priority_field.get("allowedValues", [])
                                for v in allowed_values:
                                    if isinstance(v, dict) and v.get("name"):
                                        priorities_set.add(str(v.get("name")))

            if priorities_set:
                return sorted(priorities_set)
        except Exception:
            pass

        return self._get_global_priorities()

    def _get_global_priorities(self) -> list[str]:
        """Get global priorities as a fallback."""
        try:
            priorities = self.get_priorities()
            if isinstance(priorities, list):
                return [
                    str(p.get("name"))
                    for p in priorities
                    if isinstance(p, dict) and p.get("name")
                ]
        except Exception:
            pass
        return []

    def get_priorities(self) -> dict[str, Any]:
        """Get all available priorities."""
        return self._request("GET", "priority", label="Fetching priorities")

    def get_users(self) -> dict[str, Any]:
        """Get all available users."""
        return self._request(
            "GET", "user/search", params={"maxResults": 1000}, label="Fetching users"
        )

    def get_labels(self, max_results: int = 100) -> list[str]:
        """Get all available labels."""
        jql = f"project = {self.config.get('jira_project')}"
        response = self._request(
            "GET",
            self._search_endpoint(),
            params={"jql": jql, "maxResults": max_results, "fields": "labels"},
        )

        # Extract unique labels from all issues
        labels = set()
        for issue in response.get("issues", []):
            labels.update(issue.get("fields", {}).get("labels", []))

        return sorted(labels)

    def get_components(self, max_results: int = 100) -> list[str]:
        """Get all available components."""
        jql = f"project = {self.config.get('jira_project')}"
        response = self._request(
            "GET",
            self._search_endpoint(),
            params={"jql": jql, "maxResults": max_results, "fields": "components"},
        )

        # Extract unique components from all issues
        components = set()
        for issue in response.get("issues", []):
            issue_components = issue.get("fields", {}).get("components", [])
            for component in issue_components:
                components.add(component.get("name", ""))

        return sorted(filter(None, components))

    def get_createmeta(self, project_key: str, issuetype_name: str) -> dict[str, Any]:
        """Get creation metadata for a specific project and issue type."""
        params = {
            "projectKeys": project_key,
            "issuetypeNames": issuetype_name,
            "expand": "projects.issuetypes.fields",
        }
        return self._request("GET", "issue/createmeta", params=params)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get statistics about the SQLite cache usage."""
        if self.verbose:
            log("Fetching cache statistics...")

        try:
            # Open a dedicated connection so we don't interfere with the
            # persistent one used by the cache.
            with sqlite3.connect(self.request_handler.cache.db_path) as conn:
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

            # Calculate additional stats
            size_mb = round(total_size / (1024 * 1024), 2) if total_size else 0

            return {
                "entries": total_entries,
                "size_bytes": total_size,
                "size_mb": size_mb,
                "oldest_entry": oldest_timestamp,
                "newest_entry": newest_timestamp,
                "cache_ttl": self.request_handler.cache.cache_ttl,
                "db_path": str(self.request_handler.cache.db_path),
                "serialization": "pickle",
            }

        except sqlite3.Error as e:
            if self.verbose:
                log(f"Error getting cache stats: {e}")
            return {"error": str(e)}
