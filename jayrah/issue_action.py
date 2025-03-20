import subprocess
import tempfile

import click

from jayrah import utils

from . import defaults


def transition_issue(ticketj, obj):
    """Display a fzf menu of available transitions and return the selected transition ID"""
    ticket_number = ticketj["key"]
    transitionj = obj.jira.get_transitions(ticket_number)

    if (
        not transitionj
        or "transitions" not in transitionj
        or not transitionj["transitions"]
    ):
        click.secho(
            f"No transitions available for {ticket_number}", fg="yellow", err=True
        )
        return None

    transitions = transitionj["transitions"]

    with tempfile.NamedTemporaryFile("w+") as tmp:
        tmp.write(f"|Select a transition for {ticket_number}\n")

        for transition in transitions:
            transition_id = transition["id"]
            name = transition["name"]
            to_status = transition["to"]["name"]
            description = transition["to"].get(
                "description", "No description available"
            )

            # Format: id|name (to_status): description
            line = f"{transition_id}|{name} → {to_status}: {description}\n"
            tmp.write(line)

        tmp.flush()

        preview_cmd = f"{obj.config.get('jayrah_path')} issue view '{ticket_number}'"
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
            with open(tmp.name, encoding="utf-8") as tmp_file:
                result = subprocess.run(
                    fzf_cmd,
                    stdin=tmp_file,
                    capture_output=True,
                    text=True,
                    check=False,
                )

            if not result.stdout:
                return None

            transition_id = result.stdout.strip().split("|")[0]

            # Find the name of the selected transition for confirmation
            selected_name = next(
                (t["name"] for t in transitions if t["id"] == transition_id), "Unknown"
            )

            # Confirm with the user
            if click.confirm(f"Transition issue to '{selected_name}'?", default=True):
                obj.jira.transition_issue(ticket_number, transition_id)
                click.secho(
                    f"✅ Issue {ticket_number} successfully transitioned to '{selected_name}'",
                    fg="green",
                    err=True,
                )
            else:
                click.secho("Transition canceled", fg="yellow", err=True)
                return None

        except subprocess.CalledProcessError as e:
            click.secho(f"Error occurred: {e}", fg="red", err=True)
            return None


def edit_description(ticketj, obj):
    """Edit the description of a Jira issue"""
    ticket_number = ticketj["key"]
    current_description = ticketj["fields"].get("description", "")

    # Add some helpful instructions at the top of the file
    editor_text = (
        "# Edit the description for issue " + ticket_number + "\n"
        "# The first lines starting with # will be ignored\n"
        "# Save and exit the editor to submit changes, or exit without saving to cancel\n"
        "#\n\n" + (current_description or "")
    )

    # Open the editor and get the updated description
    updated_description = utils.edit_text_with_editor(editor_text, extension=".jira")

    # Remove comment lines and check if there were actual changes
    cleaned_description = "\n".join(
        line
        for line in updated_description.splitlines()
        if not line.strip().startswith("#")
    )

    # Strip whitespace from both descriptions for comparison
    if cleaned_description.strip() == current_description.strip():
        click.secho("No changes made to description", fg="yellow", err=True)
        return False

    # Confirm with the user before submitting
    if click.confirm("Submit updated description?", default=True):
        try:
            # Update the issue with the new description
            obj.jira.update_issue(ticket_number, {"description": cleaned_description})
            click.secho(
                f"✅ Description updated for {ticket_number}", fg="green", err=True
            )
            return True
        except Exception as e:
            click.secho(f"Error updating description: {e}", fg="red", err=True)
            return False
    else:
        click.secho("Update canceled", fg="yellow", err=True)
        return False


def action_menu(ticketj, obj):
    result = choose_action(ticketj, obj)
    ticket_number = ticketj["key"]

    if not result:
        return

    match result:
        case "browse_issue":
            utils.browser_open_ticket(ticket_number, obj.config)
            return
        case "edit_description":
            # Call our new edit_description function
            edit_success = edit_description(ticketj, obj)
            if edit_success and obj.config.get("verbose"):
                click.echo(f"Description updated for {ticket_number}", err=True)
            return
        case "transition_issue":
            transition_id = transition_issue(ticketj, obj)
            if transition_id:
                try:
                    obj.jira.transition_issue(ticket_number, transition_id)
                    click.secho(
                        f"✅ Issue {ticket_number} successfully transitioned",
                        fg="green",
                        err=True,
                    )
                except Exception as e:
                    click.secho(f"Error transitioning issue: {e}", fg="red", err=True)
            return
        case "add_comment":
            click.secho("Add comment functionality coming soon", fg="yellow", err=True)
            return


def choose_action(ticketj, obj):
    """Display action menu for the issue"""
    verbose = obj.config.get("verbose")
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

        preview_cmd = f"{obj.config.get('jayrah_path')} issue view '{ticket_number}'"
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
