"""Data formatters for different Jira API versions."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Union


class FormatterBase(ABC):
    """Base class for API-specific data formatters."""

    @abstractmethod
    def format_description(self, description: str) -> Union[str, Dict[str, Any]]:
        """Format description for the API version."""

    @abstractmethod
    def format_comment(self, comment: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Format comment for the API version."""

    @abstractmethod
    def format_assignee(self, assignee: str) -> Dict[str, str]:
        """Format assignee for the API version."""

    @abstractmethod
    def get_issue_types_endpoint(self) -> str:
        """Get the endpoint for issue types."""


class V2Formatter(FormatterBase):
    """Formatter for Jira API v2."""

    def format_description(self, description: str) -> str:
        """API v2 uses plain text or wiki markup."""
        return description

    def format_comment(self, comment: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """API v2 uses plain text comments."""
        return {"body": comment}

    def format_assignee(self, assignee: str) -> Dict[str, str]:
        """API v2 uses username."""
        return {"name": assignee}

    def get_issue_types_endpoint(self) -> str:
        """API v2 endpoint for issue types."""
        return "issuetype"


class V3Formatter(FormatterBase):
    """Formatter for Jira API v3."""

    def format_description(self, description: str) -> Dict[str, Any]:
        """API v3 uses Atlassian Document Format (ADF)."""
        if isinstance(description, dict) and self._is_adf_format(description):
            return description
        return self._convert_to_adf(description)

    def format_comment(self, comment: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """API v3 uses ADF format for comments."""
        if isinstance(comment, dict) and self._is_adf_format(comment):
            adf_content = comment
        else:
            adf_content = self._convert_to_adf(str(comment))
        return {"body": adf_content}

    def format_assignee(self, assignee: str) -> Dict[str, str]:
        """API v3 prefers accountId but falls back to username."""
        if "@" in assignee:  # Looks like an email, likely an accountId
            return {"accountId": assignee}
        return {"name": assignee}

    def get_issue_types_endpoint(self) -> str:
        """API v3 endpoint for issue types."""
        return "issuetypes"

    def _convert_to_adf(self, text: str) -> Dict[str, Any]:
        """Convert plain text to Atlassian Document Format (ADF)."""
        return {
            "version": 1,
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": text}]}
            ],
        }

    def _is_adf_format(self, obj: Any) -> bool:
        """Check if an object is already in ADF format."""
        return (
            isinstance(obj, dict)
            and obj.get("version") is not None
            and obj.get("type") == "doc"
            and isinstance(obj.get("content"), list)
        )


def create_formatter(api_version: str) -> FormatterBase:
    """Factory function to create appropriate formatter."""
    if api_version == "3":
        return V3Formatter()
    if api_version == "2":
        return V2Formatter()
    raise ValueError(f"Unsupported API version: {api_version}")
