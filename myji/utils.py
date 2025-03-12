import datetime
import shutil
import subprocess
import sys

# ANSI color codes
COLORS = {
    "green": "\033[92m",
    "yellow": "\033[93m",
    "red": "\033[91m",
    "cyan": "\033[96m",
    "magenta": "\033[95m",
    "blue": "\033[94m",
    "reset": "\033[0m",
    "bold": "\033[1m",
}

# Log levels with corresponding colors
LOG_LEVELS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "SUCCESS": "blue",
}


def log(message, level="INFO", verbose_only=False, verbose=False, file=sys.stdout):
    """
    Print a colored log message based on level.

    Args:
        message (str): The message to print
        level (str): Log level (DEBUG, INFO, WARNING, ERROR, SUCCESS)
        verbose_only (bool): Only print if verbose mode is enabled
        verbose (bool): Whether verbose mode is enabled
        file: File object to write to (default: sys.stdout)
    """
    if verbose_only and not verbose:
        return

    # Default to INFO if invalid level provided
    color = COLORS.get(LOG_LEVELS.get(level, "green"))
    reset = COLORS["reset"]

    # Format level prefix
    prefix = f"[{color}{level}{reset}] " if level != "INFO" else ""

    # For error messages, print to stderr
    if level == "ERROR":
        file = sys.stderr

    # Apply color to the entire message for warnings and errors
    if level in ["WARNING", "ERROR"]:
        print(f"{prefix}{color}{message}{reset}", file=file)
    else:
        print(f"{prefix}{message}", file=file)


def colorize(color, text):
    """Colorize text with ANSI color codes"""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def show_time(s):
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%Y-%m-%d")


def parse_email(s):
    return s.split("@")[0].split("+")[0]


def get_pass_key(s):
    """
    Get the password key from a password store

    Args:
        s (str): The string to parse.

    Returns:
        str: The password key.
    """
    # check if the pass utility is in path
    if not shutil.which("pass"):
        log("pass utility not found in path", level="DEBUG")
        return None

    p = subprocess.Popen(
        ["pass", "show", s],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    out, err = p.communicate()
    if p.returncode != 0:
        log(f"Error getting password key: {err.decode().strip()}", level="ERROR")
        return None
    return out.decode().strip()
