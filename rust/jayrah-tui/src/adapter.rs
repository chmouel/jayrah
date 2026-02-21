use anyhow::{anyhow, Result};
use jayrah_config::{resolve_current_user_jql, CustomFieldConfig, JayrahConfig};
use jayrah_jira::{
    DetailIssue, IssueComment as JiraIssueComment, IssueTransition as JiraIssueTransition,
    JiraClient, ListIssue,
};

use crate::types::{
    AdapterSource, BoardEntry, CustomFieldEntry, Issue, IssueComment, IssueDetail, IssueTransition,
};

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

pub fn load_issue_comments_from_adapter(key: &str) -> Result<Vec<IssueComment>> {
    let (_, client) = load_runtime()?;
    let comments = client.get_issue_comments(key)?;
    Ok(comments.into_iter().map(map_issue_comment).collect())
}

pub fn add_issue_comment_from_adapter(key: &str, body: &str) -> Result<()> {
    let (_, client) = load_runtime()?;
    client.add_issue_comment(key, body)
}

pub fn load_issue_transitions_from_adapter(key: &str) -> Result<Vec<IssueTransition>> {
    let (_, client) = load_runtime()?;
    let transitions = client.get_issue_transitions(key)?;
    Ok(transitions.into_iter().map(map_issue_transition).collect())
}

pub fn apply_issue_transition_from_adapter(key: &str, transition_id: &str) -> Result<()> {
    let (_, client) = load_runtime()?;
    client.transition_issue(key, transition_id)
}

pub fn update_issue_summary_from_adapter(key: &str, summary: &str) -> Result<()> {
    let (_, client) = load_runtime()?;
    client.update_issue_summary(key, summary)
}

pub fn update_issue_description_from_adapter(key: &str, description: &str) -> Result<()> {
    let (_, client) = load_runtime()?;
    client.update_issue_description(key, description)
}

pub fn update_issue_labels_from_adapter(key: &str, labels: &[String]) -> Result<()> {
    let (_, client) = load_runtime()?;
    client.update_issue_labels(key, labels)
}

pub fn update_issue_components_from_adapter(key: &str, components: &[String]) -> Result<()> {
    let (_, client) = load_runtime()?;
    client.update_issue_components(key, components)
}

pub fn load_custom_fields_from_adapter() -> Result<Vec<CustomFieldEntry>> {
    let config = load_config()?;
    Ok(load_custom_fields_from_config(config))
}

pub fn update_custom_field_from_adapter(
    key: &str,
    field: &CustomFieldEntry,
    value: &str,
) -> Result<()> {
    let (_, client) = load_runtime()?;
    client.update_issue_custom_field(key, &field.field_id, &field.field_type, value)
}

pub fn load_boards_from_adapter() -> Result<Vec<BoardEntry>> {
    let config = load_config()?;
    Ok(load_boards_from_config(config))
}

fn load_runtime() -> Result<(JayrahConfig, JiraClient)> {
    let config = load_config()?;
    let client = JiraClient::from_config(&config)?;
    Ok((config, client))
}

fn load_config() -> Result<JayrahConfig> {
    JayrahConfig::load_default()
}

fn load_boards_from_config(config: JayrahConfig) -> Vec<BoardEntry> {
    config
        .boards
        .into_iter()
        .map(|board| BoardEntry {
            name: board.name,
            description: board
                .description
                .unwrap_or_else(|| "<no description>".to_string()),
        })
        .collect()
}

fn load_custom_fields_from_config(config: JayrahConfig) -> Vec<CustomFieldEntry> {
    config
        .custom_fields
        .into_iter()
        .map(map_custom_field_config)
        .collect()
}

fn map_custom_field_config(field: CustomFieldConfig) -> CustomFieldEntry {
    CustomFieldEntry {
        name: field.name,
        field_id: field.field,
        field_type: field.field_type,
        description: field
            .description
            .unwrap_or_else(|| "<no description>".to_string()),
    }
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

fn map_issue_comment(comment: JiraIssueComment) -> IssueComment {
    IssueComment {
        id: comment.id,
        author: comment.author.unwrap_or_else(|| "Unknown".to_string()),
        created: comment.created.unwrap_or_else(|| "Unknown".to_string()),
        body: if comment.body.is_empty() {
            "<no comment body>".to_string()
        } else {
            comment.body
        },
    }
}

fn map_issue_transition(transition: JiraIssueTransition) -> IssueTransition {
    IssueTransition {
        id: transition.id,
        name: transition
            .name
            .unwrap_or_else(|| "Unknown transition".to_string()),
        to_status: transition
            .to_status
            .unwrap_or_else(|| "Unknown status".to_string()),
        description: transition
            .description
            .unwrap_or_else(|| "<no description>".to_string()),
    }
}

#[cfg(test)]
mod tests {
    use jayrah_config::{BoardConfig, CustomFieldConfig, JayrahConfig};
    use jayrah_jira::{
        DetailIssue, IssueComment as JiraIssueComment, IssueTransition as JiraIssueTransition,
        ListIssue,
    };

    use super::{
        load_boards_from_config, load_custom_fields_from_config, map_issue, map_issue_comment,
        map_issue_detail, map_issue_transition, resolve_source_jql,
    };
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
    fn maps_comment_defaults() {
        let comment = map_issue_comment(JiraIssueComment {
            id: "1000".to_string(),
            author: None,
            created: None,
            body: String::new(),
        });

        assert_eq!(comment.author, "Unknown");
        assert_eq!(comment.created, "Unknown");
        assert_eq!(comment.body, "<no comment body>");
    }

    #[test]
    fn maps_transition_defaults() {
        let transition = map_issue_transition(JiraIssueTransition {
            id: "31".to_string(),
            name: None,
            to_status: None,
            description: None,
        });

        assert_eq!(transition.name, "Unknown transition");
        assert_eq!(transition.to_status, "Unknown status");
        assert_eq!(transition.description, "<no description>");
    }

    #[test]
    fn loads_boards_from_config_with_default_description() {
        let config = JayrahConfig {
            jira_server: None,
            jira_user: None,
            jira_password: None,
            api_version: None,
            auth_method: None,
            insecure: false,
            boards: vec![BoardConfig {
                name: "demo".to_string(),
                jql: "project = DEMO".to_string(),
                order_by: None,
                description: None,
            }],
            custom_fields: vec![],
        };

        let boards = load_boards_from_config(config);
        assert_eq!(boards.len(), 1);
        assert_eq!(boards[0].name, "demo");
        assert_eq!(boards[0].description, "<no description>");
    }

    #[test]
    fn loads_custom_fields_from_config() {
        let config = JayrahConfig {
            jira_server: None,
            jira_user: None,
            jira_password: None,
            api_version: None,
            auth_method: None,
            insecure: false,
            boards: vec![],
            custom_fields: vec![CustomFieldConfig {
                name: "Story Points".to_string(),
                field: "customfield_10016".to_string(),
                field_type: "number".to_string(),
                description: None,
            }],
        };

        let fields = load_custom_fields_from_config(config);
        assert_eq!(fields.len(), 1);
        assert_eq!(fields[0].name, "Story Points");
        assert_eq!(fields[0].field_id, "customfield_10016");
        assert_eq!(fields[0].description, "<no description>");
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
            custom_fields: vec![],
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
