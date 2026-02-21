use anyhow::{anyhow, Result};
use jayrah_config::{resolve_current_user_jql, JayrahConfig};
use jayrah_jira::{DetailIssue, JiraClient, ListIssue};

use crate::types::{AdapterSource, Issue, IssueDetail};

const SEARCH_PAGE_SIZE: usize = 200;
const SEARCH_FIELDS: [&str; 9] = [
    "key",
    "summary",
    "status",
    "priority",
    "issuetype",
    "assignee",
    "reporter",
    "created",
    "updated",
];

pub fn load_issues_from_adapter(source: &AdapterSource) -> Result<Vec<Issue>> {
    let (config, client) = load_runtime()?;
    let jql = resolve_source_jql(source, &config)?;
    let issues = client.search_issues_all(&jql, SEARCH_PAGE_SIZE, &SEARCH_FIELDS)?;

    Ok(issues.into_iter().map(map_issue).collect())
}

pub fn load_issue_detail_from_adapter(key: &str) -> Result<IssueDetail> {
    let (_, client) = load_runtime()?;
    let detail = client.get_issue_detail(key)?;
    Ok(map_issue_detail(detail))
}

pub fn open_issue_in_browser(key: &str) -> Result<()> {
    let (config, _) = load_runtime()?;
    let url = config.issue_url(key)?;
    webbrowser::open(&url)?;
    Ok(())
}

fn load_runtime() -> Result<(JayrahConfig, JiraClient)> {
    let config = JayrahConfig::load_default()?;
    let client = JiraClient::from_config(&config)?;
    Ok((config, client))
}

fn resolve_source_jql(source: &AdapterSource, config: &JayrahConfig) -> Result<String> {
    if let Some(raw_query) = source.query.as_deref() {
        let query = raw_query.trim();
        if query.is_empty() {
            return Err(anyhow!("JQL query cannot be empty"));
        }
        return Ok(resolve_current_user_jql(query, config.jira_user.as_deref()));
    }

    let board = config.resolve_board(source.board.as_deref())?;
    let mut jql = board.jql.trim().to_string();
    if jql.is_empty() {
        return Err(anyhow!("board '{}' has no JQL query", board.name));
    }

    if let Some(order_by) = board.order_by.as_deref() {
        if !jql.to_ascii_lowercase().contains("order by") && !order_by.trim().is_empty() {
            jql = format!("{jql} ORDER BY {}", order_by.trim());
        }
    }

    Ok(resolve_current_user_jql(&jql, config.jira_user.as_deref()))
}

fn map_issue(issue: ListIssue) -> Issue {
    Issue {
        key: issue.key,
        summary: issue.summary.unwrap_or_else(|| "<no summary>".to_string()),
        status: issue.status.unwrap_or_else(|| "Unknown".to_string()),
        assignee: issue.assignee.unwrap_or_else(|| "Unassigned".to_string()),
    }
}

fn map_issue_detail(issue: DetailIssue) -> IssueDetail {
    IssueDetail {
        key: issue.key,
        summary: issue.summary.unwrap_or_else(|| "<no summary>".to_string()),
        status: issue.status.unwrap_or_else(|| "Unknown".to_string()),
        priority: issue.priority.unwrap_or_else(|| "Unknown".to_string()),
        issue_type: issue.issue_type.unwrap_or_else(|| "Unknown".to_string()),
        assignee: issue.assignee.unwrap_or_else(|| "Unassigned".to_string()),
        reporter: issue.reporter.unwrap_or_else(|| "Unknown".to_string()),
        created: issue.created.unwrap_or_else(|| "Unknown".to_string()),
        updated: issue.updated.unwrap_or_else(|| "Unknown".to_string()),
        labels: issue.labels,
        components: issue.components,
        fix_versions: issue.fix_versions,
        description: issue.description,
    }
}

#[cfg(test)]
mod tests {
    use jayrah_config::{BoardConfig, JayrahConfig};
    use jayrah_jira::{DetailIssue, ListIssue};

    use super::{map_issue, map_issue_detail, resolve_source_jql};
    use crate::types::AdapterSource;

    #[test]
    fn maps_list_issue_defaults() {
        let issue = map_issue(ListIssue {
            key: "DEMO-1".to_string(),
            summary: None,
            status: None,
            assignee: None,
        });

        assert_eq!(issue.summary, "<no summary>");
        assert_eq!(issue.status, "Unknown");
        assert_eq!(issue.assignee, "Unassigned");
    }

    #[test]
    fn maps_detail_issue_fields() {
        let issue = map_issue_detail(DetailIssue {
            key: "DEMO-1".to_string(),
            summary: Some("Hello".to_string()),
            status: Some("In Progress".to_string()),
            priority: Some("Major".to_string()),
            issue_type: Some("Bug".to_string()),
            assignee: Some("Alice".to_string()),
            reporter: Some("Bob".to_string()),
            created: Some("2026-01-01".to_string()),
            updated: Some("2026-01-02".to_string()),
            labels: vec!["a".to_string()],
            components: vec!["core".to_string()],
            fix_versions: vec!["1.0".to_string()],
            description: "detail".to_string(),
        });

        assert_eq!(issue.key, "DEMO-1");
        assert_eq!(issue.priority, "Major");
        assert_eq!(issue.components, vec!["core"]);
        assert_eq!(issue.fix_versions, vec!["1.0"]);
        assert_eq!(issue.description, "detail");
    }

    #[test]
    fn resolves_board_jql_with_order_by_and_current_user() {
        let config = JayrahConfig {
            jira_server: Some("https://jira.example.com".to_string()),
            jira_user: Some("alice@example.com".to_string()),
            jira_password: Some("token".to_string()),
            api_version: Some("2".to_string()),
            auth_method: Some("bearer".to_string()),
            insecure: false,
            boards: vec![BoardConfig {
                name: "myissue".to_string(),
                jql: "assignee = currentUser()".to_string(),
                order_by: Some("updated".to_string()),
                description: None,
            }],
        };
        let source = AdapterSource {
            board: Some("myissue".to_string()),
            query: None,
            mock_only: false,
        };

        let resolved = resolve_source_jql(&source, &config).expect("resolved");
        assert_eq!(
            resolved,
            r#"assignee = "alice@example.com" ORDER BY updated"#
        );
    }
}
