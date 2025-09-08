"""HTTP request handler for Jira API."""

import json
import ssl
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import click

from ..utils import cache, log


class JiraRequestHandler:
    """Handles HTTP requests to Jira API."""

    def __init__(
        self,
        base_url: str,
        headers: Dict[str, str],
        cache_instance: cache.JiraCache,
        verbose: bool = False,
        insecure: bool = False,
    ):
        self.base_url = base_url
        self.headers = headers
        self.cache = cache_instance
        self.verbose = verbose
        self.insecure = insecure

        if self.insecure:
            self._setup_insecure_ssl()

    def _setup_insecure_ssl(self):
        """Setup SSL context that doesn't verify certificates."""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context)
        )
        urllib.request.install_opener(opener)

        if self.verbose:
            log("WARNING: SSL certificate verification disabled")

    def _get_curl_command(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate an equivalent curl command for debugging purposes."""
        curl_parts = [f"curl -X {method}"]

        if self.insecure:
            curl_parts.append("-k")

        for key, value in headers.items():
            if key == "Authorization":
                if value.startswith("Bearer"):
                    value = "Bearer ${JIRA_API_TOKEN}"
                elif value.startswith("Basic"):
                    value = "Basic ${JIRA_BASIC_AUTH}"
            curl_parts.append(f'-H "{key}: {value}"')

        final_url = url
        if params:
            query_string = urlencode(params)
            final_url = f"{url}?{query_string}"

        if json_data:
            json_str = json.dumps(json_data)
            curl_parts.append(f"-d '{json_str}'")

        curl_parts.append(f"'{final_url}'")
        return " ".join(curl_parts)

    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        label: Optional[str] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """Make HTTP request to Jira API."""
        url = f"{self.base_url}/{endpoint}"

        if self.verbose:
            log(f"API call Requested: {method} {url}")
            if params:
                log(f"Parameters: {params}")
            if json_data:
                log(f"Request body: {json_data}")

        # Only use cache for GET requests
        if (
            method.upper() == "GET"
            and use_cache
            and not self.cache.config.get("no_cache")
        ):
            cached_response = self.cache.get(url, params, json_data)
            if cached_response:
                if self.verbose:
                    log("Using cached response from SQLite database")
                return cached_response

            if self.verbose:
                log(f"No cache found for: {url}")

        try:
            if self.verbose:
                log(f"Sending request to {url}...")
                curl_cmd = self._get_curl_command(
                    method, url, self.headers, params, json_data
                )
                log(f"curl command :\n{curl_cmd}")

            # Construct the full URL with parameters
            if params:
                query_string = urlencode(params)
                full_url = f"{url}?{query_string}"
            else:
                full_url = url

            # Prepare the request
            request = urllib.request.Request(full_url, method=method)

            # Add headers
            for key, value in self.headers.items():
                request.add_header(key, value)

            # Add JSON data if provided
            data = None
            if json_data:
                data = json.dumps(json_data).encode("utf-8")

            # Send the request
            response_data = self._send_request(request, data, label)

            # Cache the response for GET requests
            if method.upper() == "GET":
                if self.verbose:
                    log(f"Caching response for: {url}")
                self.cache.set(url, response_data, params, json_data)

            return response_data

        except urllib.error.HTTPError as e:
            log(f"HTTP error occurred: {e}")
            log(f"Response: {e.read().decode('utf-8')}")
            raise click.ClickException(f"HTTP error: {e}") from e
        except urllib.error.URLError as e:
            log(f"URL error occurred: {e}")
            raise click.ClickException(f"URL error: {e}") from e

    def _send_request(
        self,
        request: urllib.request.Request,
        data: Optional[bytes],
        label: Optional[str],
    ) -> Dict[str, Any]:
        """Send the actual HTTP request."""
        if not self.verbose and label:
            with click.progressbar(
                length=1,
                file=sys.stderr,
                label=label,
                show_eta=False,
                show_percent=False,
                fill_char="⣾⣷⣯⣟⡿⢿⣻⣽"[0],
                empty_char=" ",
            ) as bar:
                response_data = self._execute_request(request, data)
                bar.update(1)
        else:
            response_data = self._execute_request(request, data)

        return response_data

    def _execute_request(
        self, request: urllib.request.Request, data: Optional[bytes]
    ) -> Dict[str, Any]:
        """Execute the HTTP request and parse response."""
        with urllib.request.urlopen(request, data=data) as response:
            status_code = response.status
            response_text = response.read().decode("utf-8")
            response_data = json.loads(response_text) if response_text else {}

        if self.verbose:
            log(f"Response status: {status_code}")

        return response_data
