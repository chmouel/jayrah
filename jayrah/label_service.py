"""Label service for managing Jira issue labels."""

import click


class LabelService:
    """Service class for managing labels in Jira issues."""

    def __init__(self, jira_client, config):
        """Initialize the label service.

        Args:
            jira_client: The JiraHTTP client instance
            config: Configuration dictionary
        """
        self.jira = jira_client
        self.config = config
        self.verbose = config.get("verbose", False)

    def get_available_labels(self, force_refresh=False):
        """Get all available labels from Jira, using cache if available.

        Args:
            force_refresh: Force refreshing labels from API instead of using cache

        Returns:
            list: List of available labels
        """
        # Try to get available labels from cache first unless force refresh is requested
        if not force_refresh:
            cached_labels = self.jira.cache.get_direct("jayrah_labels")
            if cached_labels and not self.config.get("no_cache"):
                if self.verbose:
                    click.echo(f"Using {len(cached_labels)} cached labels", err=True)
                return cached_labels

        # If we get here, we need to fetch labels from API
        if self.verbose:
            click.echo("Fetching labels from Jira API", err=True)

        try:
            available_labels = self.jira.get_labels()
            # Cache the labels
            self.jira.cache.set_direct("jayrah_labels", available_labels)

            if self.verbose:
                click.echo(f"Cached {len(available_labels)} labels", err=True)

            return available_labels
        except Exception as e:
            if self.verbose:
                click.secho(f"Error fetching labels: {e}", fg="red", err=True)
            return []

    def get_issue_labels(self, issue_key):
        """Get the current labels for an issue.

        Args:
            issue_key: The Jira issue key

        Returns:
            list: List of labels currently applied to the issue
        """
        try:
            issue = self.jira.get_issue(issue_key, fields=["labels"])
            return issue["fields"].get("labels", [])
        except Exception as e:
            if self.verbose:
                click.secho(f"Error fetching issue labels: {e}", fg="red", err=True)
            return []

    def add_label(self, issue_key, label):
        """Add a label to an issue.

        Args:
            issue_key: The Jira issue key
            label: The label to add

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self.verbose:
                click.echo(f"Adding label '{label}' to {issue_key}", err=True)

            result = self.jira.add_label(issue_key, label)

            # Refresh the issue in cache
            if result:
                self._refresh_issue_cache(issue_key)

            return bool(result)
        except Exception as e:
            if self.verbose:
                click.secho(f"Error adding label: {e}", fg="red", err=True)
            return False

    def remove_label(self, issue_key, label):
        """Remove a label from an issue.

        Args:
            issue_key: The Jira issue key
            label: The label to remove

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self.verbose:
                click.echo(f"Removing label '{label}' from {issue_key}", err=True)

            result = self.jira.remove_label(issue_key, label)

            # Refresh the issue in cache
            if result:
                self._refresh_issue_cache(issue_key)

            return bool(result)
        except Exception as e:
            if self.verbose:
                click.secho(f"Error removing label: {e}", fg="red", err=True)
            return False

    def clear_label_cache(self):
        """Clear the cached labels."""
        self.jira.cache.set_direct("jayrah_labels", None)
        if self.verbose:
            click.echo("Label cache cleared", err=True)

    def _refresh_issue_cache(self, issue_key):
        """
        Refresh the issue in cache by forcing a new fetch from the API.

        Args:
            issue_key: The Jira issue key
        """
        if self.verbose:
            click.echo(f"Refreshing issue {issue_key} in cache", err=True)

        # Force a fresh fetch of the issue with all fields
        try:
            # Get the issue to refresh the cache
            self.jira.get_issue(issue_key, use_cache=False)
        except Exception as e:
            if self.verbose:
                click.secho(f"Error refreshing issue in cache: {e}", fg="red", err=True)
