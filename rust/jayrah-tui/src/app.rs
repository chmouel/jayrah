use std::{
    collections::HashMap,
    sync::mpsc::Sender,
    time::{Duration, Instant},
};

use crate::{
    adapter::{load_issues_from_adapter, open_issue_in_browser},
    mock::{
        mock_comments_for_issue, mock_detail_from_issue, mock_issues, mock_transitions_for_issue,
    },
    types::{AdapterSource, Issue, IssueComment, IssueDetail, IssueTransition},
    utils::{compact_error, join_or_dash},
};

const DETAIL_FETCH_DEBOUNCE_MS: u64 = 120;
const COMMENT_FETCH_DEBOUNCE_MS: u64 = 120;
const TRANSITION_FETCH_DEBOUNCE_MS: u64 = 120;

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
pub struct CommentRequest {
    pub key: String,
}

#[derive(Debug)]
pub struct CommentResult {
    pub key: String,
    pub result: std::result::Result<Vec<IssueComment>, String>,
}

#[derive(Debug)]
pub struct AddCommentRequest {
    pub key: String,
    pub body: String,
}

#[derive(Debug)]
pub struct AddCommentResult {
    pub key: String,
    pub result: std::result::Result<(), String>,
}

#[derive(Debug)]
pub struct TransitionRequest {
    pub key: String,
}

#[derive(Debug)]
pub struct TransitionResult {
    pub key: String,
    pub result: std::result::Result<Vec<IssueTransition>, String>,
}

#[derive(Debug)]
pub struct ApplyTransitionRequest {
    pub key: String,
    pub transition_id: String,
    pub transition_name: String,
    pub to_status: String,
}

#[derive(Debug)]
pub struct ApplyTransitionResult {
    pub key: String,
    pub transition_name: String,
    pub to_status: String,
    pub result: std::result::Result<(), String>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum DetailPaneMode {
    Detail,
    Comments,
    Transitions,
    Actions,
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
    comments_cache: HashMap<String, Vec<IssueComment>>,
    comments_errors: HashMap<String, String>,
    comments_loading_key: Option<String>,
    comments_selected: usize,
    comment_input_mode: bool,
    comment_input: String,
    comment_submit_in_flight: bool,
    transitions_cache: HashMap<String, Vec<IssueTransition>>,
    transitions_errors: HashMap<String, String>,
    transitions_loading_key: Option<String>,
    transition_selected: usize,
    transition_apply_in_flight: bool,
    pane_mode: DetailPaneMode,
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
            comments_cache: HashMap::new(),
            comments_errors: HashMap::new(),
            comments_loading_key: None,
            comments_selected: 0,
            comment_input_mode: false,
            comment_input: String::new(),
            comment_submit_in_flight: false,
            transitions_cache: HashMap::new(),
            transitions_errors: HashMap::new(),
            transitions_loading_key: None,
            transition_selected: 0,
            transition_apply_in_flight: false,
            pane_mode: DetailPaneMode::Detail,
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

    pub fn in_comments_mode(&self) -> bool {
        self.pane_mode == DetailPaneMode::Comments
    }

    pub fn in_transitions_mode(&self) -> bool {
        self.pane_mode == DetailPaneMode::Transitions
    }

    pub fn in_actions_mode(&self) -> bool {
        self.pane_mode == DetailPaneMode::Actions
    }

    pub fn in_comment_input_mode(&self) -> bool {
        self.comment_input_mode
    }

    pub fn comment_input(&self) -> &str {
        self.comment_input.as_str()
    }

    pub fn enter_comments_mode(&mut self) {
        self.pane_mode = DetailPaneMode::Comments;
        self.comments_selected = 0;
        self.transition_selected = 0;
        self.status_line = "Comments mode: n/p to navigate comments, c or Esc to close".to_string();
    }

    pub fn enter_transitions_mode(&mut self) {
        self.pane_mode = DetailPaneMode::Transitions;
        self.comment_input_mode = false;
        self.comment_input.clear();
        self.transition_selected = 0;
        self.status_line =
            "Transitions mode: n/p select transition, Enter apply, t or Esc close".to_string();
    }

    pub fn enter_actions_mode(&mut self) {
        self.pane_mode = DetailPaneMode::Actions;
        self.comment_input_mode = false;
        self.comment_input.clear();
        self.status_line = "Actions help: press ? or Esc to close".to_string();
    }

    pub fn enter_detail_mode(&mut self) {
        self.pane_mode = DetailPaneMode::Detail;
        self.comment_input_mode = false;
        self.comment_input.clear();
        self.status_line = "Detail mode".to_string();
    }

    pub fn start_comment_input(&mut self) {
        if !self.in_comments_mode() {
            return;
        }
        if self.comment_submit_in_flight {
            self.status_line = "Comment submission in progress...".to_string();
            return;
        }

        self.comment_input_mode = true;
        self.status_line = "Comment input: type message, Enter submit, Esc cancel".to_string();
    }

    pub fn cancel_comment_input(&mut self) {
        self.comment_input_mode = false;
        self.comment_input.clear();
        self.status_line = "Comment draft canceled".to_string();
    }

    pub fn push_comment_input_char(&mut self, value: char) {
        self.comment_input.push(value);
    }

    pub fn pop_comment_input_char(&mut self) {
        self.comment_input.pop();
    }

    pub fn next_comment(&mut self) {
        let Some(key) = self.selected_issue_key() else {
            return;
        };
        let Some(comments) = self.comments_cache.get(&key) else {
            return;
        };
        if comments.is_empty() {
            return;
        }

        self.comments_selected = (self.comments_selected + 1) % comments.len();
    }

    pub fn prev_comment(&mut self) {
        let Some(key) = self.selected_issue_key() else {
            return;
        };
        let Some(comments) = self.comments_cache.get(&key) else {
            return;
        };
        if comments.is_empty() {
            return;
        }

        self.comments_selected = if self.comments_selected == 0 {
            comments.len() - 1
        } else {
            self.comments_selected - 1
        };
    }

    pub fn next_transition(&mut self) {
        let Some(key) = self.selected_issue_key() else {
            return;
        };
        let Some(transitions) = self.transitions_cache.get(&key) else {
            return;
        };
        if transitions.is_empty() {
            return;
        }

        self.transition_selected = (self.transition_selected + 1) % transitions.len();
    }

    pub fn prev_transition(&mut self) {
        let Some(key) = self.selected_issue_key() else {
            return;
        };
        let Some(transitions) = self.transitions_cache.get(&key) else {
            return;
        };
        if transitions.is_empty() {
            return;
        }

        self.transition_selected = if self.transition_selected == 0 {
            transitions.len() - 1
        } else {
            self.transition_selected - 1
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
        self.comments_cache.clear();
        self.comments_errors.clear();
        self.comments_loading_key = None;
        self.comments_selected = 0;
        self.comment_input_mode = false;
        self.comment_input.clear();
        self.comment_submit_in_flight = false;
        self.transitions_cache.clear();
        self.transitions_errors.clear();
        self.transitions_loading_key = None;
        self.transition_selected = 0;
        self.transition_apply_in_flight = false;

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
            self.comments_selected = 0;
            self.comment_input_mode = false;
            self.comment_input.clear();
            self.transition_selected = 0;
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

    pub fn maybe_request_comments(&mut self, request_tx: &Sender<CommentRequest>) {
        self.sync_selected_tracking();

        if self.pane_mode != DetailPaneMode::Comments {
            return;
        }

        let Some(key) = self.selected_issue_key() else {
            return;
        };

        if self.comments_cache.contains_key(&key) {
            return;
        }

        if !self.using_adapter {
            self.comments_cache
                .insert(key.clone(), mock_comments_for_issue(&key));
            return;
        }

        if self.comments_errors.contains_key(&key) {
            return;
        }

        if self.comments_loading_key.as_deref() == Some(key.as_str()) {
            return;
        }

        if self.selected_changed_at.elapsed() < Duration::from_millis(COMMENT_FETCH_DEBOUNCE_MS) {
            return;
        }

        if request_tx.send(CommentRequest { key: key.clone() }).is_ok() {
            self.comments_loading_key = Some(key.clone());
            self.status_line = format!("Loading comments for {key}...");
        }
    }

    pub fn maybe_request_transitions(&mut self, request_tx: &Sender<TransitionRequest>) {
        self.sync_selected_tracking();

        if self.pane_mode != DetailPaneMode::Transitions {
            return;
        }

        let Some(key) = self.selected_issue_key() else {
            return;
        };

        if self.transitions_cache.contains_key(&key) {
            return;
        }

        if !self.using_adapter {
            self.transitions_cache
                .insert(key.clone(), mock_transitions_for_issue(&key));
            return;
        }

        if self.transitions_errors.contains_key(&key) {
            return;
        }

        if self.transitions_loading_key.as_deref() == Some(key.as_str()) {
            return;
        }

        if self.selected_changed_at.elapsed() < Duration::from_millis(TRANSITION_FETCH_DEBOUNCE_MS)
        {
            return;
        }

        if request_tx
            .send(TransitionRequest { key: key.clone() })
            .is_ok()
        {
            self.transitions_loading_key = Some(key.clone());
            self.status_line = format!("Loading transitions for {key}...");
        }
    }

    pub fn submit_comment_input(&mut self, submit_tx: &Sender<AddCommentRequest>) {
        let Some(key) = self.selected_issue_key() else {
            self.status_line = "No issue selected".to_string();
            return;
        };

        let body = self.comment_input.trim().to_string();
        if body.is_empty() {
            self.status_line = "Comment cannot be empty".to_string();
            return;
        }

        if self.comment_submit_in_flight {
            self.status_line = "Comment submission in progress...".to_string();
            return;
        }

        if !self.using_adapter {
            let comments = self
                .comments_cache
                .entry(key.clone())
                .or_insert_with(|| mock_comments_for_issue(&key));
            let next_index = comments.len() + 1;
            comments.push(IssueComment {
                id: format!("{key}-local-{next_index}"),
                author: "you".to_string(),
                created: "local".to_string(),
                body,
            });
            self.comments_selected = comments.len().saturating_sub(1);
            self.comment_input_mode = false;
            self.comment_input.clear();
            self.status_line = format!("Added mock comment to {key}");
            return;
        }

        if submit_tx
            .send(AddCommentRequest {
                key: key.clone(),
                body,
            })
            .is_ok()
        {
            self.comment_submit_in_flight = true;
            self.comment_input_mode = false;
            self.comment_input.clear();
            self.status_line = format!("Submitting comment for {key}...");
        } else {
            self.status_line = format!("Failed to queue comment submission for {key}");
        }
    }

    pub fn apply_selected_transition(&mut self, apply_tx: &Sender<ApplyTransitionRequest>) {
        let Some(key) = self.selected_issue_key() else {
            self.status_line = "No issue selected".to_string();
            return;
        };

        if self.transition_apply_in_flight {
            self.status_line = "Transition apply in progress...".to_string();
            return;
        }

        let Some(transitions) = self.transitions_cache.get(&key) else {
            self.status_line = format!("No transitions loaded for {key}");
            return;
        };
        if transitions.is_empty() {
            self.status_line = format!("No transitions available for {key}");
            return;
        }

        let selected_index = self.transition_selected.min(transitions.len() - 1);
        let selected = transitions[selected_index].clone();

        if !self.using_adapter {
            self.update_issue_status(&key, &selected.to_status);
            self.detail_cache.remove(&key);
            self.transitions_cache.remove(&key);
            self.transition_selected = 0;
            self.status_line = format!(
                "Mock transition applied to {}: '{}' via '{}'",
                key, selected.to_status, selected.name
            );
            return;
        }

        if apply_tx
            .send(ApplyTransitionRequest {
                key: key.clone(),
                transition_id: selected.id.clone(),
                transition_name: selected.name.clone(),
                to_status: selected.to_status.clone(),
            })
            .is_ok()
        {
            self.transition_apply_in_flight = true;
            self.status_line = format!("Applying transition '{}' to {key}...", selected.name);
        } else {
            self.status_line = format!("Failed to queue transition apply for {key}");
        }
    }

    fn update_issue_status(&mut self, key: &str, status: &str) {
        if let Some(issue) = self.issues.iter_mut().find(|issue| issue.key == key) {
            issue.status = status.to_string();
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

    pub fn ingest_comment_result(&mut self, message: CommentResult) {
        match message.result {
            Ok(comments) => {
                self.comments_cache.insert(message.key.clone(), comments);
                self.comments_errors.remove(&message.key);
                if self.comments_loading_key.as_deref() == Some(message.key.as_str()) {
                    self.comments_loading_key = None;
                }
                if self.selected_issue_key().as_deref() == Some(message.key.as_str()) {
                    self.status_line = format!("Loaded comments for {}", message.key);
                }
            }
            Err(error) => {
                self.comments_errors
                    .insert(message.key.clone(), error.clone());
                if self.comments_loading_key.as_deref() == Some(message.key.as_str()) {
                    self.comments_loading_key = None;
                }
                if self.selected_issue_key().as_deref() == Some(message.key.as_str()) {
                    self.status_line = format!(
                        "Failed to load comments for {} ({})",
                        message.key,
                        compact_error(&error)
                    );
                }
            }
        }
    }

    pub fn ingest_transition_result(&mut self, message: TransitionResult) {
        match message.result {
            Ok(transitions) => {
                self.transitions_cache
                    .insert(message.key.clone(), transitions);
                self.transitions_errors.remove(&message.key);
                if self.transitions_loading_key.as_deref() == Some(message.key.as_str()) {
                    self.transitions_loading_key = None;
                }
                if self.selected_issue_key().as_deref() == Some(message.key.as_str()) {
                    self.status_line = format!("Loaded transitions for {}", message.key);
                }
            }
            Err(error) => {
                self.transitions_errors
                    .insert(message.key.clone(), error.clone());
                if self.transitions_loading_key.as_deref() == Some(message.key.as_str()) {
                    self.transitions_loading_key = None;
                }
                if self.selected_issue_key().as_deref() == Some(message.key.as_str()) {
                    self.status_line = format!(
                        "Failed to load transitions for {} ({})",
                        message.key,
                        compact_error(&error)
                    );
                }
            }
        }
    }

    pub fn ingest_apply_transition_result(&mut self, message: ApplyTransitionResult) {
        self.transition_apply_in_flight = false;
        match message.result {
            Ok(()) => {
                self.update_issue_status(&message.key, &message.to_status);
                self.detail_cache.remove(&message.key);
                self.transitions_cache.remove(&message.key);
                self.transitions_errors.remove(&message.key);
                if self.transitions_loading_key.as_deref() == Some(message.key.as_str()) {
                    self.transitions_loading_key = None;
                }
                self.transition_selected = 0;
                if self.selected_issue_key().as_deref() == Some(message.key.as_str()) {
                    self.status_line = format!(
                        "Issue {} transitioned to '{}' via '{}'",
                        message.key, message.to_status, message.transition_name
                    );
                }
            }
            Err(error) => {
                if self.selected_issue_key().as_deref() == Some(message.key.as_str()) {
                    self.status_line = format!(
                        "Failed to transition {} ({})",
                        message.key,
                        compact_error(&error)
                    );
                }
            }
        }
    }

    pub fn ingest_add_comment_result(&mut self, message: AddCommentResult) {
        self.comment_submit_in_flight = false;
        match message.result {
            Ok(()) => {
                self.comments_cache.remove(&message.key);
                self.comments_errors.remove(&message.key);
                if self.comments_loading_key.as_deref() == Some(message.key.as_str()) {
                    self.comments_loading_key = None;
                }
                self.comments_selected = 0;
                if self.selected_issue_key().as_deref() == Some(message.key.as_str()) {
                    self.status_line = format!("Added comment to {}", message.key);
                }
            }
            Err(error) => {
                if self.selected_issue_key().as_deref() == Some(message.key.as_str()) {
                    self.status_line = format!(
                        "Failed to add comment to {} ({})",
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

    pub fn comments_text_for_selected(&self) -> String {
        let Some(issue) = self.selected_issue() else {
            return "No issue selected".to_string();
        };

        let key = issue.key.as_str();
        let mut text = if let Some(comments) = self.comments_cache.get(key) {
            if comments.is_empty() {
                format!("Comments for {key}\n\nNo comments found.")
            } else {
                let active_index = self.comments_selected.min(comments.len() - 1);
                let current = &comments[active_index];
                let body = if current.body.is_empty() {
                    "<no comment body>"
                } else {
                    current.body.as_str()
                };

                format!(
                    "Comments for {}\n\nComment {}/{}\nAuthor: {}\nCreated: {}\n\n{}",
                    key,
                    active_index + 1,
                    comments.len(),
                    current.author,
                    current.created,
                    body,
                )
            }
        } else if let Some(error) = self.comments_errors.get(key) {
            format!(
                "Comments for {}\n\nFailed to load comments\n{}",
                key,
                compact_error(error),
            )
        } else if self.comments_loading_key.as_deref() == Some(key) {
            format!(
                "Loading comments for {}...\n\nSummary\n{}\n\nSource\n{}",
                issue.key,
                issue.summary,
                self.source.describe(),
            )
        } else {
            format!(
                "Comments for {}\n\nPress c to load comments for this issue.",
                issue.key
            )
        };

        if self.comment_submit_in_flight {
            text.push_str("\n\nSubmitting comment...");
        }

        if self.comment_input_mode {
            let draft = if self.comment_input.is_empty() {
                "<empty>"
            } else {
                self.comment_input.as_str()
            };
            text.push_str(&format!("\n\n---\nDraft Comment\n{draft}"));
        }

        text
    }

    pub fn transitions_text_for_selected(&self) -> String {
        let Some(issue) = self.selected_issue() else {
            return "No issue selected".to_string();
        };

        let key = issue.key.as_str();
        let mut text = if let Some(transitions) = self.transitions_cache.get(key) {
            if transitions.is_empty() {
                format!("Transitions for {key}\n\nNo transitions available.")
            } else {
                let active_index = self.transition_selected.min(transitions.len() - 1);
                let current = &transitions[active_index];
                format!(
                    "Transitions for {}\n\nTransition {}/{}\nName: {}\nTo: {}\nDescription: {}\n\nUse n/p to choose and Enter to apply.",
                    key,
                    active_index + 1,
                    transitions.len(),
                    current.name,
                    current.to_status,
                    current.description,
                )
            }
        } else if let Some(error) = self.transitions_errors.get(key) {
            format!(
                "Transitions for {}\n\nFailed to load transitions\n{}",
                key,
                compact_error(error),
            )
        } else if self.transitions_loading_key.as_deref() == Some(key) {
            format!(
                "Loading transitions for {}...\n\nSummary\n{}\n\nSource\n{}",
                issue.key,
                issue.summary,
                self.source.describe(),
            )
        } else {
            format!(
                "Transitions for {}\n\nPress t to load transitions for this issue.",
                issue.key
            )
        };

        if self.transition_apply_in_flight {
            text.push_str("\n\nApplying transition...");
        }

        text
    }

    pub fn actions_text(&self) -> String {
        let mode = if self.choose_mode { "choose" } else { "normal" };
        format!(
            "Jayrah Rust TUI Actions ({mode} mode)\n\nNavigation\n  j/k or arrows: move issue selection\n  f or /: filter issues\n  r: reload issues\n\nIssue Actions\n  o: open selected issue in browser\n  c: comments pane\n  t: transitions pane\n  ?: actions/help pane\n\nComments Mode\n  n/p: previous/next comment\n  a: compose comment\n  Enter: submit comment draft\n\nTransitions Mode\n  n/p: previous/next transition\n  Enter: apply selected transition\n\nGlobal\n  q: quit (or close active pane)\n  Esc: close active pane/filter"
        )
    }

    pub fn right_pane_text(&self) -> String {
        match self.pane_mode {
            DetailPaneMode::Detail => self.detail_text_for_selected(),
            DetailPaneMode::Comments => self.comments_text_for_selected(),
            DetailPaneMode::Transitions => self.transitions_text_for_selected(),
            DetailPaneMode::Actions => self.actions_text(),
        }
    }

    pub fn right_pane_title(&self) -> &'static str {
        match self.pane_mode {
            DetailPaneMode::Detail => "Detail",
            DetailPaneMode::Comments => "Comments",
            DetailPaneMode::Transitions => "Transitions",
            DetailPaneMode::Actions => "Actions",
        }
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

    #[test]
    fn maybe_request_comments_populates_mock_cache_without_worker_request() {
        let mut app = App::new(mock_source(), false);
        let (tx, rx) = mpsc::channel();

        app.enter_comments_mode();
        app.maybe_request_comments(&tx);

        assert!(rx.try_recv().is_err());
        let comments = app.comments_text_for_selected();
        assert!(comments.contains("Comment 1/2"));
        assert!(comments.contains("mock-user-1"));
    }

    #[test]
    fn comment_navigation_wraps() {
        let mut app = App::new(mock_source(), false);
        let (tx, _) = mpsc::channel();

        app.enter_comments_mode();
        app.maybe_request_comments(&tx);
        app.next_comment();
        assert!(app.comments_text_for_selected().contains("Comment 2/2"));

        app.next_comment();
        assert!(app.comments_text_for_selected().contains("Comment 1/2"));

        app.prev_comment();
        assert!(app.comments_text_for_selected().contains("Comment 2/2"));
    }

    #[test]
    fn submit_comment_in_mock_mode_appends_new_comment() {
        let mut app = App::new(mock_source(), false);
        let (list_tx, _) = mpsc::channel();
        let (submit_tx, _) = mpsc::channel();

        app.enter_comments_mode();
        app.maybe_request_comments(&list_tx);
        app.start_comment_input();
        for ch in "hello from test".chars() {
            app.push_comment_input_char(ch);
        }
        app.submit_comment_input(&submit_tx);

        let text = app.comments_text_for_selected();
        assert!(text.contains("hello from test"));
        assert!(text.contains("Comment 3/3"));
        assert!(!app.in_comment_input_mode());
    }

    #[test]
    fn submit_comment_rejects_empty_body() {
        let mut app = App::new(mock_source(), false);
        let (submit_tx, _) = mpsc::channel();

        app.enter_comments_mode();
        app.start_comment_input();
        app.submit_comment_input(&submit_tx);

        assert_eq!(app.status_line, "Comment cannot be empty");
        assert!(app.in_comment_input_mode());
    }

    #[test]
    fn maybe_request_transitions_populates_mock_cache_without_worker_request() {
        let mut app = App::new(mock_source(), false);
        let (tx, rx) = mpsc::channel();

        app.enter_transitions_mode();
        app.maybe_request_transitions(&tx);

        assert!(rx.try_recv().is_err());
        let transitions = app.transitions_text_for_selected();
        assert!(transitions.contains("Transition 1/2"));
        assert!(transitions.contains("Start Progress"));
    }

    #[test]
    fn apply_transition_in_mock_mode_updates_issue_status() {
        let mut app = App::new(mock_source(), false);
        let (list_tx, _) = mpsc::channel();
        let (apply_tx, _) = mpsc::channel();

        app.enter_transitions_mode();
        app.maybe_request_transitions(&list_tx);
        app.next_transition();
        app.apply_selected_transition(&apply_tx);

        let issue = app.selected_issue().expect("selected issue");
        assert_eq!(issue.status, "Done");
        assert!(app.status_line.contains("Mock transition applied"));
    }

    #[test]
    fn actions_text_lists_key_shortcuts() {
        let mut app = App::new(mock_source(), false);
        app.enter_actions_mode();

        let text = app.actions_text();
        assert!(text.contains("c: comments pane"));
        assert!(text.contains("t: transitions pane"));
        assert!(text.contains("?: actions/help pane"));
    }
}
