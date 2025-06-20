"""Jayrah utility functions and helpers."""

import datetime
import os
import subprocess
import sys
import tempfile
import webbrowser

import click


def make_osc8_link(text, url):
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def make_full_url(ticket, server):
    if server is None:
        raise ValueError("No Jira server URL provided")
    return f"{server}/browse/{ticket}"


def browser_open_ticket(ticket, config):
    server = config.get("jira_server")
    if not ticket:
        project = config.get("jira_component")
        if not project:
            raise ValueError("No ticket or project specified")
        webbrowser.open(f"{server}/projects/{project}")
        return

    try:
        webbrowser.open(make_full_url(ticket, server))
    except Exception as e:
        click.secho(f"Failed to open URL {ticket}: {e}", fg="red")


def log(message, level="INFO", verbose_only=False, verbose=False, file=sys.stdout):
    """
    Log a message with color-coded level prefix.

    Args:
        message (str): The message to log.
        level (str): The log level (e.g., INFO, WARNING, ERROR).
        verbose_only (bool): Only log if verbose mode is enabled.
        verbose (bool): Whether verbose mode is enabled.
        file (file): The file to write to.
    """
    if verbose_only and not verbose:
        return

    prefix = f"[{level}] " if level else ""

    if file == sys.stderr:
        sys.stderr.write(f"{prefix}{message}\n")
    else:
        sys.stdout.write(f"{prefix}{message}\n")


def colorize(color, text):
    """Colorize text with Click's style function"""
    return click.style(text, fg=color.lower())


def show_time(s):
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f%z").strftime("%Y-%m-%d")


def parse_email(dico):
    s = ""
    if "emailAddress" in dico:
        s = dico["emailAddress"]
    elif "key" in dico:
        s = dico["key"]
    return s.split("@")[0].split("+")[0]


def get_pass_key(pass_cmd, s):
    cmd = [pass_cmd, "show", s]
    try:
        return subprocess.check_output(cmd, text=True).strip()
    except subprocess.CalledProcessError:
        click.secho(f"Failed to retrieve password for {s}", fg="red")
        return None


def edit_text_with_editor(initial_text, extension=".md"):
    """Edit text using the system's default editor"""
    # Use the EDITOR environment variable, or default to vi
    editor = os.environ.get("EDITOR", os.environ.get("VISUAL", "vi"))

    # Create a temporary file with the initial text
    with tempfile.NamedTemporaryFile(suffix=extension, mode="w+", delete=False) as tf:
        tf.write(initial_text)
        tf_path = tf.name

    try:
        # Open the editor with the temporary file
        click.echo(f"Opening editor ({editor}) to edit description...")
        subprocess.run([editor, tf_path], check=True)

        # Read the edited content
        with open(tf_path, "r") as tf:
            edited_text = tf.read()

        return edited_text
    finally:
        # Clean up the temporary file
        os.unlink(tf_path)
