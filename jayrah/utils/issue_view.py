"""Utilities for rendering and displaying Jira issues in the terminal."""

import os
import shutil
import textwrap
from datetime import datetime

import jira2markdown

from jayrah.config import defaults

from . import adf


def get_terminal_width() -> int:
    terminal_width = None
    try:
        # Prefer FZF_PREVIEW_COLUMNS if set
        terminal_width = int(os.getenv("FZF_PREVIEW_COLUMNS", os.getenv("COLUMNS", "")))
    except (TypeError, ValueError):
        # Fallback if FZF_PREVIEW_COLUMNS or COLUMNS is not set or invalid
        terminal_width = None

    # Step 2: Use shutil.get_terminal_size() if FZF variables are not available
    if terminal_width is None:
        try:
            terminal_width = shutil.get_terminal_size((80, 20)).columns
        except OSError:
            # Final fallback to 80 characters if terminal size cannot be determined
            terminal_width = 80
    if terminal_width >= 130:
        terminal_width = 130
    elif terminal_width < 80:
        terminal_width = 80

    return terminal_width


def wrap_markdown(text):
    """Wrap markdown text to terminal width"""
    if not text:
        return ""

    terminal_width = get_terminal_width()
    lines = []
    for line in text.split("\n"):
        # Skip wrapping for code blocks and headers
        if line.endswith("```java"):
            line = "```bash"

        if line.startswith("```") or line.startswith("#"):
            lines.append(line)
        else:
            # Wrap the line to the terminal width
            wrapped_lines = textwrap.wrap(
                line,
                width=terminal_width,
            )
            lines.append("\n".join(wrapped_lines))

    return "\n".join(lines)


def format_with_rich(text):
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console(
        color_system="truecolor",
        force_terminal=True,
        width=get_terminal_width(),
    )
    md = Markdown(text, code_theme="github-dark", justify="left")
    console.print(md)


def build_issue(issue, config, comments_count):
    """Return issue in a pretty formatted view as a string"""
    fields = issue["fields"]

    # Format header
    issue_type = fields["issuetype"]["name"]
    issue_status = fields["status"]["name"]
    issue_priority = fields["priority"]["name"]

    type_emoji = defaults.ISSUE_TYPE_EMOJIS.get(issue_type, ("❓", "??"))[0]
    status_emoji = defaults.STATUS_EMOJI.get(issue_status, "❓")
    priority_emoji = defaults.PRIORITY_EMOJI.get(issue_priority, "⚪")

    plain_title = f"{type_emoji} {issue['key']}: {fields['summary']}"
    output = []

    # Add issue title
    output.append(f"# {plain_title}")

    # Start markdown table

    # Add status, priority, and type
    output.append(f"* Status: {issue_status} {status_emoji}")
    output.append(f"* Priority: {issue_priority} {priority_emoji}")
    output.append(f"* Type: {issue_type} {type_emoji}")

    # Add fix versions if available
    if fields.get("fixVersions"):
        fix_versions = [v["name"] for v in fields["fixVersions"]]
        output.append(f"* Fix Version: 📦 {', '.join(fix_versions)} ")

    # Add components if available
    if fields.get("components"):
        components = [c["name"] for c in fields["components"]]
        output.append(f"* Component: 🧩 {', '.join(components)}")

    # Add labels if available
    if fields.get("labels"):
        output.append(f"* Labels: 🏷️ {', '.join(fields['labels'])} ")

    # Add people information
    # Helper function to get user identifier - works with both v2 and v3 API
    def get_user_info(user):
        # Try to get username from emailAddress or name, falling back to displayName if needed
        if "emailAddress" in user:
            return user["emailAddress"].split("@")[0].split("+")[0]
        if "name" in user:
            return user["name"]
        if "displayName" in user:
            return user["displayName"]
        # If no good identifier, fall back to account ID only as last resort
        return user.get("accountId", "Unknown")

    if fields.get("assignee"):
        assignee = fields["assignee"]
        output.append(
            f"* Assignee: 👤 {assignee['displayName']} <{get_user_info(assignee)}>"
        )

    reporter = fields["reporter"]
    output.append(
        f"* Reporter: 📣 {reporter['displayName']} <{get_user_info(reporter)}>"
    )

    # Add dates
    date_format = "%Y-%m-%dT%H:%M:%S.%f%z"
    created_date = datetime.strptime(fields["created"], date_format)
    updated_date = datetime.strptime(fields["updated"], date_format)

    output.append(f"* Created: 📅 {created_date.strftime('%Y-%m-%d %H:%M:%S')}")
    output.append(f"* Updated: 🔄 {updated_date.strftime('%Y-%m-%d %H:%M:%S')}")

    # Show custom fields if present and not empty
    custom_fields = config.get("custom_fields", [])
    for cf in custom_fields:
        field_id = cf.get("field")
        field_name = cf.get("name", field_id)
        field_type = cf.get("type", "string")
        if field_id and fields.get(field_id):
            value = fields[field_id]
            # If value is a list, join, else str
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value if v)
            if value:
                if field_type == "text":
                    output.append(f"* {field_name}:\n```\n{value}\n```")
                elif field_type == "url":
                    output.append(f"* {field_name}: [{value}]({value})")
                else:
                    output.append(f"* {field_name}: {value}")

    # Description
    markdown_description = "\n## Description\n"

    if fields.get("description"):
        # Handle v3 API description format which might be a dict (ADF format)
        description_text = fields["description"]

        # First, check for the v3 API format with "raw" key
        if isinstance(description_text, dict) and "raw" in description_text:
            description_text = description_text["raw"]
        # Then, check if it's ADF format (has type, content, etc.)
        elif (
            isinstance(description_text, dict)
            and "type" in description_text
            and "content" in description_text
        ):
            # Import here to avoid circular imports
            description_text = adf.extract_text_from_adf(description_text)

        if description_text and isinstance(description_text, str):
            markdown_description += jira2markdown.convert(description_text)
            # Replace the first header with a second-level header but only on first line
            markdown_description_parts = markdown_description.split("\n", 1)
            if len(markdown_description_parts) > 1:
                markdown_description = (
                    markdown_description_parts[0].replace("#", "")
                    + "\n"
                    + markdown_description_parts[1]
                )
        else:
            markdown_description += "No detailed description provided"
    else:
        markdown_description += "No description provided"

    # Comments
    if comments_count > 0 and "comment" in fields and fields["comment"]["comments"]:
        comments = fields["comment"]["comments"]
        total = fields["comment"]["total"]
        shown = min(comments_count, total)

        markdown_description += f"\n\n## 💬 Comments ({shown} of {total})"

        for i, comment in enumerate(comments[:comments_count]):
            author = comment["author"]["displayName"]
            created = datetime.strptime(comment["created"], date_format).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            markdown_description += f"\n\n### Comment {i + 1} - {author} ({created})"

            # Convert Jira content to markdown
            # v3 API may have "body" or "body.raw" for comment content
            comment_body = comment.get("body", "")

            # Handle v3 API format with "raw" key
            if isinstance(comment_body, dict) and "raw" in comment_body:
                comment_body = comment_body["raw"]
            # Handle ADF format
            elif (
                isinstance(comment_body, dict)
                and "type" in comment_body
                and "content" in comment_body
            ):
                # Import here to avoid circular imports
                comment_body = adf.extract_text_from_adf(comment_body)

            if comment_body and isinstance(comment_body, str):
                comment_content = jira2markdown.convert(comment_body)
                markdown_description += "\n\n" + comment_content
            else:
                markdown_description += "\n\n[No comment content available]"

    return "\n".join(output), markdown_description
