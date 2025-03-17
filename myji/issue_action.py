import subprocess
import tempfile

import click

from myji import utils

from . import defaults


def action_menu(ticketj, obj):
    result = choose_action(ticketj, obj)
    ticket_number = ticketj["key"]
    match result:
        case "browse_issue":
            utils.browser_open_ticket(ticket_number)
            return
        case "edit_description":
            return


def choose_action(ticketj, obj):
    """Display action menu for the issue"""
    verbose = obj.verbose
    if not ticketj:
        return None

    ticket_number = ticketj["key"]
    # Placeholder for the action menu logic
    if verbose:
        utils.log(
            f"Preparing fuzzy search interface for ticket {ticket_number}",
            "DEBUG",
            verbose_only=True,
            verbose=verbose,
        )

    with tempfile.NamedTemporaryFile("w+") as tmp:
        actions = {
            "Browse issue": ("browse_issue", "🔍"),
            "Edit Description": ("edit_description", "✏️"),
            "Transition issue": ("transition_issue", "🔄"),
            "Add comment": ("add_comment", "💬"),
        }

        tmp.write(f"|Choose an action for {ticket_number}\n")

        for action, (func, icon) in actions.items():
            ss = f"{func}|{icon} {action}"
            tmp.write(ss + "\n")
        tmp.flush()

        preview_cmd = f"{obj.myj_path} issue view '{ticket_number}'"
        fzf_cmd = [
            "fzf",
            "-d",
            "|",
            "--ansi",
            "--header-lines=1",
            "--with-nth=2..",
            "--accept-nth=1",
            "--reverse",
            "--ansi",
            "--preview",
            preview_cmd,
            "--preview-window",
            "bottom:80%:wrap",
        ]
        fzf_cmd += defaults.FZFOPTS

        try:
            # Add check parameter and use with statement for file opening
            with open(tmp.name, encoding="utf-8") as tmp_file:
                result = subprocess.run(
                    fzf_cmd,
                    stdin=tmp_file,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            if verbose and result.stdout:
                click.echo(f"User selected: {result.stdout.strip()}", err=True)

        except subprocess.CalledProcessError as e:
            click.secho(f"Error occurred: {e}", fg="red", err=True)
            return None

        return result.stdout.strip().split("\t")[0] if result.stdout else None
