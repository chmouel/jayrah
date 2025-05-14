"""CSS loader for Textual UI components"""
import importlib.resources
import pathlib


def get_css_path(filename):
    """Get the path to a CSS file in the ui package."""
    pkg_path = pathlib.Path(__file__).parent.resolve()
    return pkg_path / filename
