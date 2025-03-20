"""Help module for jayrah providing formatted help text."""

import shutil

import click


def get_help_text():
    """Return nicely formatted help text with colors and emojis."""
    # Get terminal width for formatting
    width = shutil.get_terminal_size().columns
    width = min(100, width)  # Cap width to 100 characters

    # Create a centered title
    title = "🌟 JayRah Help 🌟"
    centered_title = title.center(width)

    help_text = [
        click.style(centered_title, fg="bright_blue", bold=True),
        "=" * width,
        "",
        click.style("🔑 Keyboard Shortcuts:", fg="bright_yellow", bold=True),
        "",
        f"  {click.style('F1', fg='green', bold=True)}          {click.style('Show this help page', fg='white')}",
        f"  {click.style('Enter', fg='green', bold=True)}       {click.style('Open selected issue in browser', fg='white')}",
        f"  {click.style('Ctrl+V', fg='green', bold=True)}      {click.style('Toggle preview window', fg='white')}",
        f"  {click.style('Ctrl+N/P', fg='green', bold=True)}    {click.style('Navigate up/down', fg='white')}",
        f"  {click.style('Ctrl+J/K', fg='green', bold=True)}    {click.style('Scroll preview up/down', fg='white')}",
        f"  {click.style('Esc/Ctrl+C', fg='green', bold=True)}  {click.style('Exit', fg='white')}",
        f"  {click.style('Ctrl+R', fg='green', bold=True)}      {click.style('Reload', fg='white')}",
        "",
        click.style("📋 Commands:", fg="bright_yellow", bold=True),
        "",
        f"  {click.style('jayrah browse [BOARD]', fg='cyan')}    {click.style('Browse issues from a board defined in config', fg='white')}",
        f"  {click.style('jayrah create', fg='cyan')}            {click.style('Create a new issue', fg='white')}",
        f"  {click.style('jayrah issue open TICKET', fg='cyan')} {click.style('Open issue in browser', fg='white')}",
        f"  {click.style('jayrah issue view TICKET', fg='cyan')} {click.style('View issue details', fg='white')}",
        f"  {click.style('jayrah issue action TICKET', fg='cyan')} {click.style('Perform actions on an issue', fg='white')}",
        f"  {click.style('jayrah issue edit-description TICKET', fg='cyan')} {click.style('Edit issue description', fg='white')}",
        f"  {click.style('jayrah issue transition TICKET', fg='cyan')} {click.style('Change issue status', fg='white')}",
        "",
        click.style("🔍 Boards:", fg="bright_yellow", bold=True),
        "",
        f"  {click.style('Boards are defined in your config file:', fg='white')}",
        f"  {click.style('~/.config/jayrah/config.yaml', fg='bright_green')}",
        f"  {click.style('Example board configuration:', fg='white')}",
        f"  {click.style('boards:', fg='bright_green')}",
        f"  {click.style('  myissues:', fg='bright_green')}",
        f"  {click.style('    jql: "assignee = currentUser() AND resolution = Unresolved"', fg='bright_green')}",
        f"  {click.style('    order_by: "updated DESC"', fg='bright_green')}",
        "",
        click.style("🚀 Global Options:", fg="bright_yellow", bold=True),
        "",
        f"  {click.style('--no-cache, -n', fg='magenta')}  {click.style('Disable response caching', fg='white')}",
        f"  {click.style('--verbose, -v', fg='magenta')}   {click.style('Enable verbose logging', fg='white')}",
        f"  {click.style('--no-fzf', fg='magenta')}        {click.style('Output directly to stdout', fg='white')}",
        f"  {click.style('--cache-ttl', fg='magenta')}     {click.style('Set cache TTL in seconds', fg='white')}",
        "",
        click.style("💡 Tips:", fg="bright_yellow", bold=True),
        "",
        "  • Use "
        + click.style("jayrah --help", fg="bright_green")
        + " to see all available commands",
        "  • Press "
        + click.style("Ctrl+V", fg="bright_green")
        + " to toggle the preview window",
        "  • Environment variables: "
        + click.style(
            "JIRA_SERVER, JIRA_USER, JIRA_PASSWORD, JIRA_COMPONENT", fg="bright_green"
        ),
        "  • Custom boards can be defined in your config file and used with "
        + click.style("jayrah browse [BOARD]", fg="bright_green"),
        "",
        "",
    ]

    return "\n".join(help_text)
