from typing import List, Optional, Union

import click
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()


def select_from_list(
    title: str,
    options: List[str],
    multi: bool = False,
    default: Optional[str] = None,
) -> Union[str, List[str]]:
    """
    Display a list of options and let the user select one or multiple items.

    Args:
        title: The title to display above the options
        options: List of options to choose from
        multi: Whether to allow multiple selections
        default: Default value to use if provided

    Returns:
        Selected option(s) as string or list of strings
    """
    if not options:
        return [] if multi else None

    # If there's only one option and no default, return it
    if len(options) == 1 and not default:
        return options[0] if not multi else options

    # Create a table for the options
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Number", style="cyan")
    table.add_column("Option", style="white")

    for idx, option in enumerate(options, 1):
        table.add_row(str(idx), option)

    # Display the title and options
    console.print(f"\n[bold]{title}[/bold]")
    console.print(table)

    if multi:
        # For multiple selection, allow comma-separated numbers
        while True:
            selection = Prompt.ask(
                "Enter numbers (comma-separated) or 'all'",
                default="all" if default == "all" else None,
            )

            if selection.lower() == "all":
                return options

            try:
                # Parse comma-separated numbers
                indices = [int(x.strip()) for x in selection.split(",")]
                # Validate indices
                if all(1 <= idx <= len(options) for idx in indices):
                    return [options[idx - 1] for idx in indices]
                console.print("[red]Invalid selection. Please try again.[/red]")
            except ValueError:
                console.print(
                    "[red]Invalid input. Please enter numbers separated by commas.[/red]"
                )
    else:
        # For single selection, just ask for a number
        while True:
            selection = Prompt.ask(
                "Enter number",
                default=str(options.index(default) + 1) if default else None,
            )
            try:
                idx = int(selection)
                if 1 <= idx <= len(options):
                    return options[idx - 1]
                console.print("[red]Invalid selection. Please try again.[/red]")
            except ValueError:
                console.print("[red]Invalid input. Please enter a number.[/red]")


def display_preview(
    title: str,
    content: str,
    width: Optional[int] = None,
) -> None:
    """
    Display a preview of content in a panel.

    Args:
        title: The title of the preview panel
        content: The content to display
        width: Optional width for the panel
    """
    panel = Panel(
        Text(content, style="white"),
        title=title,
        border_style="blue",
        width=width,
    )
    console.print(panel)


def confirm_action(message: str, default: bool = True) -> bool:
    """
    Ask for confirmation with a yes/no prompt.

    Args:
        message: The message to display
        default: Default value for the confirmation

    Returns:
        True if confirmed, False otherwise
    """
    return Confirm.ask(message, default=default)
