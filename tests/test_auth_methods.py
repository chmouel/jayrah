"""
Test authentication methods for the JiraHTTP class.
"""

import base64
import unittest
from unittest.mock import MagicMock, patch

from jayrah.api.jira_client import JiraHTTP


class TestJiraHTTPAuth(unittest.TestCase):
    """Test the authentication methods in the JiraHTTP class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_config = {
            "jira_server": "https://test-jira.example.com",
            "jira_user": "testuser",
            "jira_password": "testpassword",
            "jira_project": "TEST",
            "verbose": False,
            "insecure": False,
            "no_cache": True,  # Disable caching for tests
        }

    def test_default_auth_method_for_v2(self):
        """Test that API v2 uses Bearer token authentication by default."""
        client = JiraHTTP(self.mock_config, api_version="2")
        self.assertEqual(client.auth_method, "bearer")
        self.assertEqual(
            client.headers["Authorization"],
            f"Bearer {self.mock_config['jira_password']}",
        )

    def test_default_auth_method_for_v3(self):
        """Test that API v3 uses Basic authentication by default."""
        client = JiraHTTP(self.mock_config, api_version="3")
        self.assertEqual(client.auth_method, "basic")

        # Verify that the Authorization header contains a Basic auth token
        auth_header = client.headers["Authorization"]
        self.assertTrue(auth_header.startswith("Basic "))

        # Verify the encoded credentials
        encoded_auth = auth_header.split(" ")[1]
        decoded_auth = base64.b64decode(encoded_auth).decode("utf-8")
        self.assertEqual(
            decoded_auth,
            f"{self.mock_config['jira_user']}:{self.mock_config['jira_password']}",
        )

    def test_explicit_bearer_auth_for_v3(self):
        """Test using Bearer token auth explicitly with API v3."""
        client = JiraHTTP(self.mock_config, api_version="3", auth_method="bearer")
        self.assertEqual(client.auth_method, "bearer")
        self.assertEqual(
            client.headers["Authorization"],
            f"Bearer {self.mock_config['jira_password']}",
        )

    def test_explicit_basic_auth_for_v2(self):
        """Test using Basic auth explicitly with API v2."""
        client = JiraHTTP(self.mock_config, api_version="2", auth_method="basic")
        self.assertEqual(client.auth_method, "basic")

        # Verify that the Authorization header contains a Basic auth token
        auth_header = client.headers["Authorization"]
        self.assertTrue(auth_header.startswith("Basic "))

    def test_basic_auth_missing_username(self):
        """Test that Basic auth fails when username is missing."""
        config_without_username = self.mock_config.copy()
        del config_without_username["jira_user"]

        with self.assertRaises(Exception) as context:
            JiraHTTP(config_without_username, api_version="3")

        print(context.exception)
        self.assertTrue("requires both username and password" in str(context.exception))

    @patch("urllib.request.urlopen")
    def test_v3_basic_auth_request(self, mock_urlopen):
        """Test that a request with API v3 and Basic auth works correctly."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"issuetypes": []}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        # Create client and make request
        client = JiraHTTP(self.mock_config, api_version="3")
        client.get_issue_types()

        # Check that urlopen was called with the correct request
        args, _kwargs = mock_urlopen.call_args
        request = args[0]

        # Verify the Authorization header contains Basic auth
        self.assertTrue(request.headers["Authorization"].startswith("Basic "))


if __name__ == "__main__":
    unittest.main()
