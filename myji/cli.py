import sys
import click
from . import myji, utils


def main():
    try:
        myji.cli()
    except KeyboardInterrupt:
        click.secho("Operation cancelled by user", fg="yellow", err=True)
        sys.exit(1)
    except Exception as e:
        click.secho(f"Error: {e}", fg="red", err=True)
        if "--verbose" in sys.argv or "-v" in sys.argv:
            raise e
        sys.exit(1)


if __name__ == "__main__":
    main()
