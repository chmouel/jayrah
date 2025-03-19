import typing

import click

from . import defaults


def show(config):
    click.echo("Available boards:")
    for x in config.get("boards", []):
        click.secho(f"  {x.get('name')}", fg="cyan", nl=False)
        if x.get("description"):
            click.secho(f" - {x.get('description')}", italic=True, nl=False)
        click.echo()


def check(board, config) -> typing.Tuple[str, str]:
    if not board:
        show(config)
        return "", ""
    chosen_boards = [x for x in config["boards"] if x.get("name") == board]
    if board is not None and board not in [
        x.get("name") for x in chosen_boards if x.get("name") == board
    ]:
        click.secho("Invalid board: ", fg="red", err=True, nl=False)
        click.echo(f"{board}", err=True)
        show(config)
        return "", ""

    jql = chosen_boards[0].get("jql").strip() if chosen_boards else None
    if not jql:
        click.secho(f"Board {board} has no JQL defined", fg="red", err=True)
        return "", ""
    order_by = chosen_boards[0].get("order_by", defaults.ORDER_BY)
    if config.get("verbose"):
        click.echo(f"Running query: {jql} ORDER BY: {order_by}", err=True)
    return jql, order_by
