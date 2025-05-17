import subprocess
import tempfile
from functools import reduce

import click

from .... import defaults, utils


def fzf_search(self, issues):
    """Use fzf to interactively select an issue."""
    if self.verbose:
        utils.log(
            f"Preparing fzf search interface for {len(issues)} issues",
            "DEBUG",
            verbose_only=True,
            verbose=self.verbose,
        )

    if not issues:
        return None

    with tempfile.NamedTemporaryFile("w+") as tmp:
        tmp.write(
            f"Press {click.style('F1', fg='red')} for help -- {click.style('Ctrl-v', fg='red')} for preview -- {click.style('Ctrl-r', fg='red')} to reload -- {click.style('Ctrl-a', fg='red')} for actions\n"
        )

        def get_max_length(field_path, default_value=0):
            return max(
                (len(value) if value else default_value)
                for issue in issues
                if (
                    value := reduce(
                        lambda obj, key: obj.get(key)
                        if isinstance(obj, dict)
                        else None,
                        field_path.split("."),
                        issue,
                    )
                )
                is not None
            )

        max_summary_length = min(
            get_max_length("fields.summary", 0), defaults.SUMMARY_MAX_LENGTH
        )
        max_ticket_length = get_max_length("key")
        max_asignee_length = get_max_length("fields.assignee")
        max_reporter_length = get_max_length("fields.reporter")
        max_status_length = get_max_length("fields.status.name")
        fields = [
            "IT",
            "TICKET".center(max_ticket_length),
            "SUMMARY".center(max_summary_length),
            "ASSIGNEE".center(max_asignee_length),
            "REPORTER".center(max_reporter_length),
            "CREATED".center(10),
            "UPDATED".center(10),
            "STATUS".center(max_status_length),
        ]
        tmp.write(utils.colorize("cyan", "|").join(fields) + "\n")
        for issue in issues:
            ss = self._build_issue_table(
                issue,
                max_ticket_length,
                max_summary_length,
                max_asignee_length,
                max_reporter_length,
                max_status_length,
            )
            tmp.write(utils.colorize("cyan", "|").join(ss) + "\n")
        tmp.flush()

        if self.verbose:
            utils.log(
                f"Temporary file created at {tmp.name}",
                "DEBUG",
                verbose_only=True,
                verbose=self.verbose,
            )

        preview_cmd = f"{self.config.get('jayrah_path')} issue view {{2}}"
        help_cmd = f"clear;{self.config.get('jayrah_path')} help;bash -c \"read -n1 -p 'Press a key to exit'\""
        fzf_cmd = [
            "fzf",
            "-d",
            "|",
            "--ansi",
            "--header-lines=2",
            "--reverse",
            "--preview",
            preview_cmd,
            "--preview-window",
            "right:hidden:wrap",
            "--bind",
            # TODO: arguments
            f"ctrl-r:reload({self.config.get('jayrah_path')} --no-fzf -n browse {self.command})",
            "--bind",
            f"enter:execute({self.config.get('jayrah_path')} issue open {{2}})",
            "--bind",
            f"ctrl-a:execute({self.config.get('jayrah_path')} issue action {{2}})",
            "--bind",
            f"f1:execute({help_cmd})",
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

            if self.verbose and result.stdout:
                click.echo(f"User selected: {result.stdout.strip()}", err=True)

        except subprocess.CalledProcessError as e:
            click.secho(f"Error occurred: {e}", fg="red", err=True)
            return None

        return result.stdout.strip().split("\t")[0] if result.stdout else None
