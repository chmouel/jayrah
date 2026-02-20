use std::process::Command;

use anyhow::{bail, Result};
use serde::Deserialize;

use crate::types::{AdapterSource, Issue, IssueDetail};

#[derive(Debug, Deserialize)]
struct BrowseListPayload {
    issues: Vec<BrowseIssue>,
}

#[derive(Debug, Deserialize)]
struct BrowseIssue {
    key: String,
    #[serde(default)]
    summary: String,
    #[serde(default)]
    status: Option<String>,
    #[serde(default)]
    assignee: Option<String>,
}

#[derive(Debug, Deserialize)]
struct IssueShowPayload {
    issue: IssueShowIssue,
}

#[derive(Debug, Deserialize)]
struct IssueShowIssue {
    key: String,
    #[serde(default)]
    summary: String,
    #[serde(default)]
    status: Option<String>,
    #[serde(default)]
    priority: Option<String>,
    #[serde(default)]
    issue_type: Option<String>,
    #[serde(default)]
    assignee: Option<String>,
    #[serde(default)]
    reporter: Option<String>,
    #[serde(default)]
    created: Option<String>,
    #[serde(default)]
    updated: Option<String>,
    #[serde(default)]
    labels: Vec<String>,
    #[serde(default)]
    components: Vec<String>,
    #[serde(default)]
    fix_versions: Vec<String>,
    #[serde(default)]
    description: String,
}

pub fn load_issues_from_adapter(source: &AdapterSource) -> Result<Vec<Issue>> {
    let mut command = Command::new("uv");
    command.args(["run", "jayrah", "cli", "browse-list", "--limit", "200"]);

    if let Some(query) = &source.query {
        command.args(["--query", query]);
    } else if let Some(board) = &source.board {
        command.arg(board);
    }

    let output = command.output()?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        bail!(
            "status={} stderr='{}' stdout='{}'",
            output.status,
            stderr,
            stdout
        );
    }

    parse_issue_list(&output.stdout)
}

pub fn load_issue_detail_from_adapter(key: &str) -> Result<IssueDetail> {
    let output = Command::new("uv")
        .args(["run", "jayrah", "cli", "issue-show", key])
        .output()?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
        bail!(
            "status={} stderr='{}' stdout='{}'",
            output.status,
            stderr,
            stdout
        );
    }

    parse_issue_detail(&output.stdout)
}

pub fn open_issue_in_browser(key: &str) -> Result<()> {
    let output = Command::new("uv")
        .args(["run", "jayrah", "cli", "open", key])
        .output()?;

    if output.status.success() {
        return Ok(());
    }

    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    bail!(
        "status={} stderr='{}' stdout='{}'",
        output.status,
        stderr,
        stdout
    );
}

fn parse_issue_list(bytes: &[u8]) -> Result<Vec<Issue>> {
    let payload: BrowseListPayload = serde_json::from_slice(bytes)?;

    Ok(payload
        .issues
        .into_iter()
        .map(|issue| Issue {
            key: issue.key,
            summary: if issue.summary.is_empty() {
                "<no summary>".to_string()
            } else {
                issue.summary
            },
            status: issue.status.unwrap_or_else(|| "Unknown".to_string()),
            assignee: issue.assignee.unwrap_or_else(|| "Unassigned".to_string()),
        })
        .collect())
}

fn parse_issue_detail(bytes: &[u8]) -> Result<IssueDetail> {
    let payload: IssueShowPayload = serde_json::from_slice(bytes)?;
    let issue = payload.issue;

    Ok(IssueDetail {
        key: issue.key,
        summary: if issue.summary.is_empty() {
            "<no summary>".to_string()
        } else {
            issue.summary
        },
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
    })
}

#[cfg(test)]
mod tests {
    use super::{parse_issue_detail, parse_issue_list};

    #[test]
    fn parses_issue_list_payload() {
        let payload = br#"{"issues":[{"key":"DEMO-1","summary":"Hello","status":"In Progress","assignee":"Alice"}]}"#;
        let issues = parse_issue_list(payload).expect("issues");

        assert_eq!(issues.len(), 1);
        assert_eq!(issues[0].key, "DEMO-1");
        assert_eq!(issues[0].summary, "Hello");
        assert_eq!(issues[0].status, "In Progress");
        assert_eq!(issues[0].assignee, "Alice");
    }

    #[test]
    fn parses_issue_detail_payload() {
        let payload = br#"{"issue":{"key":"DEMO-1","summary":"Hello","status":"In Progress","priority":"Major","issue_type":"Bug","assignee":"Alice","reporter":"Bob","created":"2026-01-01","updated":"2026-01-02","labels":["a"],"components":["core"],"fix_versions":["1.0"],"description":"detail"}}"#;

        let issue = parse_issue_detail(payload).expect("issue detail");
        assert_eq!(issue.key, "DEMO-1");
        assert_eq!(issue.priority, "Major");
        assert_eq!(issue.components, vec!["core"]);
        assert_eq!(issue.fix_versions, vec!["1.0"]);
        assert_eq!(issue.description, "detail");
    }
}
