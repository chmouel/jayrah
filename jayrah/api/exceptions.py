"""Custom exception classes for Jira API errors."""


class JiraAPIError(Exception):
    """Base exception for Jira API errors."""

    def __init__(
        self, message: str, endpoint: str, status_code: int, response_body: str
    ):
        self.endpoint = endpoint
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)

    def __str__(self):
        return (
            f"{super().__str__()}\n"
            f"Endpoint: {self.endpoint}\n"
            f"Status: {self.status_code}\n"
            f"Response: {self.response_body}"
        )


class JiraRateLimitError(JiraAPIError):
    """Exception raised when Jira rate limit (429) is exceeded."""

    def __init__(self, endpoint: str, response_body: str):
        super().__init__(
            "Rate limit exceeded. Please wait before making more requests.",
            endpoint,
            429,
            response_body,
        )


class JiraNotFoundError(JiraAPIError):
    """Exception raised when Jira resource is not found (404)."""

    def __init__(self, endpoint: str, response_body: str):
        super().__init__(
            "Resource not found. Check that the project key and endpoint are correct.",
            endpoint,
            404,
            response_body,
        )


class JiraAuthenticationError(JiraAPIError):
    """Exception raised when authentication fails (401)."""

    def __init__(self, endpoint: str, response_body: str):
        super().__init__(
            "Authentication failed. Check your credentials in ~/.config/jayrah/config.yaml",
            endpoint,
            401,
            response_body,
        )


class JiraAuthorizationError(JiraAPIError):
    """Exception raised when authorization fails (403)."""

    def __init__(self, endpoint: str, response_body: str):
        super().__init__(
            "Access forbidden. You don't have permission to access this resource.",
            endpoint,
            403,
            response_body,
        )
