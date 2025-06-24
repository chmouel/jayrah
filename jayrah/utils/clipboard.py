# pylint: disable=too-many-return-statements
"""Clipboard utilities for cross-platform URL copying."""

import os
import platform
import subprocess
from typing import Optional


def detect_platform() -> str:
    """Detect the current platform for clipboard operations.

    Returns:
        Platform identifier: 'macos', 'windows', 'wayland', 'x11', 'wsl', or 'unknown'
    """
    system = platform.system().lower()

    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        # Check for WSL
        if "microsoft" in platform.uname().release.lower():
            return "wsl"

        # Check for Wayland
        if os.environ.get("WAYLAND_DISPLAY"):
            return "wayland"

        # Check for X11
        if os.environ.get("DISPLAY"):
            return "x11"

        return "linux"

    return "unknown"


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard based on the current platform.

    Args:
        text: The text to copy to clipboard

    Returns:
        True if successful, False otherwise
    """
    platform_type = detect_platform()

    try:
        if platform_type == "macos":
            subprocess.run(["pbcopy"], input=text, text=True, check=True)
        elif platform_type == "windows":
            subprocess.run(["clip"], input=text, text=True, check=True)
        elif platform_type == "wsl":
            subprocess.run(["clip.exe"], input=text, text=True, check=True)
        elif platform_type == "wayland":
            subprocess.run(["wl-copy"], input=text, text=True, check=True)
        elif platform_type == "x11":
            # Try xclip first, then xsel as fallback
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text,
                    text=True,
                    check=True,
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                subprocess.run(
                    ["xsel", "--clipboard", "--input"],
                    input=text,
                    text=True,
                    check=True,
                )
        else:
            return False

        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_clipboard_command() -> Optional[str]:
    """Get the clipboard command for the current platform.

    Returns:
        The command name if available, None otherwise
    """
    platform_type = detect_platform()

    if platform_type == "macos":
        return "pbcopy"
    if platform_type == "windows":
        return "clip"
    if platform_type == "wsl":
        return "clip.exe"
    if platform_type == "wayland":
        return "wl-copy"
    if platform_type == "x11":
        # Check which tool is available
        for cmd in ["xclip", "xsel"]:
            try:
                subprocess.run([cmd, "--version"], capture_output=True, check=True)
                return cmd
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        return None

    return None
