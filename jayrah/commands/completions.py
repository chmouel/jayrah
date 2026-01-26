""" "Click parameter types for JIRA objects with shell completion."""

import pathlib

import click

from .. import config
from ..api import jira_client as jirahttp
from ..config import defaults, read_config


def setup_jira_http(ctx):
    """Initializes and returns a JiraHTTP client from a configuration file."""
    config_file = defaults.CONFIG_FILE
    if custom_config := ctx.parent.params.get("config_file"):
        config_file = pathlib.Path(custom_config)
    cfg = read_config({}, config_file)
    # Get API version from config or use default
    api_version = cfg.get("api_version", defaults.API_VERSION)
    auth_method = cfg.get("auth_method", defaults.AUTH_METHOD)
    return jirahttp.JiraHTTP(cfg, api_version=api_version, auth_method=auth_method)


class BoardType(click.ParamType):
    name = "board"

    def shell_complete(self, ctx, _, incomplete):
        config_file = defaults.CONFIG_FILE
        if ctx.parent.params.get("config_file"):
            config_file = pathlib.Path(ctx.parent.params.get("config_file"))
        cfg = config.read_config({}, config_file)
        return [
            click.shell_completion.CompletionItem(x)
            for x in [x.get("name") for x in cfg.get("boards", [])]
            if x.startswith(incomplete)
        ]


class JiraObjectCompletion(click.ParamType):
    """
    A base class for click parameter types that provides shell completion
    for JIRA objects.
    """

    name = "jira_object"

    def __init__(self, fetch_method_name):
        self.fetch_method_name = fetch_method_name

    def shell_complete(self, ctx, _, incomplete):
        """
        Provides shell completion by fetching data from JIRA.
        """
        try:
            jiracnx = setup_jira_http(ctx)
            fetch_method = getattr(jiracnx, self.fetch_method_name)

            # Try calling with use_cache=True for methods that support it
            # (like get_issue_types)
            try:
                items = fetch_method(use_cache=True)
            except TypeError:
                # Method doesn't accept use_cache parameter
                items = fetch_method()

            # Handle dict response (like from get_issue_types)
            if isinstance(items, dict):
                return [
                    click.shell_completion.CompletionItem(name)
                    for name in items.keys()
                    if name.lower().startswith(incomplete.lower())
                ]

            # Handle list response (like from get_priorities)
            return [
                click.shell_completion.CompletionItem(item["name"])
                for item in items
                if "name" in item
                and item["name"].lower().startswith(incomplete.lower())
            ]
        except Exception:
            # Fail gracefully on errors - return empty list instead of crashing shell
            return []


class PriorityType(JiraObjectCompletion):
    """A click parameter type for JIRA priorities."""

    name = "priority"

    def __init__(self):
        super().__init__("get_priorities")


class IssueType(JiraObjectCompletion):
    """A click parameter type for JIRA issue types."""

    name = "issuetype"

    def __init__(self):
        super().__init__("get_issue_types")


class ComponentType(JiraObjectCompletion):
    """A click parameter type for JIRA components."""

    name = "components"

    def __init__(self):
        super().__init__("get_components")
