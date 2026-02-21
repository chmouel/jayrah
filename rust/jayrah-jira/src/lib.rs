use std::time::Duration;

use anyhow::{anyhow, bail, Context, Result};
use jayrah_config::JayrahConfig;
use reqwest::blocking::{Client, RequestBuilder};
use serde::Deserialize;
use serde_json::{json, Value};

const REQUEST_TIMEOUT_SECS: u64 = 30;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ListIssue {
    pub key: String,
    pub summary: Option<String>,
    pub status: Option<String>,
    pub assignee: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DetailIssue {
    pub key: String,
    pub summary: Option<String>,
    pub status: Option<String>,
    pub priority: Option<String>,
    pub issue_type: Option<String>,
    pub assignee: Option<String>,
    pub reporter: Option<String>,
    pub created: Option<String>,
    pub updated: Option<String>,
    pub labels: Vec<String>,
    pub components: Vec<String>,
    pub fix_versions: Vec<String>,
    pub description: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct IssueComment {
    pub id: String,
    pub author: Option<String>,
    pub created: Option<String>,
    pub body: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct IssueTransition {
    pub id: String,
    pub name: Option<String>,
    pub to_status: Option<String>,
    pub description: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
enum AuthMode {
    Basic { user: String, password: String },
    Bearer { token: String },
}

pub struct JiraClient {
    api_version: String,
    base_url: String,
    http: Client,
    auth_mode: AuthMode,
}

#[derive(Deserialize)]
struct SearchPayload {
    #[serde(default)]
    issues: Vec<IssuePayload>,
    #[serde(default)]
    total: usize,
}

#[derive(Default, Deserialize)]
struct CommentsPayload {
    #[serde(default)]
    comments: Vec<CommentPayload>,
}

#[derive(Default, Deserialize)]
struct TransitionsPayload {
    #[serde(default)]
    transitions: Vec<TransitionPayload>,
}

#[derive(Deserialize)]
struct IssuePayload {
    key: String,
    #[serde(default)]
    fields: IssueFields,
}

#[derive(Default, Deserialize)]
struct IssueFields {
    summary: Option<String>,
    status: Option<NameLike>,
    priority: Option<NameLike>,
    issuetype: Option<NameLike>,
    assignee: Option<UserLike>,
    reporter: Option<UserLike>,
    created: Option<String>,
    updated: Option<String>,
    #[serde(default)]
    labels: Vec<String>,
    #[serde(default)]
    components: Vec<NameLike>,
    #[serde(rename = "fixVersions", default)]
    fix_versions: Vec<NameLike>,
    description: Option<Value>,
}

#[derive(Default, Deserialize)]
struct NameLike {
    name: Option<String>,
}

#[derive(Default, Deserialize)]
struct UserLike {
    #[serde(rename = "displayName")]
    display_name: Option<String>,
    name: Option<String>,
    #[serde(rename = "emailAddress")]
    email_address: Option<String>,
}

#[derive(Default, Deserialize)]
struct StatusLike {
    name: Option<String>,
    description: Option<String>,
}

#[derive(Default, Deserialize)]
struct CommentPayload {
    id: Option<String>,
    author: Option<UserLike>,
    created: Option<String>,
    body: Option<Value>,
}

#[derive(Default, Deserialize)]
struct TransitionPayload {
    id: Option<String>,
    name: Option<String>,
    to: Option<StatusLike>,
}

impl JiraClient {
    pub fn from_config(config: &JayrahConfig) -> Result<Self> {
        let server = config
            .jira_server
            .as_deref()
            .ok_or_else(|| anyhow!("jira_server not configured"))?;
        let api_version = config.api_version().to_string();
        let auth_mode = parse_auth_mode(config)?;

        let http = Client::builder()
            .danger_accept_invalid_certs(config.insecure)
            .timeout(Duration::from_secs(REQUEST_TIMEOUT_SECS))
            .build()
            .with_context(|| "failed to build Jira HTTP client")?;

        Ok(Self {
            api_version: api_version.clone(),
            base_url: format!("{server}/rest/api/{api_version}"),
            http,
            auth_mode,
        })
    }

    pub fn search_issues_all(
        &self,
        jql: &str,
        max_results: usize,
        fields: &[&str],
    ) -> Result<Vec<ListIssue>> {
        let mut issues = Vec::new();
        let mut start_at = 0usize;

        loop {
            let page = self.search_issues_page(jql, start_at, max_results, fields)?;
            let page_len = page.issues.len();
            issues.extend(page.issues.into_iter().map(into_list_issue));

            if page_len == 0 || start_at + max_results >= page.total {
                break;
            }
            start_at += max_results;
        }

        Ok(issues)
    }

    pub fn get_issue_detail(&self, key: &str) -> Result<DetailIssue> {
        let endpoint = format!("{}/issue/{}", self.base_url, key);
        let fields = [
            "key",
            "summary",
            "status",
            "priority",
            "issuetype",
            "assignee",
            "reporter",
            "created",
            "updated",
            "labels",
            "components",
            "fixVersions",
            "description",
        ]
        .join(",");

        let response = self
            .with_auth(self.http.get(endpoint))
            .query(&[("fields", fields)])
            .send()
            .with_context(|| format!("failed to fetch issue detail for {}", key))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().unwrap_or_default();
            bail!(
                "jira detail request failed: status={} body={}",
                status,
                body
            );
        }

        let payload: IssuePayload = response
            .json()
            .with_context(|| "failed to decode Jira issue detail response")?;
        Ok(into_detail_issue(payload))
    }

    pub fn get_issue_comments(&self, key: &str) -> Result<Vec<IssueComment>> {
        let endpoint = format!("{}/issue/{}/comment", self.base_url, key);
        let response = self
            .with_auth(self.http.get(endpoint))
            .send()
            .with_context(|| format!("failed to fetch comments for {}", key))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().unwrap_or_default();
            bail!(
                "jira comment list request failed: status={} body={}",
                status,
                body
            );
        }

        let payload: CommentsPayload = response
            .json()
            .with_context(|| "failed to decode Jira comment list response")?;
        Ok(payload
            .comments
            .into_iter()
            .map(into_issue_comment)
            .collect())
    }

    pub fn add_issue_comment(&self, key: &str, body: &str) -> Result<()> {
        let trimmed = body.trim();
        if trimmed.is_empty() {
            bail!("comment body cannot be empty");
        }

        let endpoint = format!("{}/issue/{}/comment", self.base_url, key);
        let response = self
            .with_auth(self.http.post(endpoint))
            .json(&self.comment_body_payload(trimmed))
            .send()
            .with_context(|| format!("failed to add comment for {}", key))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().unwrap_or_default();
            bail!(
                "jira comment create request failed: status={} body={}",
                status,
                body
            );
        }

        Ok(())
    }

    pub fn get_issue_transitions(&self, key: &str) -> Result<Vec<IssueTransition>> {
        let endpoint = format!("{}/issue/{}/transitions", self.base_url, key);
        let response = self
            .with_auth(self.http.get(endpoint))
            .send()
            .with_context(|| format!("failed to fetch transitions for {}", key))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().unwrap_or_default();
            bail!(
                "jira transition list request failed: status={} body={}",
                status,
                body
            );
        }

        let payload: TransitionsPayload = response
            .json()
            .with_context(|| "failed to decode Jira transition list response")?;
        Ok(payload
            .transitions
            .into_iter()
            .map(into_issue_transition)
            .collect())
    }

    pub fn transition_issue(&self, key: &str, transition_id: &str) -> Result<()> {
        let trimmed = transition_id.trim();
        if trimmed.is_empty() {
            bail!("transition_id cannot be empty");
        }

        let endpoint = format!("{}/issue/{}/transitions", self.base_url, key);
        let response = self
            .with_auth(self.http.post(endpoint))
            .json(&json!({
                "transition": {"id": trimmed}
            }))
            .send()
            .with_context(|| format!("failed to transition issue {}", key))?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().unwrap_or_default();
            bail!(
                "jira transition apply request failed: status={} body={}",
                status,
                body
            );
        }

        Ok(())
    }

    fn search_issues_page(
        &self,
        jql: &str,
        start_at: usize,
        max_results: usize,
        fields: &[&str],
    ) -> Result<SearchPayload> {
        let endpoint = format!("{}/{}", self.base_url, self.search_endpoint());
        let fields_arg = fields.join(",");
        let response = self
            .with_auth(self.http.get(endpoint))
            .query(&[
                ("jql", jql.to_string()),
                ("startAt", start_at.to_string()),
                ("maxResults", max_results.to_string()),
                ("fields", fields_arg),
            ])
            .send()
            .with_context(|| "failed to execute Jira search request")?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().unwrap_or_default();
            bail!(
                "jira search request failed: status={} body={}",
                status,
                body
            );
        }

        response
            .json()
            .with_context(|| "failed to decode Jira search response")
    }

    fn search_endpoint(&self) -> &str {
        if self.api_version == "3" {
            "search/jql"
        } else {
            "search"
        }
    }

    fn with_auth(&self, request: RequestBuilder) -> RequestBuilder {
        match &self.auth_mode {
            AuthMode::Basic { user, password } => request.basic_auth(user, Some(password)),
            AuthMode::Bearer { token } => request.bearer_auth(token),
        }
    }

    fn comment_body_payload(&self, text: &str) -> Value {
        if self.api_version == "3" {
            json!({
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {"type": "text", "text": text}
                            ]
                        }
                    ]
                }
            })
        } else {
            json!({
                "body": text
            })
        }
    }
}

fn parse_auth_mode(config: &JayrahConfig) -> Result<AuthMode> {
    let secret = config
        .jira_password
        .as_deref()
        .ok_or_else(|| anyhow!("jira_password not configured"))?;

    match config.auth_method() {
        "basic" => {
            let user = config
                .jira_user
                .as_deref()
                .ok_or_else(|| anyhow!("jira_user not configured for basic auth"))?;
            Ok(AuthMode::Basic {
                user: user.to_string(),
                password: secret.to_string(),
            })
        }
        "bearer" => Ok(AuthMode::Bearer {
            token: secret.to_string(),
        }),
        other => bail!("unsupported auth method '{}'", other),
    }
}

fn into_list_issue(payload: IssuePayload) -> ListIssue {
    ListIssue {
        key: payload.key,
        summary: payload.fields.summary.and_then(non_empty),
        status: payload.fields.status.and_then(name_like),
        assignee: payload.fields.assignee.and_then(display_name_like),
    }
}

fn into_detail_issue(payload: IssuePayload) -> DetailIssue {
    let fields = payload.fields;
    DetailIssue {
        key: payload.key,
        summary: fields.summary.and_then(non_empty),
        status: fields.status.and_then(name_like),
        priority: fields.priority.and_then(name_like),
        issue_type: fields.issuetype.and_then(name_like),
        assignee: fields.assignee.and_then(display_name_like),
        reporter: fields.reporter.and_then(display_name_like),
        created: fields.created.and_then(non_empty),
        updated: fields.updated.and_then(non_empty),
        labels: fields
            .labels
            .into_iter()
            .filter_map(non_empty)
            .collect::<Vec<_>>(),
        components: fields
            .components
            .into_iter()
            .filter_map(name_like)
            .collect::<Vec<_>>(),
        fix_versions: fields
            .fix_versions
            .into_iter()
            .filter_map(name_like)
            .collect::<Vec<_>>(),
        description: normalize_description(fields.description),
    }
}

fn into_issue_comment(payload: CommentPayload) -> IssueComment {
    IssueComment {
        id: payload
            .id
            .and_then(non_empty)
            .unwrap_or_else(|| "unknown".to_string()),
        author: payload.author.and_then(display_name_like),
        created: payload.created.and_then(non_empty),
        body: normalize_description(payload.body),
    }
}

fn into_issue_transition(payload: TransitionPayload) -> IssueTransition {
    let to_status = payload.to.as_ref().and_then(|value| value.name.clone());
    let description = payload
        .to
        .and_then(|value| value.description.and_then(non_empty));

    IssueTransition {
        id: payload
            .id
            .and_then(non_empty)
            .unwrap_or_else(|| "unknown".to_string()),
        name: payload.name.and_then(non_empty),
        to_status: to_status.and_then(non_empty),
        description,
    }
}

fn name_like(value: NameLike) -> Option<String> {
    value.name.and_then(non_empty)
}

fn display_name_like(value: UserLike) -> Option<String> {
    value
        .display_name
        .or(value.name)
        .or(value.email_address)
        .and_then(non_empty)
}

fn non_empty(value: String) -> Option<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return None;
    }
    Some(trimmed.to_string())
}

fn normalize_description(value: Option<Value>) -> String {
    let Some(payload) = value else {
        return String::new();
    };

    if let Some(text) = payload.as_str() {
        return text.to_string();
    }

    if let Some(raw) = payload.get("raw").and_then(Value::as_str) {
        return raw.to_string();
    }

    let is_doc = payload
        .get("type")
        .and_then(Value::as_str)
        .map(|value| value == "doc")
        .unwrap_or(false);

    if !is_doc {
        return String::new();
    }

    let mut out = String::new();
    extract_adf_text(&payload, &mut out);
    out.trim().to_string()
}

fn extract_adf_text(node: &Value, out: &mut String) {
    if let Some(node_type) = node.get("type").and_then(Value::as_str) {
        match node_type {
            "text" => {
                if let Some(text) = node.get("text").and_then(Value::as_str) {
                    out.push_str(text);
                }
            }
            "hardBreak" => out.push('\n'),
            "paragraph" | "heading" | "blockquote" | "listItem" => {
                if let Some(children) = node.get("content").and_then(Value::as_array) {
                    for child in children {
                        extract_adf_text(child, out);
                    }
                }
                out.push('\n');
            }
            _ => {
                if let Some(children) = node.get("content").and_then(Value::as_array) {
                    for child in children {
                        extract_adf_text(child, out);
                    }
                }
            }
        }
        return;
    }

    if let Some(children) = node.get("content").and_then(Value::as_array) {
        for child in children {
            extract_adf_text(child, out);
        }
    }
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::{
        into_issue_comment, into_issue_transition, normalize_description, CommentPayload,
        JiraClient, TransitionPayload,
    };

    #[test]
    fn chooses_correct_search_endpoint_for_api_versions() {
        let version_2 = "2".to_string();
        let version_3 = "3".to_string();

        let client_2 = JiraClient {
            api_version: version_2,
            base_url: "https://jira.example.com/rest/api/2".to_string(),
            http: reqwest::blocking::Client::new(),
            auth_mode: super::AuthMode::Bearer {
                token: "x".to_string(),
            },
        };
        let client_3 = JiraClient {
            api_version: version_3,
            base_url: "https://jira.example.com/rest/api/3".to_string(),
            http: reqwest::blocking::Client::new(),
            auth_mode: super::AuthMode::Bearer {
                token: "x".to_string(),
            },
        };

        assert_eq!(client_2.search_endpoint(), "search");
        assert_eq!(client_3.search_endpoint(), "search/jql");
    }

    #[test]
    fn flattens_adf_description() {
        let doc = json!({
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Hello"}]
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "World"}]
                }
            ]
        });

        assert_eq!(normalize_description(Some(doc)), "Hello\nWorld");
    }

    #[test]
    fn maps_comment_payload_defaults() {
        let comment = into_issue_comment(CommentPayload {
            id: None,
            author: None,
            created: None,
            body: None,
        });

        assert_eq!(comment.id, "unknown");
        assert_eq!(comment.author, None);
        assert_eq!(comment.created, None);
        assert_eq!(comment.body, "");
    }

    #[test]
    fn builds_comment_payload_shape_by_api_version() {
        let version_2 = "2".to_string();
        let version_3 = "3".to_string();

        let client_2 = JiraClient {
            api_version: version_2,
            base_url: "https://jira.example.com/rest/api/2".to_string(),
            http: reqwest::blocking::Client::new(),
            auth_mode: super::AuthMode::Bearer {
                token: "x".to_string(),
            },
        };
        let client_3 = JiraClient {
            api_version: version_3,
            base_url: "https://jira.example.com/rest/api/3".to_string(),
            http: reqwest::blocking::Client::new(),
            auth_mode: super::AuthMode::Bearer {
                token: "x".to_string(),
            },
        };

        assert_eq!(
            client_2.comment_body_payload("hello"),
            json!({"body": "hello"})
        );
        assert_eq!(
            client_3.comment_body_payload("hello"),
            json!({
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "hello"}]
                    }]
                }
            })
        );
    }

    #[test]
    fn maps_transition_payload_defaults() {
        let transition = into_issue_transition(TransitionPayload {
            id: None,
            name: None,
            to: None,
        });

        assert_eq!(transition.id, "unknown");
        assert_eq!(transition.name, None);
        assert_eq!(transition.to_status, None);
        assert_eq!(transition.description, None);
    }
}
