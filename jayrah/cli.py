"""CLI entry point for the Jayrah Jira tool."""

import sys

import click

from . import commands, utils


def main():
    verbose = False
    if "--verbose" in sys.argv or "-v" in sys.argv:
        verbose = True

    if "-h" in sys.argv:
        sys.argv.remove("-h")
        sys.argv.append("--help")

    args = []
    for arg in sys.argv:
        if arg.startswith("-"):
            continue
        args.append(arg)
    if len(args) == 1:
        sys.argv.append("browse")

    try:
        # pylint: disable=no-value-for-parameter
        commands.cli()
    except KeyboardInterrupt:
        click.secho("Operation cancelled by user", fg="yellow")
        sys.exit(1)
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        if verbose:
            utils.log("Verbose mode enabled. Full error details:")
            raise e
        sys.exit(1)


if __name__ == "__main__":
    main()
