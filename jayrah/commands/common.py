"""Common utilities and helpers for Jayrah CLI commands."""

import os
import pathlib
import sys

import click

from .. import config, utils
from ..ui import boards


@click.group()
@click.option("--no-cache", "-n", is_flag=True, help="Disable caching of API responses")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--insecure", is_flag=True, help="Disable SSL verification for requests")
@click.option(
    "--jira-server",
    default=os.environ.get("JIRA_SERVER"),
    help="Jira server URL",
)
@click.option(
    "--jira-user",
    default=os.environ.get("JIRA_USER"),
    help="Jira user",
)
@click.option(
    "--jira-component",
    default=os.environ.get("JIRA_COMPONENT"),
    help="Jira user",
)
@click.option(
    "--jira-password",
    default=os.environ.get("JIRA_PASSWORD"),
    help="Jira user",
)
@click.option("--cache-ttl", "-t", help="Cache TTL in seconds")
@click.option(
    "-c",
    "--config-file",
    default=config.defaults.CONFIG_FILE,
    help="Config file to use",
)
@click.option("--quiet", is_flag=True, help="Suppress non-error output")
@click.option(
    "--ui-backend",
    type=click.Choice(["textual", "rust"], case_sensitive=False),
    default=None,
    help="UI backend for interactive commands in this invocation",
)
@click.pass_context
def cli(
    ctx,
    no_cache,
    verbose,
    insecure,
    jira_user,
    jira_password,
    jira_component,
    jira_server,
    cache_ttl,
    config_file,
    quiet,
    ui_backend,
):
    """Jira Helper Tool"""

    flag_config = {
        "jira_server": jira_server,
        "jira_user": jira_user,
        "jira_password": jira_password,
        "jira_component": jira_component,
        "cache_ttl": cache_ttl,
        "no_cache": no_cache,
        "verbose": verbose,
        "quiet": quiet,
        "ui_backend": ui_backend,
        "insecure": insecure,
        "jayrah_path": os.path.abspath(sys.argv[0]),
        "ctx": ctx,
    }
    wconfig = config.make_config(flag_config, pathlib.Path(config_file))
    # CLI flags should win over persisted config for this invocation.
    if ui_backend:
        wconfig["ui_backend"] = ui_backend.lower()
        wconfig["_ui_backend_from_cli"] = True
    else:
        wconfig["_ui_backend_from_cli"] = False
    utils.log(f"Using config: {wconfig}", verbose=verbose, verbose_only=True)
    ctx.obj = boards.Boards(wconfig)
