"""Authentication handlers for Jira API."""

import base64
from abc import ABC, abstractmethod
from typing import Dict

import click


class AuthenticatorBase(ABC):
    """Base class for authentication handlers."""

    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers."""


class BearerAuthenticator(AuthenticatorBase):
    """Bearer token authentication."""

    def __init__(self, token: str):
        if not token:
            raise click.ClickException("Bearer authentication requires a token")
        self.token = token

    def get_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


class BasicAuthenticator(AuthenticatorBase):
    """Basic authentication with username and password."""

    def __init__(self, username: str, password: str):
        if not username or not password:
            raise click.ClickException(
                "Basic authentication requires both jira_user and jira_password"
            )
        self.username = username
        self.password = password

    def get_headers(self) -> Dict[str, str]:
        auth_string = f"{self.username}:{self.password}"
        encoded_auth = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
        return {"Authorization": f"Basic {encoded_auth}"}


def create_authenticator(config: dict, auth_method: str) -> AuthenticatorBase:
    """Factory function to create appropriate authenticator."""
    if auth_method == "basic":
        username = config.get("jira_user")
        password = config.get("jira_password")
        if username is None or password is None:
            raise click.ClickException(
                "Basic authentication requires both username and password in config"
            )
        return BasicAuthenticator(username, password)
    if auth_method == "bearer":
        token = config.get("jira_password")
        if token is None:
            raise click.ClickException(
                "Bearer authentication requires a token in config"
            )
        return BearerAuthenticator(token)
    raise click.ClickException(f"Unknown authentication method: {auth_method}")
