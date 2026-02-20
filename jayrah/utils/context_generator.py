"""Context generator for exporting Jira board data to LLM-friendly formats."""

import json
from datetime import datetime
from typing import Any

from .. import utils


class ContextGenerator:
    """Generate comprehensive context from Jira board data for LLM consumption."""

    def __init__(
        self,
        issues_client,
        config: dict[str, Any],
        include_comments: bool = False,
        include_metadata: bool = False,
        output_format: str = "markdown",
    ):
        """Initialize the context generator.

        Args:
            issues_client: Jayrah issues client instance
            config: Jayrah configuration
            include_comments: Whether to include all comments
            include_metadata: Whether to include custom fields and metadata
            output_format: Output format ('markdown' or 'plain')
        """
        self.issues_client = issues_client
        self.config = config
        self.include_comments = include_comments
        self.include_metadata = include_metadata
        self.format = output_format
        self.verbose = config.get("verbose", False)

    def generate_board_context(self, board_name: str, jql: str, order_by: str) -> str:
        """Generate comprehensive context from board tickets.

        Args:
            board_name: Name of the board
            jql: JQL query for the board
            order_by: Order by clause

        Returns:
            Formatted context string
        """
        if self.verbose:
            utils.log(f"Generating context for board '{board_name}'")
            utils.log(f"JQL: {jql}")

        # Get all fields we want to include
        fields = self._get_fields_list()

        # Fetch all issues with comprehensive data
        issues = self.issues_client.list_issues(
            jql,
            order_by=order_by,
            limit=1000,  # Large limit to get all issues
            all_pages=True,
            fields=fields,
            use_cache=True,
        )

        if not issues:
            if self.verbose:
                utils.log("No issues found for the board")
            return self._format_no_issues(board_name)

        if self.verbose:
            utils.log(f"Found {len(issues)} issues to process")

        # Generate context content
        if self.format == "markdown":
            return self._generate_markdown_context(board_name, jql, issues)
        return self._generate_plain_context(board_name, jql, issues)

    def _get_fields_list(self) -> list[str]:
        """Get the list of fields to fetch from Jira."""
        # Base fields always included
        fields = [
            "key",
            "summary",
            "description",
            "status",
            "issuetype",
            "priority",
            "assignee",
            "reporter",
            "created",
            "updated",
            "labels",
            "components",
            "fixVersions",
            "versions",
        ]

        if self.include_comments:
            fields.append("comment")

        if self.include_metadata:
            # Add common custom fields and metadata
            fields.extend(
                [
                    "customfield_*",  # All custom fields
                    "attachment",
                    "worklog",
                    "resolution",
                    "resolutiondate",
                    "duedate",
                    "environment",
                    "timeestimate",
                    "timeoriginalestimate",
                    "timespent",
                    "progress",
                    "votes",
                    "watches",
                ]
            )

        return fields

    def _generate_markdown_context(
        self, board_name: str, jql: str, issues: list[dict]
    ) -> str:
        """Generate markdown-formatted context."""
        content = []

        # Header with metadata
        content.append(f"# Jira Board Context: {board_name}")
        content.append("")
        content.append("## Overview")
        content.append("")
        content.append(
            "This document contains comprehensive information about all tickets in the Jira board."
        )
        content.append(
            "It has been specifically formatted for consumption by Large Language Models (LLMs) to provide"
        )
        content.append(
            "complete context about the project, including ticket descriptions, comments, metadata, and"
        )
        content.append("relationships between issues.")
        content.append("")
        content.append("**Purpose:** This context can be used to:")
        content.append("- Understand the current state of the project")
        content.append(
            "- Analyze patterns in ticket types, priorities, and assignments"
        )
        content.append("- Generate reports, summaries, or insights about the board")
        content.append(
            "- Answer questions about specific tickets or the project as a whole"
        )
        content.append("- Identify dependencies, blockers, or areas needing attention")
        content.append("")
        content.append("## Board Information")
        content.append("")
        content.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        content.append(f"**Board:** {board_name}")
        content.append(f"**JQL Query:** `{jql}`")
        content.append(f"**Total Issues:** {len(issues)}")
        if self.include_comments:
            content.append("**Comments:** Included")
        if self.include_metadata:
            content.append(
                "**Metadata:** Included (custom fields, time tracking, etc.)"
            )
        content.append("")

        # Table of contents
        content.append("## Table of Contents")
        content.append("")
        for i, issue in enumerate(issues, 1):
            key = issue.get("key", f"Issue-{i}")
            summary = issue.get("fields", {}).get("summary", "No summary")
            content.append(f"{i}. [{key}](#{key.lower().replace('-', '')}) - {summary}")
        content.append("")

        # Issue details
        content.append("## Issues")
        content.append("")

        for issue in issues:
            content.extend(self._format_issue_markdown(issue))
            content.append("")

        return "\n".join(content)

    def _generate_plain_context(
        self, board_name: str, jql: str, issues: list[dict]
    ) -> str:
        """Generate plain text context."""
        content = []

        # Header
        content.append(f"JIRA BOARD CONTEXT: {board_name.upper()}")
        content.append("=" * 60)
        content.append("")
        content.append("OVERVIEW:")
        content.append(
            "This document contains comprehensive information about all tickets in the Jira board."
        )
        content.append(
            "It has been specifically formatted for consumption by Large Language Models (LLMs)"
        )
        content.append(
            "to provide complete context about the project, including ticket descriptions,"
        )
        content.append("comments, metadata, and relationships between issues.")
        content.append("")
        content.append("PURPOSE: This context can be used to:")
        content.append("- Understand the current state of the project")
        content.append(
            "- Analyze patterns in ticket types, priorities, and assignments"
        )
        content.append("- Generate reports, summaries, or insights about the board")
        content.append(
            "- Answer questions about specific tickets or the project as a whole"
        )
        content.append("- Identify dependencies, blockers, or areas needing attention")
        content.append("")
        content.append("BOARD INFORMATION:")
        content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        content.append(f"Board: {board_name}")
        content.append(f"JQL Query: {jql}")
        content.append(f"Total Issues: {len(issues)}")
        if self.include_comments:
            content.append("Comments: Included")
        if self.include_metadata:
            content.append("Metadata: Included (custom fields, time tracking, etc.)")
        content.append("")

        # Issues
        for i, issue in enumerate(issues, 1):
            content.extend(self._format_issue_plain(issue, i))
            content.append("-" * 60)
            content.append("")

        return "\n".join(content)

    def _format_issue_markdown(self, issue: dict) -> list[str]:
        """Format a single issue in markdown."""
        content = []
        fields = issue.get("fields", {})
        key = issue.get("key", "Unknown")

        # Issue header
        content.append(f"### {key}")
        content.append("")

        # Basic information
        summary = fields.get("summary", "No summary")
        content.append(f"**Summary:** {summary}")
        content.append("")

        status = fields.get("status", {}).get("name", "Unknown")
        content.append(f"**Status:** {status}")

        issue_type = fields.get("issuetype", {}).get("name", "Unknown")
        content.append(f"**Type:** {issue_type}")

        priority = fields.get("priority")
        if priority:
            content.append(f"**Priority:** {priority.get('name', 'Unknown')}")

        assignee = fields.get("assignee")
        if assignee:
            assignee_name = assignee.get("displayName", assignee.get("name", "Unknown"))
            content.append(f"**Assignee:** {assignee_name}")

        reporter = fields.get("reporter")
        if reporter:
            reporter_name = reporter.get("displayName", reporter.get("name", "Unknown"))
            content.append(f"**Reporter:** {reporter_name}")

        # Dates
        created = fields.get("created")
        if created:
            content.append(f"**Created:** {self._format_date(created)}")

        updated = fields.get("updated")
        if updated:
            content.append(f"**Updated:** {self._format_date(updated)}")

        content.append("")

        # Description
        description = fields.get("description")
        if description:
            content.append("**Description:**")
            content.append("")
            content.append(self._format_description(description))
            content.append("")

        # Labels
        labels = fields.get("labels", [])
        if labels:
            content.append(f"**Labels:** {', '.join(labels)}")
            content.append("")

        # Components
        components = fields.get("components", [])
        if components:
            comp_names = [comp.get("name", "Unknown") for comp in components]
            content.append(f"**Components:** {', '.join(comp_names)}")
            content.append("")

        # Comments
        if self.include_comments:
            comments = fields.get("comment", {}).get("comments", [])
            if comments:
                content.append("**Comments:**")
                content.append("")
                for comment in comments:
                    content.extend(self._format_comment_markdown(comment))
                content.append("")

        # Custom fields and metadata
        if self.include_metadata:
            metadata = self._extract_metadata(fields)
            if metadata:
                content.append("**Metadata:**")
                content.append("")
                for meta_key, value in metadata.items():
                    content.append(f"- **{meta_key}:** {value}")
                content.append("")

        return content

    def _format_issue_plain(self, issue: dict, index: int) -> list[str]:
        """Format a single issue in plain text."""
        content = []
        fields = issue.get("fields", {})
        key = issue.get("key", "Unknown")

        # Issue header
        content.append(f"ISSUE #{index}: {key}")
        content.append("")

        # Basic information
        summary = fields.get("summary", "No summary")
        content.append(f"Summary: {summary}")

        status = fields.get("status", {}).get("name", "Unknown")
        content.append(f"Status: {status}")

        issue_type = fields.get("issuetype", {}).get("name", "Unknown")
        content.append(f"Type: {issue_type}")

        priority = fields.get("priority")
        if priority:
            content.append(f"Priority: {priority.get('name', 'Unknown')}")

        assignee = fields.get("assignee")
        if assignee:
            assignee_name = assignee.get("displayName", assignee.get("name", "Unknown"))
            content.append(f"Assignee: {assignee_name}")

        reporter = fields.get("reporter")
        if reporter:
            reporter_name = reporter.get("displayName", reporter.get("name", "Unknown"))
            content.append(f"Reporter: {reporter_name}")

        # Dates
        created = fields.get("created")
        if created:
            content.append(f"Created: {self._format_date(created)}")

        updated = fields.get("updated")
        if updated:
            content.append(f"Updated: {self._format_date(updated)}")

        content.append("")

        # Description
        description = fields.get("description")
        if description:
            content.append("DESCRIPTION:")
            content.append(self._format_description(description))
            content.append("")

        # Labels
        labels = fields.get("labels", [])
        if labels:
            content.append(f"Labels: {', '.join(labels)}")

        # Components
        components = fields.get("components", [])
        if components:
            comp_names = [comp.get("name", "Unknown") for comp in components]
            content.append(f"Components: {', '.join(comp_names)}")

        content.append("")

        # Comments
        if self.include_comments:
            comments = fields.get("comment", {}).get("comments", [])
            if comments:
                content.append("COMMENTS:")
                for i, comment in enumerate(comments, 1):
                    content.extend(self._format_comment_plain(comment, i))
                content.append("")

        # Custom fields and metadata
        if self.include_metadata:
            metadata = self._extract_metadata(fields)
            if metadata:
                content.append("METADATA:")
                for meta_key, value in metadata.items():
                    content.append(f"  {meta_key}: {value}")
                content.append("")

        return content

    def _format_comment_markdown(self, comment: dict) -> list[str]:
        """Format a comment in markdown."""
        content = []
        author = comment.get("author", {})
        author_name = author.get("displayName", author.get("name", "Unknown"))
        created = comment.get("created", "Unknown date")
        body = comment.get("body", "No content")

        content.append(f"**Comment by {author_name}** _{self._format_date(created)}_")
        content.append("")
        content.append(self._format_description(body))
        content.append("")

        return content

    def _format_comment_plain(self, comment: dict, index: int) -> list[str]:
        """Format a comment in plain text."""
        content = []
        author = comment.get("author", {})
        author_name = author.get("displayName", author.get("name", "Unknown"))
        created = comment.get("created", "Unknown date")
        body = comment.get("body", "No content")

        content.append(
            f"  Comment #{index} by {author_name} on {self._format_date(created)}:"
        )
        content.append(f"  {self._format_description(body)}")
        content.append("")

        return content

    def _format_description(self, description: Any) -> str:
        """Format description text."""
        if isinstance(description, dict):
            # Handle ADF (Atlassian Document Format)
            return self._extract_text_from_adf(description)
        if isinstance(description, str):
            return description
        return str(description) if description else "No description"

    def _extract_text_from_adf(self, adf_content: dict) -> str:
        """Extract plain text from ADF (Atlassian Document Format)."""
        if not isinstance(adf_content, dict):
            return str(adf_content)

        def extract_text(node):
            if isinstance(node, str):
                return node
            if isinstance(node, dict):
                text_parts = []
                if node.get("type") == "text":
                    return node.get("text", "")
                if "content" in node:
                    text_parts.extend(extract_text(child) for child in node["content"])
                return " ".join(text_parts)
            if isinstance(node, list):
                return " ".join(extract_text(item) for item in node)
            return ""

        return extract_text(adf_content)

    def _extract_metadata(self, fields: dict) -> dict[str, str]:
        """Extract custom fields and metadata."""
        metadata = {}

        # Time tracking
        if fields.get("timeestimate"):
            metadata["Time Estimate"] = f"{fields['timeestimate']} seconds"
        if fields.get("timespent"):
            metadata["Time Spent"] = f"{fields['timespent']} seconds"

        # Resolution
        resolution = fields.get("resolution")
        if resolution:
            metadata["Resolution"] = resolution.get("name", "Unknown")

        # Due date
        if fields.get("duedate"):
            metadata["Due Date"] = self._format_date(fields["duedate"])

        # Environment
        if fields.get("environment"):
            metadata["Environment"] = str(fields["environment"])

        # Custom fields (usually start with customfield_)
        for field_key, value in fields.items():
            if field_key.startswith("customfield_") and value is not None:
                # Try to get a human-readable value
                if isinstance(value, dict):
                    if "value" in value:
                        metadata[f"Custom Field {field_key}"] = str(value["value"])
                    elif "name" in value:
                        metadata[f"Custom Field {field_key}"] = str(value["name"])
                    else:
                        metadata[f"Custom Field {field_key}"] = json.dumps(value)
                else:
                    metadata[f"Custom Field {field_key}"] = str(value)

        return metadata

    def _format_date(self, date_str: str) -> str:
        """Format ISO date string to readable format."""
        try:
            # Parse ISO format and convert to readable format
            dt = datetime.fromisoformat(date_str)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, AttributeError):
            return str(date_str)

    def _format_no_issues(self, board_name: str) -> str:
        """Format message when no issues are found."""
        if self.format == "markdown":
            return f"""# Jira Board Context: {board_name}

## Overview

This document was generated to provide comprehensive information about all tickets in the Jira board
for consumption by Large Language Models (LLMs). However, no issues were found in this board.

## Board Information

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Board:** {board_name}
**Total Issues:** 0

No issues found in this board.
"""
        return f"""JIRA BOARD CONTEXT: {board_name.upper()}
{"=" * 60}

OVERVIEW:
This document was generated to provide comprehensive information about all tickets
in the Jira board for consumption by Large Language Models (LLMs). However, no
issues were found in this board.

BOARD INFORMATION:
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Board: {board_name}
Total Issues: 0

No issues found in this board.
"""
