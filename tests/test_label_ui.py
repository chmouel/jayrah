"""Unit tests for the label_ui module."""

import subprocess
from unittest.mock import MagicMock, patch

import click
import pytest

from jayrah.label_ui import LabelUI


class TestLabelUI:
    """Tests for the LabelUI class."""

    @pytest.fixture
    def mock_label_ui(self, mock_jira_client, sample_config):
        """Create a mock label UI instance."""
        with patch("jayrah.label_ui.LabelService") as mock_service:
            service_instance = MagicMock()
            mock_service.return_value = service_instance

            # Set jira client on the service
            service_instance.jira = mock_jira_client

            ui = LabelUI(mock_jira_client, sample_config)
            ui.service = service_instance
            yield ui

    @pytest.fixture
    def sample_issue(self):
        """Create a sample issue with labels."""
        return {
            "key": "TEST-123",
            "fields": {
                "summary": "Test issue",
                "labels": ["bug", "documentation", "frontend"],
            },
        }

    @pytest.fixture
    def empty_labels_issue(self):
        """Create a sample issue with no labels."""
        return {"key": "TEST-123", "fields": {"summary": "Test issue", "labels": []}}

    @patch("subprocess.run")
    def test_manage_labels_menu_add_label(self, mock_run, mock_label_ui, sample_issue):
        """Test the main label management menu with add label option."""
        # Setup subprocess.run mock to return an add action
        mock_process = MagicMock()
        mock_process.stdout = "add|Add a new label"
        mock_run.return_value = mock_process

        # Mock the add_label_menu to return success
        mock_label_ui.add_label_menu = MagicMock(return_value=True)

        # Mock available labels
        mock_label_ui.service.get_available_labels.return_value = [
            "bug",
            "documentation",
            "frontend",
            "backend",
            "ui",
        ]

        # Mock the updated issue after adding label
        updated_issue = {
            "key": "TEST-123",
            "fields": {
                "summary": "Test issue",
                "labels": ["bug", "documentation", "frontend", "backend"],
            },
        }
        mock_label_ui.service.jira.get_issue.return_value = updated_issue

        # Call the method
        result = mock_label_ui.manage_labels_menu(sample_issue)

        # Assertions
        assert result is True
        mock_label_ui.service.get_available_labels.assert_called_once()
        mock_label_ui.add_label_menu.assert_called_once()
        mock_label_ui.service.jira.get_issue.assert_called_once_with(
            "TEST-123", fields=["labels"]
        )

    @patch("subprocess.run")
    def test_manage_labels_menu_remove_label(
        self, mock_run, mock_label_ui, sample_issue
    ):
        """Test the main label management menu with remove label option."""
        # Setup subprocess.run mock to return a remove action
        mock_process = MagicMock()
        mock_process.stdout = "remove|Remove an existing label"
        mock_run.return_value = mock_process

        # Mock the remove_label_menu to return success
        mock_label_ui.remove_label_menu = MagicMock(return_value=True)

        # Mock available labels
        mock_label_ui.service.get_available_labels.return_value = [
            "bug",
            "documentation",
            "frontend",
            "backend",
            "ui",
        ]

        # Mock the updated issue after removing label
        updated_issue = {
            "key": "TEST-123",
            "fields": {"summary": "Test issue", "labels": ["bug", "documentation"]},
        }
        mock_label_ui.service.jira.get_issue.return_value = updated_issue

        # Call the method
        result = mock_label_ui.manage_labels_menu(sample_issue)

        # Assertions
        assert result is True
        mock_label_ui.service.get_available_labels.assert_called_once()
        mock_label_ui.remove_label_menu.assert_called_once()
        mock_label_ui.service.jira.get_issue.assert_called_once_with(
            "TEST-123", fields=["labels"]
        )

    @patch("subprocess.run")
    def test_manage_labels_menu_refresh(self, mock_run, mock_label_ui, sample_issue):
        """Test the main label management menu with refresh option."""
        # Setup subprocess.run mock to return a refresh action
        mock_process = MagicMock()
        mock_process.stdout = "refresh|Refresh label list from server"
        mock_run.return_value = mock_process

        # Mock available labels
        mock_label_ui.service.get_available_labels.return_value = [
            "bug",
            "documentation",
            "frontend",
            "backend",
            "ui",
        ]

        # Mock the updated issue
        updated_issue = {
            "key": "TEST-123",
            "fields": {
                "summary": "Test issue",
                "labels": ["bug", "documentation", "frontend"],
            },
        }
        mock_label_ui.service.jira.get_issue.return_value = updated_issue

        # Call the method
        result = mock_label_ui.manage_labels_menu(sample_issue)

        # Assertions
        assert result is True
        mock_label_ui.service.clear_label_cache.assert_called_once()
        mock_label_ui.service.get_available_labels.assert_called_with(
            force_refresh=True
        )
        mock_label_ui.service.jira.get_issue.assert_called_once_with(
            "TEST-123", fields=["labels"]
        )

    @patch("subprocess.run")
    def test_manage_labels_menu_canceled(self, mock_run, mock_label_ui, sample_issue):
        """Test the main label management menu when canceled."""
        # Setup subprocess.run mock to return no output (user canceled)
        mock_process = MagicMock()
        mock_process.stdout = ""
        mock_run.return_value = mock_process

        # Mock available labels
        mock_label_ui.service.get_available_labels.return_value = [
            "bug",
            "documentation",
            "frontend",
            "backend",
            "ui",
        ]

        # Call the method
        result = mock_label_ui.manage_labels_menu(sample_issue)

        # Assertions
        assert result is False
        mock_label_ui.service.get_available_labels.assert_called_once()
        mock_label_ui.add_label_menu.assert_not_called()
        mock_label_ui.remove_label_menu.assert_not_called()

    @patch("subprocess.run")
    @patch("click.prompt")
    def test_add_label_menu_custom_label(
        self, mock_prompt, mock_run, mock_label_ui, sample_issue
    ):
        """Test adding a custom label."""
        # Setup subprocess.run mock to return custom label option
        mock_process = MagicMock()
        mock_process.stdout = "custom|Enter a custom label"
        mock_run.return_value = mock_process

        # Mock the prompt response
        mock_prompt.return_value = "new-custom-label"

        # Mock the service add_label method
        mock_label_ui.service.add_label.return_value = True

        # Call the method
        current_labels = sample_issue["fields"]["labels"]
        available_labels = ["bug", "documentation", "frontend", "backend", "ui"]
        result = mock_label_ui.add_label_menu(
            "TEST-123", current_labels, available_labels
        )

        # Assertions
        assert result is True
        mock_prompt.assert_called_once_with("Enter new label")
        mock_label_ui.service.add_label.assert_called_once_with(
            "TEST-123", "new-custom-label"
        )

    @patch("subprocess.run")
    def test_add_label_menu_existing_label(self, mock_run, mock_label_ui, sample_issue):
        """Test adding an existing label from the list."""
        # Setup subprocess.run mock to return an existing label
        mock_process = MagicMock()
        mock_process.stdout = "backend|backend"
        mock_run.return_value = mock_process

        # Mock the service add_label method
        mock_label_ui.service.add_label.return_value = True

        # Call the method
        current_labels = sample_issue["fields"]["labels"]
        available_labels = ["bug", "documentation", "frontend", "backend", "ui"]
        result = mock_label_ui.add_label_menu(
            "TEST-123", current_labels, available_labels
        )

        # Assertions
        assert result is True
        mock_label_ui.service.add_label.assert_called_once_with("TEST-123", "backend")

    @patch("subprocess.run")
    def test_remove_label_menu(self, mock_run, mock_label_ui, sample_issue):
        """Test removing a label."""
        # Setup subprocess.run mock to return a label to remove
        mock_process = MagicMock()
        mock_process.stdout = "frontend|frontend"
        mock_run.return_value = mock_process

        # Mock the service remove_label method
        mock_label_ui.service.remove_label.return_value = True

        # Call the method
        current_labels = sample_issue["fields"]["labels"]
        result = mock_label_ui.remove_label_menu("TEST-123", current_labels)

        # Assertions
        assert result is True
        mock_label_ui.service.remove_label.assert_called_once_with(
            "TEST-123", "frontend"
        )

    def test_remove_label_empty_labels(self, mock_label_ui, empty_labels_issue):
        """Test removing a label when there are no labels."""
        # Call the method
        current_labels = empty_labels_issue["fields"]["labels"]
        result = mock_label_ui.remove_label_menu("TEST-123", current_labels)

        # Assertions
        assert result is False

    @patch("subprocess.run")
    def test_run_fzf_menu_error(self, mock_run, mock_label_ui):
        """Test handling of errors in the FZF menu."""
        # Setup subprocess.run to raise CalledProcessError
        mock_run.side_effect = subprocess.CalledProcessError(1, "fzf")

        # Call the method
        result = mock_label_ui._run_fzf_menu("tmp_file_path", "TEST-123")

        # Assertions
        assert result is None
        mock_run.assert_called_once()
