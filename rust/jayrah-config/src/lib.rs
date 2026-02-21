use std::{
    env, fs,
    path::{Path, PathBuf},
    process::Command,
};

use anyhow::{anyhow, Context, Result};
use regex::RegexBuilder;
use serde::Deserialize;

const DEFAULT_BOARD_NAME: &str = "myissue";
const DEFAULT_BOARD_JQL: &str = "assignee = currentUser() AND resolution = Unresolved";
const DEFAULT_BOARD_ORDER_BY: &str = "updated";

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BoardConfig {
    pub name: String,
    pub jql: String,
    pub order_by: Option<String>,
    pub description: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CustomFieldConfig {
    pub name: String,
    pub field: String,
    pub field_type: String,
    pub description: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct JayrahConfig {
    pub jira_server: Option<String>,
    pub jira_user: Option<String>,
    pub jira_password: Option<String>,
    pub api_version: Option<String>,
    pub auth_method: Option<String>,
    pub insecure: bool,
    pub boards: Vec<BoardConfig>,
    pub custom_fields: Vec<CustomFieldConfig>,
}

#[derive(Default, Deserialize)]
struct RawConfig {
    #[serde(default)]
    general: RawGeneral,
    #[serde(default)]
    boards: Vec<RawBoard>,
    #[serde(default)]
    custom_fields: Vec<RawCustomField>,
    jira_server: Option<String>,
    jira_user: Option<String>,
    jira_password: Option<String>,
    api_version: Option<String>,
    auth_method: Option<String>,
    insecure: Option<bool>,
}

#[derive(Default, Deserialize)]
struct RawGeneral {
    jira_server: Option<String>,
    jira_user: Option<String>,
    jira_password: Option<String>,
    api_version: Option<String>,
    auth_method: Option<String>,
    insecure: Option<bool>,
    #[serde(default)]
    custom_fields: Vec<RawCustomField>,
}

#[derive(Default, Deserialize)]
struct RawBoard {
    name: Option<String>,
    jql: Option<String>,
    order_by: Option<String>,
    description: Option<String>,
}

#[derive(Default, Deserialize)]
struct RawCustomField {
    name: Option<String>,
    field: Option<String>,
    #[serde(rename = "type")]
    field_type: Option<String>,
    description: Option<String>,
}

impl JayrahConfig {
    pub fn load_default() -> Result<Self> {
        Self::load_from_path(&default_config_path())
    }

    pub fn load_from_path(path: &Path) -> Result<Self> {
        let payload = fs::read_to_string(path)
            .with_context(|| format!("failed to read config at {}", path.display()))?;
        let raw: RawConfig =
            serde_yaml::from_str(&payload).with_context(|| "invalid YAML config format")?;
        Ok(Self::from_raw(raw))
    }

    pub fn api_version(&self) -> &str {
        match self.api_version.as_deref() {
            Some("3") => "3",
            _ => "2",
        }
    }

    pub fn auth_method(&self) -> &str {
        if let Some(value) = self.auth_method.as_deref() {
            let normalized = value.trim().to_ascii_lowercase();
            if normalized == "basic" || normalized == "bearer" {
                return if normalized == "basic" {
                    "basic"
                } else {
                    "bearer"
                };
            }
        }

        if self.api_version() == "3" {
            "basic"
        } else {
            "bearer"
        }
    }

    pub fn resolve_board(&self, requested_name: Option<&str>) -> Result<&BoardConfig> {
        if let Some(name) = requested_name {
            return self
                .boards
                .iter()
                .find(|board| board.name == name)
                .ok_or_else(|| anyhow!("board '{}' not found in configuration", name));
        }

        self.boards
            .first()
            .ok_or_else(|| anyhow!("no boards configured"))
    }

    pub fn issue_url(&self, key: &str) -> Result<String> {
        let server = self
            .jira_server
            .as_deref()
            .ok_or_else(|| anyhow!("jira_server not configured"))?;
        Ok(format!("{server}/browse/{key}"))
    }

    fn from_raw(raw: RawConfig) -> Self {
        let jira_server =
            first_some(raw.general.jira_server, raw.jira_server).and_then(normalize_jira_server);
        let jira_user = first_some(raw.general.jira_user, raw.jira_user).and_then(non_empty);
        let jira_password = first_some(raw.general.jira_password, raw.jira_password)
            .and_then(resolve_jira_password);
        let api_version = first_some(raw.general.api_version, raw.api_version).and_then(non_empty);
        let auth_method = first_some(raw.general.auth_method, raw.auth_method).and_then(non_empty);
        let insecure = raw.general.insecure.or(raw.insecure).unwrap_or(false);

        let mut boards = raw
            .boards
            .into_iter()
            .filter_map(|board| {
                let name = board.name.and_then(non_empty)?;
                let jql = board.jql.and_then(non_empty)?;
                let order_by = board.order_by.and_then(non_empty);
                let description = board.description.and_then(non_empty);
                Some(BoardConfig {
                    name,
                    jql,
                    order_by,
                    description,
                })
            })
            .collect::<Vec<_>>();

        if boards.is_empty() {
            boards.push(default_board());
        }

        let mut custom_fields = parse_custom_fields(raw.general.custom_fields);
        if !raw.custom_fields.is_empty() {
            custom_fields = parse_custom_fields(raw.custom_fields);
        }

        Self {
            jira_server,
            jira_user,
            jira_password,
            api_version,
            auth_method,
            insecure,
            boards,
            custom_fields,
        }
    }
}

pub fn default_config_path() -> PathBuf {
    if let Some(override_path) = env::var_os("JAYRAH_CONFIG_FILE") {
        return PathBuf::from(override_path);
    }

    let mut base = env::var_os("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."));
    base.push(".config");
    base.push("jayrah");
    base.push("config.yaml");
    base
}

pub fn resolve_current_user_jql(jql: &str, jira_user: Option<&str>) -> String {
    let Some(user) = jira_user.and_then(non_empty_str) else {
        return jql.to_string();
    };

    let escaped = user.replace('\\', "\\\\").replace('"', "\\\"");
    let replacement = format!("\"{escaped}\"");
    let regex = RegexBuilder::new(r"currentUser\(\)")
        .case_insensitive(true)
        .build()
        .expect("regex");
    regex.replace_all(jql, replacement.as_str()).to_string()
}

fn default_board() -> BoardConfig {
    BoardConfig {
        name: DEFAULT_BOARD_NAME.to_string(),
        jql: DEFAULT_BOARD_JQL.to_string(),
        order_by: Some(DEFAULT_BOARD_ORDER_BY.to_string()),
        description: Some("My current unresolved issues".to_string()),
    }
}

fn non_empty(value: String) -> Option<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return None;
    }
    Some(trimmed.to_string())
}

fn non_empty_str(value: &str) -> Option<&str> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return None;
    }
    Some(trimmed)
}

fn normalize_jira_server(value: String) -> Option<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return None;
    }

    if trimmed.starts_with("http://") || trimmed.starts_with("https://") {
        Some(trimmed.trim_end_matches('/').to_string())
    } else {
        Some(format!("https://{}", trimmed.trim_end_matches('/')))
    }
}

fn first_some<T>(first: Option<T>, second: Option<T>) -> Option<T> {
    first.or(second)
}

fn parse_custom_fields(entries: Vec<RawCustomField>) -> Vec<CustomFieldConfig> {
    entries
        .into_iter()
        .filter_map(|entry| {
            let name = entry.name.and_then(non_empty)?;
            let field = entry.field.and_then(non_empty)?;
            let field_type = entry
                .field_type
                .and_then(non_empty)
                .unwrap_or_else(|| "string".to_string());
            let description = entry.description.and_then(non_empty);
            Some(CustomFieldConfig {
                name,
                field,
                field_type,
                description,
            })
        })
        .collect()
}

fn resolve_jira_password(value: String) -> Option<String> {
    resolve_jira_password_with(value, fetch_secret_from_manager)
}

fn resolve_jira_password_with<F>(value: String, fetch: F) -> Option<String>
where
    F: Fn(&str, &str) -> Option<String>,
{
    let password = non_empty(value)?;
    let Some((provider, key)) = parse_secret_reference(password.as_str()) else {
        return Some(password);
    };
    fetch(provider, key)
}

fn parse_secret_reference(value: &str) -> Option<(&str, &str)> {
    let (provider, key) = value.split_once("::")?;
    if key.trim().is_empty() {
        return None;
    }
    if provider == "pass" || provider == "passage" {
        Some((provider, key.trim()))
    } else {
        None
    }
}

fn fetch_secret_from_manager(provider: &str, key: &str) -> Option<String> {
    let output = Command::new(provider).arg("show").arg(key).output().ok()?;
    if !output.status.success() {
        return None;
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    non_empty(stdout.trim().to_string())
}

#[cfg(test)]
mod tests {
    use std::fs;

    use tempfile::tempdir;

    use super::{
        default_config_path, resolve_current_user_jql, resolve_jira_password_with, JayrahConfig,
    };

    #[test]
    fn parses_general_config_and_board() {
        let dir = tempdir().expect("temp dir");
        let path = dir.path().join("config.yaml");
        fs::write(
            &path,
            r#"
general:
  jira_server: jira.example.com
  jira_user: alice@example.com
  jira_password: token
  api_version: "3"
  auth_method: basic
boards:
  - name: my-board
    jql: project = DEMO
    order_by: updated
custom_fields:
  - name: Story Points
    field: customfield_10016
    type: number
"#,
        )
        .expect("write config");

        let config = JayrahConfig::load_from_path(&path).expect("config");
        assert_eq!(
            config.jira_server.as_deref(),
            Some("https://jira.example.com")
        );
        assert_eq!(config.api_version(), "3");
        assert_eq!(config.auth_method(), "basic");
        assert_eq!(config.boards[0].name, "my-board");
        assert_eq!(config.custom_fields[0].name, "Story Points");
        assert_eq!(config.custom_fields[0].field_type, "number");
    }

    #[test]
    fn injects_default_board_when_none_defined() {
        let dir = tempdir().expect("temp dir");
        let path = dir.path().join("config.yaml");
        fs::write(&path, "general:\n  jira_server: https://jira.example.com\n").expect("write");

        let config = JayrahConfig::load_from_path(&path).expect("config");
        assert_eq!(config.boards.len(), 1);
        assert_eq!(config.boards[0].name, "myissue");
    }

    #[test]
    fn resolves_current_user_case_insensitively() {
        let resolved = resolve_current_user_jql(
            "assignee = currentUser() OR assignee = CURRENTUSER()",
            Some("alice@example.com"),
        );
        assert_eq!(
            resolved,
            r#"assignee = "alice@example.com" OR assignee = "alice@example.com""#
        );
    }

    #[test]
    fn exposes_default_path_and_honors_override() {
        let original = std::env::var_os("JAYRAH_CONFIG_FILE");
        std::env::set_var("JAYRAH_CONFIG_FILE", "/tmp/jayrah-test-config.yaml");
        assert_eq!(
            default_config_path().to_string_lossy(),
            "/tmp/jayrah-test-config.yaml"
        );
        match original {
            Some(value) => std::env::set_var("JAYRAH_CONFIG_FILE", value),
            None => std::env::remove_var("JAYRAH_CONFIG_FILE"),
        }
    }

    #[test]
    fn resolves_pass_secret_references() {
        let resolved =
            resolve_jira_password_with("pass::jira/main".to_string(), |provider, key| {
                assert_eq!(provider, "pass");
                assert_eq!(key, "jira/main");
                Some("token-from-pass".to_string())
            });
        assert_eq!(resolved.as_deref(), Some("token-from-pass"));
    }

    #[test]
    fn resolves_passage_secret_references() {
        let resolved =
            resolve_jira_password_with("passage::jira/main".to_string(), |provider, key| {
                assert_eq!(provider, "passage");
                assert_eq!(key, "jira/main");
                Some("token-from-passage".to_string())
            });
        assert_eq!(resolved.as_deref(), Some("token-from-passage"));
    }

    #[test]
    fn leaves_plain_password_unchanged() {
        let resolved = resolve_jira_password_with("plain-token".to_string(), |_provider, _key| {
            panic!("fetch should not be called for plain passwords");
        });
        assert_eq!(resolved.as_deref(), Some("plain-token"));
    }

    #[test]
    fn drops_password_when_secret_lookup_fails() {
        let resolved =
            resolve_jira_password_with("pass::jira/main".to_string(), |_provider, _key| None);
        assert!(resolved.is_none());
    }
}
