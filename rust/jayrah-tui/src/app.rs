use std::{
    collections::HashMap,
    sync::mpsc::Sender,
    time::{Duration, Instant},
};

use crate::{
    adapter::{load_issues_from_adapter, open_issue_in_browser},
    mock::{mock_detail_from_issue, mock_issues},
    types::{AdapterSource, Issue, IssueDetail},
    utils::{compact_error, join_or_dash},
};

const DETAIL_FETCH_DEBOUNCE_MS: u64 = 120;

#[derive(Debug)]
pub struct DetailRequest {
    pub key: String,
}

#[derive(Debug)]
pub struct DetailResult {
    pub key: String,
    pub result: std::result::Result<IssueDetail, String>,
}

#[derive(Debug)]
pub struct App {
    pub(crate) issues: Vec<Issue>,
    pub(crate) selected: usize,
    pub(crate) filter_mode: bool,
    pub(crate) filter_input: String,
    reload_count: usize,
    pub(crate) status_line: String,
    pub(crate) source: AdapterSource,
    pub(crate) using_adapter: bool,
    pub(crate) choose_mode: bool,
    detail_cache: HashMap<String, IssueDetail>,
    detail_errors: HashMap<String, String>,
    detail_loading_key: Option<String>,
    last_selected_key: Option<String>,
    selected_changed_at: Instant,
}

impl App {
    pub fn new(source: AdapterSource, choose_mode: bool) -> Self {
        let mut app = Self {
            issues: Vec::new(),
            selected: 0,
            filter_mode: false,
            filter_input: String::new(),
            reload_count: 0,
            status_line: String::new(),
            source,
            using_adapter: false,
            choose_mode,
            detail_cache: HashMap::new(),
            detail_errors: HashMap::new(),
            detail_loading_key: None,
            last_selected_key: None,
            selected_changed_at: Instant::now(),
        };
        app.reload_issues();
        app.sync_selected_tracking();
        app
    }

    pub fn visible_indices(&self) -> Vec<usize> {
        let filter = self.filter_input.trim().to_lowercase();
        if filter.is_empty() {
            return (0..self.issues.len()).collect();
        }

        self.issues
            .iter()
            .enumerate()
            .filter_map(|(idx, issue)| {
                let matches = issue.key.to_lowercase().contains(&filter)
                    || issue.summary.to_lowercase().contains(&filter)
                    || issue.status.to_lowercase().contains(&filter)
                    || issue.assignee.to_lowercase().contains(&filter);
                if matches {
                    Some(idx)
                } else {
                    None
                }
            })
            .collect()
    }

    pub fn normalize_selection(&mut self) {
        self.normalize_selection_with_preferred_key(None);
    }

    pub fn normalize_selection_with_preferred_key(&mut self, preferred_key: Option<&str>) {
        let visible = self.visible_indices();
        if visible.is_empty() {
            self.selected = 0;
            return;
        }

        if let Some(key) = preferred_key {
            if let Some(position) = visible
                .iter()
                .position(|index| self.issues[*index].key.as_str() == key)
            {
                self.selected = position;
                return;
            }
        }

        let len = visible.len();
        if self.selected >= len {
            self.selected = len - 1;
        }
    }

    pub fn next(&mut self) {
        let len = self.visible_indices().len();
        if len == 0 {
            return;
        }
        self.selected = (self.selected + 1) % len;
    }

    pub fn prev(&mut self) {
        let len = self.visible_indices().len();
        if len == 0 {
            return;
        }
        self.selected = if self.selected == 0 {
            len - 1
        } else {
            self.selected - 1
        };
    }

    pub fn selected_issue(&self) -> Option<&Issue> {
        let visible = self.visible_indices();
        let issue_index = visible.get(self.selected)?;
        self.issues.get(*issue_index)
    }

    pub(crate) fn selected_issue_key(&self) -> Option<String> {
        self.selected_issue().map(|issue| issue.key.clone())
    }

    pub fn reload_issues(&mut self) {
        let preferred_key = self.selected_issue_key();
        self.reload_count += 1;
        self.detail_cache.clear();
        self.detail_errors.clear();
        self.detail_loading_key = None;

        if self.source.mock_only {
            self.issues = mock_issues(self.reload_count);
            self.using_adapter = false;
            self.status_line = format!("Reloaded mock issues ({})", self.reload_count);
            self.normalize_selection_with_preferred_key(preferred_key.as_deref());
            return;
        }

        match load_issues_from_adapter(&self.source) {
            Ok(issues) => {
                self.using_adapter = true;
                self.issues = issues;
                self.status_line = format!(
                    "Loaded {} issues from adapter ({})",
                    self.issues.len(),
                    self.source.describe()
                );
            }
            Err(error) => {
                self.using_adapter = false;
                self.issues = mock_issues(self.reload_count);
                self.status_line = format!(
                    "Adapter unavailable ({}); using mock data",
                    compact_error(&error.to_string())
                );
            }
        }

        self.normalize_selection_with_preferred_key(preferred_key.as_deref());
        self.sync_selected_tracking();
    }

    fn sync_selected_tracking(&mut self) {
        let current = self.selected_issue_key();
        if current != self.last_selected_key {
            self.last_selected_key = current;
            self.selected_changed_at = Instant::now();
        }
    }

    pub fn maybe_request_detail(&mut self, request_tx: &Sender<DetailRequest>) {
        self.sync_selected_tracking();

        let Some(key) = self.selected_issue_key() else {
            return;
        };

        if self.detail_cache.contains_key(&key) {
            return;
        }

        if !self.using_adapter {
            if let Some(issue) = self.selected_issue() {
                self.detail_cache.insert(key, mock_detail_from_issue(issue));
            }
            return;
        }

        if self.detail_errors.contains_key(&key) {
            return;
        }

        if self.detail_loading_key.as_deref() == Some(key.as_str()) {
            return;
        }

        if self.selected_changed_at.elapsed() < Duration::from_millis(DETAIL_FETCH_DEBOUNCE_MS) {
            return;
        }

        if request_tx.send(DetailRequest { key: key.clone() }).is_ok() {
            self.detail_loading_key = Some(key.clone());
            self.status_line = format!("Loading detail for {key}...");
        }
    }

    pub fn ingest_detail_result(&mut self, message: DetailResult) {
        match message.result {
            Ok(detail) => {
                self.detail_cache.insert(message.key.clone(), detail);
                self.detail_errors.remove(&message.key);
                if self.detail_loading_key.as_deref() == Some(message.key.as_str()) {
                    self.detail_loading_key = None;
                }
                if self.selected_issue_key().as_deref() == Some(message.key.as_str()) {
                    self.status_line = format!("Loaded detail for {}", message.key);
                }
            }
            Err(error) => {
                self.detail_errors
                    .insert(message.key.clone(), error.clone());
                if self.detail_loading_key.as_deref() == Some(message.key.as_str()) {
                    self.detail_loading_key = None;
                }
                if self.selected_issue_key().as_deref() == Some(message.key.as_str()) {
                    self.status_line = format!(
                        "Failed to load detail for {} ({})",
                        message.key,
                        compact_error(&error)
                    );
                }
            }
        }
    }

    pub fn detail_text_for_selected(&self) -> String {
        let Some(issue) = self.selected_issue() else {
            return "No issue selected".to_string();
        };

        let key = issue.key.as_str();
        if let Some(detail) = self.detail_cache.get(key) {
            let labels = join_or_dash(&detail.labels);
            let components = join_or_dash(&detail.components);
            let fix_versions = join_or_dash(&detail.fix_versions);
            let description = if detail.description.is_empty() {
                "<no description>"
            } else {
                detail.description.as_str()
            };

            return format!(
                "Key: {}\nSummary: {}\nStatus: {}\nPriority: {}\nType: {}\nAssignee: {}\nReporter: {}\nCreated: {}\nUpdated: {}\nLabels: {}\nComponents: {}\nFix Versions: {}\n\nDescription\n{}",
                detail.key,
                detail.summary,
                detail.status,
                detail.priority,
                detail.issue_type,
                detail.assignee,
                detail.reporter,
                detail.created,
                detail.updated,
                labels,
                components,
                fix_versions,
                description,
            );
        }

        if let Some(error) = self.detail_errors.get(key) {
            return format!(
                "Key: {}\nStatus: {}\nAssignee: {}\n\nSummary\n{}\n\nDetail load failed\n{}",
                issue.key,
                issue.status,
                issue.assignee,
                issue.summary,
                compact_error(error),
            );
        }

        if self.detail_loading_key.as_deref() == Some(key) {
            return format!(
                "Loading detail for {}...\n\nSummary\n{}\n\nSource\n{}",
                issue.key,
                issue.summary,
                self.source.describe(),
            );
        }

        format!(
            "Key: {}\nStatus: {}\nAssignee: {}\n\nSummary\n{}\n\nSource\n{}",
            issue.key,
            issue.status,
            issue.assignee,
            issue.summary,
            self.source.describe(),
        )
    }

    pub fn open_selected_issue(&mut self) {
        let Some(key) = self.selected_issue_key() else {
            self.status_line = String::from("No issue selected");
            return;
        };

        if !self.using_adapter {
            self.status_line = format!("Open disabled while using mock data ({key})");
            return;
        }

        match open_issue_in_browser(&key) {
            Ok(()) => {
                self.status_line = format!("Opened {key} in browser");
            }
            Err(error) => {
                self.status_line = format!(
                    "Failed to open {} ({})",
                    key,
                    compact_error(&error.to_string())
                );
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use std::sync::mpsc;

    use super::App;
    use crate::types::AdapterSource;

    fn mock_source() -> AdapterSource {
        AdapterSource {
            board: None,
            query: None,
            mock_only: true,
        }
    }

    #[test]
    fn filters_visible_indices_by_summary() {
        let mut app = App::new(mock_source(), false);
        app.filter_input = "adapter".to_string();

        let visible = app.visible_indices();
        assert_eq!(visible.len(), 1);
        assert_eq!(app.issues[visible[0]].key, "JAY-102");
    }

    #[test]
    fn maybe_request_detail_populates_mock_cache_without_worker_request() {
        let mut app = App::new(mock_source(), false);
        let (tx, rx) = mpsc::channel();

        app.maybe_request_detail(&tx);

        assert!(rx.try_recv().is_err());
        let detail = app.detail_text_for_selected();
        assert!(detail.contains("Description"));
        assert!(detail.contains("Mock detail payload"));
    }

    #[test]
    fn preserves_selected_issue_when_filter_changes() {
        let mut app = App::new(mock_source(), false);
        app.selected = 2;

        let selected_key = app.selected_issue_key().expect("selected key");
        app.filter_input = "jay".to_string();
        app.normalize_selection_with_preferred_key(Some(selected_key.as_str()));

        assert_eq!(
            app.selected_issue_key().as_deref(),
            Some(selected_key.as_str())
        );
    }

    #[test]
    fn preserves_selected_issue_key_across_reload() {
        let mut app = App::new(mock_source(), false);
        app.selected = 1;
        let selected_key = app.selected_issue_key().expect("selected key");

        app.reload_issues();

        assert_eq!(
            app.selected_issue_key().as_deref(),
            Some(selected_key.as_str())
        );
    }
}
