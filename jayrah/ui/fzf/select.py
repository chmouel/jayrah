from . import fzf_select


def issue_type(jayrah_obj):
    """Select issue type using fzf."""
    issue_types = jayrah_obj.jira.get_issue_types()
    if jayrah_obj.cmdline and jayrah_obj.cmdline.get("issuetype"):
        if jayrah_obj.cmdline_config.get("issuetype") in issue_types:
            return jayrah_obj.cmdline_config.get("issuetype")
    return fzf_select(
        "Select issue type",
        [it["name"] for it in issue_types],
        default=jayrah_obj.config.get("default_issuetype", "Story"),
    )


def priority(jayrah_obj):
    """Select priority using fzf."""
    priorities = jayrah_obj.jira.get_priorities()
    return fzf_select(
        "Select priority",
        [p["name"] for p in priorities],
        default=jayrah_obj.config.get("default_priority", "Medium"),
    )


def assignee(jayrah_obj):
    """Select assignee using fzf."""
    users = jayrah_obj.jira.get_users()
    return fzf_select(
        "Select assignee",
        [u["displayName"] for u in users],
        default=jayrah_obj.config.get("default_assignee"),
    )


def labels(jayrah_obj):
    """Select labels using fzf."""
    labels = jayrah_obj.jira.get_labels()
    return fzf_select(
        "Select labels",
        labels,
        multi=True,
        default="all" if jayrah_obj.config.get("default_labels") else None,
    )
