"""Jayrah CLI command group initialization."""

from jayrah.ui.web import cli as web_cli

from . import browse, cache, create, mcli, mcp
from .common import cli as cli

__all__ = ["browse", "cache", "create", "mcp", "cli", "web_cli", "mcli"]
