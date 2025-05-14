"""UI components for the label management functionality."""

import subprocess
import tempfile

import click

from jayrah import utils
from jayrah.label_service import LabelService
from . import defaults


class LabelUI:
    """UI for label management."""

    def __init__(self, jira_client, config):
        """
        Initialize the label UI.

        Args:
            jira_client: The JiraHTTP client instance
            config: Configuration dictionary
        """
        self.config = config
        self.service = LabelService(jira_client, config)
        self.verbose = config.get("verbose", False)

    def manage_labels_menu(self, issue):
        """
        Show the main label management menu for an issue.

        Args:
            issue: The issue data dictionary

        Returns:
            bool: True if operation was successful, False otherwise
        """
        issue_key = issue["key"]
        current_labels = issue["fields"].get("labels", [])

        if self.verbose:
            utils.log(
                f"Managing labels for issue {issue_key}",
                "DEBUG",
                verbose_only=True,
                verbose=self.verbose,
            )

        # Get the available labels
        available_labels = self.service.get_available_labels()

        # Format current labels for display
        current_labels_text = ", ".join(current_labels) if current_labels else "None"

        # Create menu options
        with tempfile.NamedTemporaryFile("w+") as tmp:
            tmp.write(f"|Label management for {issue_key}\n")

            # Add option
            tmp.write(f"add|➕ Add a new label (Current: {current_labels_text})\n")

            # Remove option (only if there are labels to remove)
            if current_labels:
                tmp.write("remove|➖ Remove an existing label\n")

            # Refresh option to update labels from server
            tmp.write("refresh|🔄 Refresh label list from server\n")

            tmp.flush()

            # Run the fzf selection
            result = self._run_fzf_menu(tmp.name, issue_key)
            if not result:
                return False

            action = result.strip().split("|")[0]

            if action == "add":
                success = self.add_label_menu(
                    issue_key, current_labels, available_labels
                )
                if success:
                    # Get the updated issue with fresh labels (bypass cache)
                    updated_issue = self.service.jira.get_issue(
                        issue_key, fields=["labels"], use_cache=False
                    )
                    return self.manage_labels_menu(updated_issue)
                return success
            elif action == "remove":
                success = self.remove_label_menu(issue_key, current_labels)
                if success:
                    # Get the updated issue with fresh labels (bypass cache)
                    updated_issue = self.service.jira.get_issue(
                        issue_key, fields=["labels"], use_cache=False
                    )
                    return self.manage_labels_menu(updated_issue)
                return success
            elif action == "refresh":
                # Clear the cache and reload labels
                self.service.clear_label_cache()
                self.service.get_available_labels(force_refresh=True)
                # Get the updated issue with fresh labels (bypass cache)
                updated_issue = self.service.jira.get_issue(
                    issue_key, fields=["labels"], use_cache=False
                )
                return self.manage_labels_menu(updated_issue)

        return False

    def add_label_menu(self, issue_key, current_labels, available_labels):
        """
        Show menu for adding a label to an issue.

        Args:
            issue_key: The Jira issue key
            current_labels: List of current labels on the issue
            available_labels: List of available labels

        Returns:
            bool: True if the label was added successfully, False otherwise
        """
        with tempfile.NamedTemporaryFile("w+") as tmp:
            tmp.write(f"|Select a label to add to {issue_key}\n")

            # Add option for custom label
            tmp.write("custom|➕ Enter a custom label\n")

            # Filter out labels that are already on the issue
            available_new_labels = [
                label for label in available_labels if label not in current_labels
            ]

            # Sort alphabetically
            available_new_labels.sort()

            # Add available labels
            for label in available_new_labels:
                tmp.write(f"{label}|{label}\n")

            # Add message if no available labels are found
            if not available_new_labels:
                tmp.write("info|No suggested labels available - use custom option\n")

            tmp.flush()

            # Run the fzf selection
            result = self._run_fzf_menu(tmp.name, issue_key)
            if not result:
                return False

            selected = result.strip().split("|")[0]

            # Skip info line
            if selected == "info":
                return False

            # Handle custom label entry
            if selected == "custom":
                selected = click.prompt("Enter new label")
                if not selected or selected.strip() == "":
                    click.secho("No label entered", fg="yellow", err=True)
                    return False

            # Add the label
            success = self.service.add_label(issue_key, selected)
            if success:
                click.secho(
                    f"✅ Label '{selected}' added to {issue_key}",
                    fg="green",
                    err=True,
                )
            return success

    def remove_label_menu(self, issue_key, current_labels):
        """
        Show menu for removing a label from an issue.

        Args:
            issue_key: The Jira issue key
            current_labels: List of current labels on the issue

        Returns:
            bool: True if the label was removed successfully, False otherwise
        """
        if not current_labels:
            click.secho("No labels to remove", fg="yellow", err=True)
            return False

        with tempfile.NamedTemporaryFile("w+") as tmp:
            tmp.write(f"|Select a label to remove from {issue_key}\n")

            # Add current labels
            for label in current_labels:
                tmp.write(f"{label}|{label}\n")

            tmp.flush()

            # Run the fzf selection
            result = self._run_fzf_menu(tmp.name, issue_key)
            if not result:
                return False

            selected = result.strip().split("|")[0]

            # Remove the label
            success = self.service.remove_label(issue_key, selected)
            if success:
                click.secho(
                    f"✅ Label '{selected}' removed from {issue_key}",
                    fg="green",
                    err=True,
                )
            return success

    def _run_fzf_menu(self, tmp_file_path, issue_key):
        """
        Run a fuzzy finder menu from a temporary file.

        Args:
            tmp_file_path: Path to the temporary file with menu options
            issue_key: The issue key for preview command

        Returns:
            str: The selected line or None if cancelled
        """
        preview_cmd = f"{self.config.get('jayrah_path')} issue view '{issue_key}'"
        fzf_cmd = [
            "fzf",
            "-d",
            "|",
            "--ansi",
            "--header-lines=1",
            "--with-nth=2..",
            "--accept-nth=1",
            "--reverse",
            "--preview",
            preview_cmd,
            "--preview-window",
            "bottom:80%:wrap:hidden",
        ]
        fzf_cmd += defaults.FZFOPTS

        try:
            with open(tmp_file_path, encoding="utf-8") as tmp_file:
                result = subprocess.run(
                    fzf_cmd,
                    stdin=tmp_file,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            if not result.stdout:
                return None

            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            click.secho(f"Error occurred: {e}", fg="red", err=True)
            return None
