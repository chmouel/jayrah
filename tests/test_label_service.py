"""Unit tests for the label_service module."""

import pytest
from unittest.mock import MagicMock, patch

from jayrah.label_service import LabelService


class TestLabelService:
    """Tests for the LabelService class."""

    def test_get_available_labels_from_cache(self, mock_jira_client, sample_config):
        """Test retrieving labels from cache."""
        # Setup
        service = LabelService(mock_jira_client, sample_config)
        mock_jira_client.cache.get_direct.return_value = ["label1", "label2"]

        # Call
        labels = service.get_available_labels()

        # Assert
        assert labels == ["label1", "label2"]
        mock_jira_client.cache.get_direct.assert_called_once_with("jayrah_labels")
        mock_jira_client.get_labels.assert_not_called()

    def test_get_available_labels_from_api(self, mock_jira_client, sample_config):
        """Test retrieving labels from API when cache is empty."""
        # Setup
        service = LabelService(mock_jira_client, sample_config)
        mock_jira_client.cache.get_direct.return_value = None
        mock_jira_client.get_labels.return_value = ["label1", "label2", "label3"]

        # Call
        labels = service.get_available_labels()

        # Assert
        assert labels == ["label1", "label2", "label3"]
        mock_jira_client.cache.get_direct.assert_called_once_with("jayrah_labels")
        mock_jira_client.get_labels.assert_called_once()
        mock_jira_client.cache.set_direct.assert_called_once()

    def test_get_available_labels_with_force_refresh(
        self, mock_jira_client, sample_config
    ):
        """Test retrieving labels with force_refresh option."""
        # Setup
        service = LabelService(mock_jira_client, sample_config)
        mock_jira_client.get_labels.return_value = ["label1", "label2", "label3"]

        # Call
        labels = service.get_available_labels(force_refresh=True)

        # Assert
        assert labels == ["label1", "label2", "label3"]
        mock_jira_client.cache.get_direct.assert_not_called()
        mock_jira_client.get_labels.assert_called_once()
        mock_jira_client.cache.set_direct.assert_called_once()

    def test_get_available_labels_api_error(self, mock_jira_client, sample_config):
        """Test handling API errors when fetching labels."""
        # Setup
        service = LabelService(mock_jira_client, sample_config)
        mock_jira_client.cache.get_direct.return_value = None
        mock_jira_client.get_labels.side_effect = Exception("API Error")

        # Call
        labels = service.get_available_labels()

        # Assert
        assert labels == []
        mock_jira_client.cache.get_direct.assert_called_once_with("jayrah_labels")
        mock_jira_client.get_labels.assert_called_once()

    def test_get_issue_labels(self, mock_jira_client, sample_config):
        """Test retrieving labels for a specific issue."""
        # Setup
        service = LabelService(mock_jira_client, sample_config)
        mock_issue = {"fields": {"labels": ["bug", "frontend", "priority"]}}
        mock_jira_client.get_issue.return_value = mock_issue

        # Call
        labels = service.get_issue_labels("TEST-123")

        # Assert
        assert labels == ["bug", "frontend", "priority"]
        mock_jira_client.get_issue.assert_called_once_with(
            "TEST-123", fields=["labels"]
        )

    def test_get_issue_labels_no_labels(self, mock_jira_client, sample_config):
        """Test retrieving labels when issue has no labels."""
        # Setup
        service = LabelService(mock_jira_client, sample_config)
        mock_issue = {"fields": {}}
        mock_jira_client.get_issue.return_value = mock_issue

        # Call
        labels = service.get_issue_labels("TEST-123")

        # Assert
        assert labels == []
        mock_jira_client.get_issue.assert_called_once_with(
            "TEST-123", fields=["labels"]
        )

    def test_get_issue_labels_error(self, mock_jira_client, sample_config):
        """Test error handling when retrieving issue labels."""
        # Setup
        service = LabelService(mock_jira_client, sample_config)
        mock_jira_client.get_issue.side_effect = Exception("API Error")

        # Call
        labels = service.get_issue_labels("TEST-123")

        # Assert
        assert labels == []
        mock_jira_client.get_issue.assert_called_once_with(
            "TEST-123", fields=["labels"]
        )    def test_add_label_success(self, mock_jira_client, sample_config):
        """Test adding a label successfully."""
        # Setup
        service = LabelService(mock_jira_client, sample_config)
        mock_jira_client.add_label.return_value = {"key": "TEST-123"}
        
        # Call
        result = service.add_label("TEST-123", "frontend")
        
        # Assert
        assert result is True
        mock_jira_client.add_label.assert_called_once_with("TEST-123", "frontend")
        # Check if the issue was refreshed in cache
        mock_jira_client.get_issue.assert_called_once_with("TEST-123", use_cache=False)
        mock_jira_client.get_issue.assert_called_once_with("TEST-123", use_cache=False)

    def test_add_label_error(self, mock_jira_client, sample_config):
        """Test error handling when adding a label."""
        # Setup
        service = LabelService(mock_jira_client, sample_config)
        mock_jira_client.add_label.side_effect = Exception("API Error")

        # Call
        result = service.add_label("TEST-123", "frontend")

        # Assert
        assert result is False
        mock_jira_client.add_label.assert_called_once_with("TEST-123", "frontend")

    def test_remove_label_success(self, mock_jira_client, sample_config):
        """Test removing a label successfully."""
        # Setup
        service = LabelService(mock_jira_client, sample_config)
        mock_jira_client.remove_label.return_value = {"key": "TEST-123"}

        # Call
        result = service.remove_label("TEST-123", "frontend")

        # Assert
        assert result is True
        mock_jira_client.remove_label.assert_called_once_with("TEST-123", "frontend")

    def test_remove_label_error(self, mock_jira_client, sample_config):
        """Test error handling when removing a label."""
        # Setup
        service = LabelService(mock_jira_client, sample_config)
        mock_jira_client.remove_label.side_effect = Exception("API Error")

        # Call
        result = service.remove_label("TEST-123", "frontend")

        # Assert
        assert result is False
        mock_jira_client.remove_label.assert_called_once_with("TEST-123", "frontend")

    def test_clear_label_cache(self, mock_jira_client, sample_config):
        """Test clearing the label cache."""
        # Setup
        service = LabelService(mock_jira_client, sample_config)

        # Call
        service.clear_label_cache()

        # Assert
        mock_jira_client.cache.set_direct.assert_called_once_with("jayrah_labels", None)
