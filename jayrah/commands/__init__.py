"""Jayrah CLI command group initialization."""

from .common import cli as cli

__all__ = ["cli", "browse", "cache", "create", "mcp"]

try:
    from . import browse  # noqa: F401
except Exception:  # pragma: no cover - optional dependencies
    browse = None

for _name in ("cache", "create", "mcp"):
    try:
        globals()[_name] = __import__(f".{_name}", globals(), locals(), [_name], 1)
    except Exception:  # pragma: no cover - optional dependencies
        globals()[_name] = None
