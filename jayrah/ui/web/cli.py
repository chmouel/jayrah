"""Command-line interface for running the Jayrah web server."""

import click
import uvicorn

from jayrah.commands.common import cli
from jayrah.ui.web.server import initialize_app_state


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host address to bind.")
@click.option("--port", default=8000, type=int, help="Port to bind.")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload.")
@click.option("--workers", default=1, type=int, help="Number of worker processes.")
@click.option("--log-level", default="info", help="Logging level.")
@click.option(
    "--reloads-dirs",
    default=None,
    type=str,
    help="Comma-separated list of directories to watch for reloads.",
)
def web(host, port, reload, workers, log_level, reloads_dirs=None):
    """Web interface for Jayrah."""
    initialize_app_state()
    if reloads_dirs:
        reloads_dirs = reloads_dirs.split(",")
        reload = True
    try:
        uvicorn.run(
            "jayrah.ui.web.server:app",
            host=host,
            port=port,
            reload=reload,
            workers=workers,
            log_level=log_level,
            reload_dirs=reloads_dirs,
        )
    except KeyboardInterrupt:
        print("Server stopped by user.")
