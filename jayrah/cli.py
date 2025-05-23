import sys

import click

from . import commands, utils


def main():
    verbose = False
    if "--verbose" in sys.argv or "-v" in sys.argv:
        verbose = True

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
