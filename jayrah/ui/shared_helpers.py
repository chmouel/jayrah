"""Helpers shared between TUI and Web UI, with no TUI dependencies."""

from jayrah import utils
from jayrah.config import defaults


def get_row_data_for_issue(issue: dict) -> tuple:
    issue_type = issue["fields"]["issuetype"]["name"]
    issue_type = defaults.ISSUE_TYPE_EMOJIS.get(issue_type, (issue_type[:4],))[0]
    key = issue["key"]
    summary = issue["fields"]["summary"]
    if len(summary) > defaults.SUMMARY_MAX_LENGTH:
        summary = f"{summary[: defaults.SUMMARY_MAX_LENGTH - 1]}…"
    assignee = "None"
    if assignee_field := issue["fields"].get("assignee"):
        assignee = utils.parse_email(assignee_field)
    reporter = utils.parse_email(issue["fields"].get("reporter", ""))
    created = utils.show_time(issue["fields"].get("created", ""))
    updated = utils.show_time(issue["fields"].get("updated", ""))
    status = issue["fields"]["status"]["name"]
    return (
        issue_type,
        key,
        summary,
        status,
        assignee,
        reporter,
        created,
        updated,
    )


def filter_issues_by_text(issues: list, search_text: str) -> list:
    if not search_text.strip():
        return issues
    filtered_issues = []
    search_text = search_text.lower()
    for issue in issues:
        issue_key = issue["key"].lower()
        summary = issue["fields"]["summary"].lower()
        assignee = "none"
        if assignee_field := issue["fields"].get("assignee"):
            assignee = utils.parse_email(assignee_field).lower()
        reporter = utils.parse_email(issue["fields"].get("reporter", "")).lower()
        status = issue["fields"]["status"]["name"].lower()
        if (
            search_text in issue_key
            or search_text in summary
            or search_text in assignee
            or search_text in reporter
            or search_text in status
        ):
            filtered_issues.append(issue)
    return filtered_issues
