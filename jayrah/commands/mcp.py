"""MCP command for Jayrah Jira CLI."""

import asyncio

import click

from ..mcp import server
from .common import cli


@cli.command("mcp")
@click.option("--host", default="127.0.0.1", help="Host to bind the MCP server")
@click.option("--port", default=8765, type=int, help="Port to bind the MCP server")
@click.pass_context
def mcp_server_cmd(ctx, host, port):
    """Start the MCP server for programmatic access."""

    # Use the config file from the CLI context if available
    # config_file = ctx.parent.params.get("config_file") if ctx.parent else None
    try:
        asyncio.run(server.main())
    except KeyboardInterrupt:
        click.secho("MCP server stopped by user", fg="yellow")
