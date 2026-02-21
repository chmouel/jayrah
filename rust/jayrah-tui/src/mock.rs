use crate::types::{Issue, IssueComment, IssueDetail};

pub fn mock_issues(reload_count: usize) -> Vec<Issue> {
    let suffix = if reload_count == 0 {
        String::new()
    } else {
        format!(" [reload {}]", reload_count)
    };

    vec![
        Issue {
            key: "JAY-101".to_string(),
            summary: format!("Build ratatui scaffold{}", suffix),
            status: "In Progress".to_string(),
            assignee: "alice".to_string(),
        },
        Issue {
            key: "JAY-102".to_string(),
            summary: format!("Add adapter JSON contract{}", suffix),
            status: "To Do".to_string(),
            assignee: "bob".to_string(),
        },
        Issue {
            key: "JAY-103".to_string(),
            summary: format!("Wire issue detail pane{}", suffix),
            status: "Blocked".to_string(),
            assignee: "carol".to_string(),
        },
        Issue {
            key: "JAY-104".to_string(),
            summary: format!("Measure navigation latency{}", suffix),
            status: "Review".to_string(),
            assignee: "dave".to_string(),
        },
    ]
}

pub fn mock_detail_from_issue(issue: &Issue) -> IssueDetail {
    IssueDetail {
        key: issue.key.clone(),
        summary: issue.summary.clone(),
        status: issue.status.clone(),
        priority: "Mock".to_string(),
        issue_type: "Task".to_string(),
        assignee: issue.assignee.clone(),
        reporter: "mock-reporter".to_string(),
        created: "2026-02-20T00:00:00Z".to_string(),
        updated: "2026-02-20T00:00:00Z".to_string(),
        labels: vec!["mock".to_string()],
        components: vec!["tui".to_string()],
        fix_versions: Vec::new(),
        description: "Mock detail payload used while adapter data is unavailable.".to_string(),
    }
}

pub fn mock_comments_for_issue(issue_key: &str) -> Vec<IssueComment> {
    vec![
        IssueComment {
            id: format!("{issue_key}-comment-1"),
            author: "mock-user-1".to_string(),
            created: "2026-02-21T00:00:00Z".to_string(),
            body: "First mock comment for previewing the comments pane.".to_string(),
        },
        IssueComment {
            id: format!("{issue_key}-comment-2"),
            author: "mock-user-2".to_string(),
            created: "2026-02-21T00:30:00Z".to_string(),
            body: "Second mock comment with extra detail for navigation testing.".to_string(),
        },
    ]
}
