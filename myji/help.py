"""Help module for myji providing formatted help text."""

import shutil

import click


def get_help_text():
    """Return nicely formatted help text with colors and emojis."""
    # Get terminal width for formatting
    width = shutil.get_terminal_size().columns
    width = min(100, width)  # Cap width to 100 characters

    # Create a centered title
    title = "🌟 MyJi Help 🌟"
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
        f"  {click.style('myj myissue', fg='cyan')}       {click.style('List my current issues', fg='white')}",
        f"  {click.style('myj myinprogress', fg='cyan')}  {click.style('List my in-progress issues', fg='white')}",
        f"  {click.style('myj pac-current', fg='cyan')}   {click.style('List current PAC issues', fg='white')}",
        f"  {click.style('myj pac-create', fg='cyan')}    {click.style('Create a new PAC issue', fg='white')}",
        f"  {click.style('myj git-branch', fg='cyan')}    {click.style('Generate git branch name from issue', fg='white')}",
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
        + click.style("myj --help", fg="bright_green")
        + " to see all available commands",
        "  • Press "
        + click.style("Ctrl+V", fg="bright_green")
        + " to toggle the preview window",
        "  • Environment variables: "
        + click.style("JIRA_SERVER, JIRA_API_TOKEN, JIRA_COMPONENT", fg="bright_green"),
        "",
        "",
    ]

    return "\n".join(help_text)
