"""Generate context command for exporting board tickets to markdown for LLM consumption."""

import click

from ..ui import boards
from .common import cli
from .completions import BoardType


@cli.command("gencontext")
@click.argument("board", type=BoardType())
@click.option("--output", "-o", help="Output file path (default: stdout)")
@click.option(
    "--include-comments", "-c", is_flag=True, help="Include all comments from tickets"
)
@click.option(
    "--include-metadata", "-m", is_flag=True, help="Include custom fields and metadata"
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "plain"]),
    default="markdown",
    help="Output format (default: markdown)",
)
@click.pass_obj
def gencontext(
    jayrah_obj, board, output, include_comments, include_metadata, output_format
):
    """
    Generate comprehensive context file from board tickets for LLM consumption.

    Exports all tickets from the specified board including descriptions,
    comments, and metadata in a format optimized for importing into
    NotebookLM, Gemini, or other LLM contexts.

    Example: jayrah gencontext my-board --include-comments --include-metadata
    """
    from ..utils.context_generator import ContextGenerator

    # Get board configuration
    jql, order_by = boards.check(board, jayrah_obj.config)
    if not jql or not order_by:
        return

    # Initialize context generator
    generator = ContextGenerator(
        jayrah_obj.issues_client,
        jayrah_obj.config,
        include_comments=include_comments,
        include_metadata=include_metadata,
        output_format=output_format,
    )

    # Generate context
    try:
        context_content = generator.generate_board_context(board, jql, order_by)

        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(context_content)
            click.echo(f"Context exported to {output}")
        else:
            click.echo(context_content)

    except Exception as e:
        click.secho(f"Error generating context: {e}", fg="red", err=True)
        raise click.ClickException(str(e))
