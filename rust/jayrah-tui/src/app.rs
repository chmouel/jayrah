use std::{
    collections::HashMap,
    sync::mpsc::Sender,
    time::{Duration, Instant},
};

use crate::{
    adapter::{
        load_boards_from_adapter, load_custom_fields_from_adapter, load_issues_from_adapter,
        open_issue_in_browser,
    },
    mock::{
        mock_boards, mock_comments_for_issue, mock_custom_fields, mock_detail_from_issue,
        mock_issues, mock_transitions_for_issue,
    },
    telemetry,
    types::{
        AdapterSource, BoardEntry, CustomFieldEntry, Issue, IssueComment, IssueDetail,
        IssueTransition,
    },
    utils::{compact_error, join_or_dash},
};

const DETAIL_FETCH_DEBOUNCE_MS: u64 = 120;
const COMMENT_FETCH_DEBOUNCE_MS: u64 = 120;
const TRANSITION_FETCH_DEBOUNCE_MS: u64 = 120;
const PANE_RESIZE_STEP_PERCENT: u16 = 5;
const MIN_LEFT_PANE_PERCENT: u16 = 25;
const MAX_LEFT_PANE_PERCENT: u16 = 75;
const HORIZONTAL_FIRST_PANE_DEFAULT_PERCENT: u16 = 40;
const VERTICAL_FIRST_PANE_DEFAULT_PERCENT: u16 = 30;
const ACTIONS_DEFAULT_VIEWPORT_HEIGHT: u16 = 20;
const DETAIL_DEFAULT_VIEWPORT_HEIGHT: u16 = 20;

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
pub enum EditField {
    Summary,
    Description,
    Labels,
    Components,
    CustomField,
}

#[derive(Debug)]
pub struct EditIssueRequest {
    pub key: String,
    pub field: EditField,
    pub value: String,
    pub custom_field: Option<CustomFieldEntry>,
}

#[derive(Debug)]
pub struct EditIssueResult {
    pub key: String,
    pub field: EditField,
    pub value: String,
    pub custom_field: Option<CustomFieldEntry>,
    pub result: std::result::Result<(), String>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum DetailPaneMode {
    Detail,
    Comments,
    Transitions,
    Boards,
    CustomFields,
    Actions,
    EditMenu,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PaneOrientation {
    Horizontal,
    Vertical,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PaneZoom {
    None,
    Issues,
    Detail,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct StartupLayoutConfig {
    pub orientation: PaneOrientation,
    pub zoom: PaneZoom,
}

impl Default for StartupLayoutConfig {
    fn default() -> Self {
        Self {
            orientation: PaneOrientation::Horizontal,
            zoom: PaneZoom::None,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum SearchDirection {
    Forward,
    Backward,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DetailViewMode {
    EmptySelection,
    SummaryOnly,
    Loading,
    Error,
    Loaded,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DetailMetaField {
    pub label: &'static str,
    pub value: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DetailViewModel {
    pub mode: DetailViewMode,
    pub key: Option<String>,
    pub summary: String,
    pub meta_fields: Vec<DetailMetaField>,
    pub description: String,
    pub source: Option<String>,
    pub error_message: Option<String>,
}

fn meta_value<'a>(meta_fields: &'a [DetailMetaField], label: &str) -> Option<&'a str> {
    meta_fields
        .iter()
        .find_map(|field| (field.label == label).then_some(field.value.as_str()))
}

fn format_detail_view_model_plain_text(view: &DetailViewModel) -> String {
    match view.mode {
        DetailViewMode::EmptySelection => String::from("No issue selected"),
        DetailViewMode::Loaded => {
            let mut lines = Vec::new();
            if let Some(key) = &view.key {
                lines.push(format!("Key: {key}"));
            }
            lines.push(format!("Summary: {}", view.summary));
            for field in &view.meta_fields {
                lines.push(format!("{}: {}", field.label, field.value));
            }
            lines.push(String::new());
            lines.push(String::from("Description"));
            lines.extend(view.description.lines().map(ToString::to_string));
            lines.join("\n")
        }
        DetailViewMode::Error => {
            let key = view.key.as_deref().unwrap_or("<no issue>");
            let status = meta_value(&view.meta_fields, "Status").unwrap_or("-");
            let assignee = meta_value(&view.meta_fields, "Assignee").unwrap_or("-");
            let error_message = view.error_message.as_deref().unwrap_or("unknown error");
            format!(
                "Key: {key}\nStatus: {status}\nAssignee: {assignee}\n\nSummary\n{}\n\nDetail load failed\n{error_message}",
                view.summary
            )
        }
        DetailViewMode::Loading => {
            let key = view.key.as_deref().unwrap_or("<no issue>");
            let source = view.source.as_deref().unwrap_or("-");
            format!(
                "Loading detail for {key}...\n\nSummary\n{}\n\nSource\n{source}",
                view.summary
            )
        }
        DetailViewMode::SummaryOnly => {
            let key = view.key.as_deref().unwrap_or("<no issue>");
            let status = meta_value(&view.meta_fields, "Status").unwrap_or("-");
            let assignee = meta_value(&view.meta_fields, "Assignee").unwrap_or("-");
            let source = view.source.as_deref().unwrap_or("-");
            format!(
                "Key: {key}\nStatus: {status}\nAssignee: {assignee}\n\nSummary\n{}\n\nSource\n{source}",
                view.summary
            )
        }
    }
}

fn issue_matches_query(issue: &Issue, query: &str) -> bool {
    issue.key.to_lowercase().contains(query)
        || issue.summary.to_lowercase().contains(query)
        || issue.status.to_lowercase().contains(query)
        || issue.assignee.to_lowercase().contains(query)
}

#[derive(Debug)]
pub struct App {
    pub(crate) issues: Vec<Issue>,
    pub(crate) selected: usize,
    pub(crate) filter_mode: bool,
    pub(crate) filter_input: String,
    pub(crate) search_mode: bool,
    pub(crate) search_input: String,
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
    edit_input_mode: bool,
    edit_input: String,
    edit_target: EditField,
    active_custom_field: Option<CustomFieldEntry>,
    edit_submit_in_flight: bool,
    transitions_cache: HashMap<String, Vec<IssueTransition>>,
    transitions_errors: HashMap<String, String>,
    transitions_loading_key: Option<String>,
    transition_selected: usize,
    transition_apply_in_flight: bool,
    boards: Vec<BoardEntry>,
    board_selected: usize,
    custom_fields: Vec<CustomFieldEntry>,
    custom_field_selected: usize,
    edit_menu_selected: usize,
    pane_mode: DetailPaneMode,
    actions_scroll: u16,
    actions_viewport_height: u16,
    detail_scroll: u16,
    detail_viewport_height: u16,
    pane_orientation: PaneOrientation,
    pane_zoom: PaneZoom,
    horizontal_first_pane_percent: u16,
    vertical_first_pane_percent: u16,
    last_search_query: String,
    last_selected_key: Option<String>,
    selected_changed_at: Instant,
}

impl App {
    #[allow(dead_code)]
    pub fn new(source: AdapterSource, choose_mode: bool) -> Self {
        Self::new_with_layout(source, choose_mode, StartupLayoutConfig::default())
    }

    pub fn new_with_layout(
        source: AdapterSource,
        choose_mode: bool,
        startup_layout: StartupLayoutConfig,
    ) -> Self {
        let mut app = Self {
            issues: Vec::new(),
            selected: 0,
            filter_mode: false,
            filter_input: String::new(),
            search_mode: false,
            search_input: String::new(),
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
            edit_input_mode: false,
            edit_input: String::new(),
            edit_target: EditField::Summary,
            active_custom_field: None,
            edit_submit_in_flight: false,
            transitions_cache: HashMap::new(),
            transitions_errors: HashMap::new(),
            transitions_loading_key: None,
            transition_selected: 0,
            transition_apply_in_flight: false,
            boards: Vec::new(),
            board_selected: 0,
            custom_fields: Vec::new(),
            custom_field_selected: 0,
            edit_menu_selected: 0,
            pane_mode: DetailPaneMode::Detail,
            actions_scroll: 0,
            actions_viewport_height: ACTIONS_DEFAULT_VIEWPORT_HEIGHT,
            detail_scroll: 0,
            detail_viewport_height: DETAIL_DEFAULT_VIEWPORT_HEIGHT,
            pane_orientation: startup_layout.orientation,
            pane_zoom: startup_layout.zoom,
            horizontal_first_pane_percent: HORIZONTAL_FIRST_PANE_DEFAULT_PERCENT,
            vertical_first_pane_percent: VERTICAL_FIRST_PANE_DEFAULT_PERCENT,
            last_search_query: String::new(),
            last_selected_key: None,
            selected_changed_at: Instant::now(),
        };
        app.reload_issues();
        app.sync_selected_tracking();
        app
    }

    pub fn visible_indices(&self) -> Vec<usize> {
        let filter = self.filter_query().to_lowercase();
        if filter.is_empty() {
            return (0..self.issues.len()).collect();
        }

        self.issues
            .iter()
            .enumerate()
            .filter_map(|(idx, issue)| {
                if issue_matches_query(issue, &filter) {
                    Some(idx)
                } else {
                    None
                }
            })
            .collect()
    }

    pub fn has_active_filter(&self) -> bool {
        !self.filter_query().is_empty()
    }

    pub fn filter_query(&self) -> &str {
        self.filter_input.trim()
    }

    pub fn has_active_search_query(&self) -> bool {
        !self.last_search_query().is_empty()
    }

    pub fn search_query(&self) -> &str {
        self.search_input.trim()
    }

    pub fn last_search_query(&self) -> &str {
        self.last_search_query.trim()
    }

    fn visible_match_positions(&self, query: &str) -> Vec<usize> {
        let query = query.trim().to_lowercase();
        if query.is_empty() {
            return Vec::new();
        }

        self.visible_indices()
            .iter()
            .enumerate()
            .filter_map(|(position, issue_index)| {
                let issue = self.issues.get(*issue_index)?;
                if issue_matches_query(issue, &query) {
                    Some(position)
                } else {
                    None
                }
            })
            .collect()
    }

    fn jump_to_search_match(
        &mut self,
        query: &str,
        direction: SearchDirection,
        include_current: bool,
    ) -> bool {
        let visible_len = self.visible_indices().len();
        if visible_len == 0 {
            return false;
        }

        let matches = self.visible_match_positions(query);
        if matches.is_empty() {
            return false;
        }

        let current = self.selected.min(visible_len.saturating_sub(1));
        let fallback_forward = matches.first().copied().unwrap_or(current);
        let fallback_backward = matches.last().copied().unwrap_or(current);
        let target = match direction {
            SearchDirection::Forward => {
                if include_current {
                    matches
                        .iter()
                        .copied()
                        .find(|position| *position >= current)
                        .unwrap_or(fallback_forward)
                } else {
                    matches
                        .iter()
                        .copied()
                        .find(|position| *position > current)
                        .unwrap_or(fallback_forward)
                }
            }
            SearchDirection::Backward => {
                if include_current {
                    matches
                        .iter()
                        .copied()
                        .rev()
                        .find(|position| *position <= current)
                        .unwrap_or(fallback_backward)
                } else {
                    matches
                        .iter()
                        .copied()
                        .rev()
                        .find(|position| *position < current)
                        .unwrap_or(fallback_backward)
                }
            }
        };

        self.selected = target;
        true
    }

    pub fn submit_search_query(&mut self) {
        self.last_search_query = self.search_query().to_string();
        if self.last_search_query.is_empty() {
            self.status_line = "Search query is empty".to_string();
            return;
        }

        let query = self.last_search_query.clone();
        if self.jump_to_search_match(query.as_str(), SearchDirection::Forward, true) {
            if let Some(key) = self.selected_issue_key() {
                self.status_line = format!("Search '{}': {key}", query);
            } else {
                self.status_line = format!("Search '{}': match selected", query);
            }
        } else {
            self.status_line = format!("Search '{}' found no matches", query);
        }
    }

    pub fn repeat_last_search_forward(&mut self) {
        self.repeat_last_search(SearchDirection::Forward);
    }

    pub fn repeat_last_search_backward(&mut self) {
        self.repeat_last_search(SearchDirection::Backward);
    }

    fn repeat_last_search(&mut self, direction: SearchDirection) {
        if self.last_search_query().is_empty() {
            self.status_line = "No previous search. Press / to search".to_string();
            return;
        }

        let query = self.last_search_query().to_string();
        if self.jump_to_search_match(query.as_str(), direction, false) {
            if let Some(key) = self.selected_issue_key() {
                let label = match direction {
                    SearchDirection::Forward => "next",
                    SearchDirection::Backward => "prev",
                };
                self.status_line = format!("Search {label} '{}': {key}", query);
            }
        } else {
            self.status_line = format!("Search '{}' found no matches", query);
        }
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

    pub fn select_visible_row(&mut self, row_index: usize) -> bool {
        let len = self.visible_indices().len();
        if len == 0 {
            self.selected = 0;
            return false;
        }

        self.selected = row_index.min(len - 1);
        self.sync_selected_tracking();
        true
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

    pub fn in_boards_mode(&self) -> bool {
        self.pane_mode == DetailPaneMode::Boards
    }

    pub fn in_custom_fields_mode(&self) -> bool {
        self.pane_mode == DetailPaneMode::CustomFields
    }

    pub fn in_actions_mode(&self) -> bool {
        self.pane_mode == DetailPaneMode::Actions
    }

    pub fn in_edit_menu_mode(&self) -> bool {
        self.pane_mode == DetailPaneMode::EditMenu
    }

    pub fn in_popup_mode(&self) -> bool {
        self.pane_mode != DetailPaneMode::Detail
    }

    pub fn in_comment_input_mode(&self) -> bool {
        self.comment_input_mode
    }

    pub fn in_edit_input_mode(&self) -> bool {
        self.edit_input_mode
    }

    pub fn comment_input(&self) -> &str {
        self.comment_input.as_str()
    }

    pub fn edit_input(&self) -> &str {
        self.edit_input.as_str()
    }

    pub fn set_edit_input(&mut self, value: String) {
        self.edit_input = value;
    }

    pub fn edit_target_label(&self) -> &'static str {
        match self.edit_target {
            EditField::Summary => "summary",
            EditField::Description => "description",
            EditField::Labels => "labels",
            EditField::Components => "components",
            EditField::CustomField => "custom field",
        }
    }

    pub fn edit_target_display(&self) -> String {
        if self.edit_target == EditField::CustomField {
            if let Some(field) = &self.active_custom_field {
                return format!("custom field: {}", field.name);
            }
        }
        self.edit_target_label().to_string()
    }

    pub fn enter_comments_mode(&mut self) {
        self.pane_mode = DetailPaneMode::Comments;
        self.comments_selected = 0;
        self.transition_selected = 0;
        self.status_line =
            "Comments mode: j/k or n/p navigate comments, c or Esc to close".to_string();
    }

    pub fn enter_transitions_mode(&mut self) {
        self.pane_mode = DetailPaneMode::Transitions;
        self.comment_input_mode = false;
        self.comment_input.clear();
        self.transition_selected = 0;
        self.status_line =
            "Transitions mode: j/k or n/p select transition, Enter apply, t or Esc close"
                .to_string();
    }

    pub fn enter_boards_mode(&mut self) {
        self.pane_mode = DetailPaneMode::Boards;
        self.comment_input_mode = false;
        self.comment_input.clear();
        self.load_boards();
        if !self.boards.is_empty() {
            self.status_line =
                "Boards mode: j/k or n/p select board, Enter apply, b or Esc close".to_string();
        }
    }

    pub fn enter_custom_fields_mode(&mut self) {
        self.pane_mode = DetailPaneMode::CustomFields;
        self.comment_input_mode = false;
        self.comment_input.clear();
        self.edit_input_mode = false;
        self.edit_input.clear();
        self.active_custom_field = None;
        self.load_custom_fields();
        if !self.custom_fields.is_empty() {
            self.status_line =
                "Custom fields mode: j/k or n/p select field, Enter edit, u or Esc close"
                    .to_string();
        }
    }

    pub fn enter_edit_menu_mode(&mut self) {
        self.pane_mode = DetailPaneMode::EditMenu;
        self.comment_input_mode = false;
        self.comment_input.clear();
        self.edit_input_mode = false;
        self.edit_input.clear();
        self.active_custom_field = None;
        self.edit_menu_selected = 0;
        self.status_line =
            "Edit menu: j/k or n/p select field, Enter edit, e or Esc close".to_string();
    }

    pub fn enter_actions_mode(&mut self) {
        self.pane_mode = DetailPaneMode::Actions;
        self.comment_input_mode = false;
        self.comment_input.clear();
        self.actions_scroll = 0;
        self.status_line =
            "Actions popup: j/k scroll, Ctrl+d/Ctrl+u page, ? or Esc close".to_string();
    }

    pub fn enter_detail_mode(&mut self) {
        self.pane_mode = DetailPaneMode::Detail;
        self.comment_input_mode = false;
        self.comment_input.clear();
        self.edit_input_mode = false;
        self.edit_input.clear();
        self.active_custom_field = None;
        self.status_line = "Detail mode".to_string();
    }

    fn actions_max_scroll(&self) -> u16 {
        let viewport_height = usize::from(self.actions_viewport_height.max(1));
        let content_lines = self.actions_text().lines().count();
        u16::try_from(content_lines.saturating_sub(viewport_height)).unwrap_or(u16::MAX)
    }

    fn detail_max_scroll(&self) -> u16 {
        let viewport_height = usize::from(self.detail_viewport_height.max(1));
        let content_lines = self.detail_text_for_selected().lines().count();
        u16::try_from(content_lines.saturating_sub(viewport_height)).unwrap_or(u16::MAX)
    }

    pub fn actions_scroll(&self) -> u16 {
        self.actions_scroll.min(self.actions_max_scroll())
    }

    pub fn actions_half_page_step(&self) -> u16 {
        (self.actions_viewport_height / 2).max(1)
    }

    pub fn detail_scroll(&self) -> u16 {
        self.detail_scroll.min(self.detail_max_scroll())
    }

    pub fn detail_half_page_step(&self) -> u16 {
        (self.detail_viewport_height / 2).max(1)
    }

    pub fn set_actions_viewport_height(&mut self, viewport_height: u16) {
        self.actions_viewport_height = viewport_height.max(1);
        self.actions_scroll = self.actions_scroll.min(self.actions_max_scroll());
    }

    pub fn set_detail_viewport_height(&mut self, viewport_height: u16) {
        self.detail_viewport_height = viewport_height.max(1);
        self.detail_scroll = self.detail_scroll.min(self.detail_max_scroll());
    }

    pub fn scroll_actions_down(&mut self, lines: u16) {
        let next = self.actions_scroll.saturating_add(lines.max(1));
        self.actions_scroll = next.min(self.actions_max_scroll());
    }

    pub fn scroll_actions_up(&mut self, lines: u16) {
        self.actions_scroll = self.actions_scroll.saturating_sub(lines.max(1));
    }

    pub fn scroll_detail_down(&mut self, lines: u16) {
        let next = self.detail_scroll.saturating_add(lines.max(1));
        self.detail_scroll = next.min(self.detail_max_scroll());
    }

    pub fn scroll_detail_up(&mut self, lines: u16) {
        self.detail_scroll = self.detail_scroll.saturating_sub(lines.max(1));
    }

    pub fn start_comment_input(&mut self) {
        if !self.in_comments_mode() {
            return;
        }
        if self.comment_submit_in_flight {
            self.status_line = "Comment submission in progress...".to_string();
            return;
        }

        self.edit_input_mode = false;
        self.edit_input.clear();
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

    pub fn start_summary_edit_input(&mut self) {
        self.start_edit_input(EditField::Summary);
    }

    pub fn start_description_edit_input(&mut self) {
        self.start_edit_input(EditField::Description);
    }

    pub fn start_labels_edit_input(&mut self) {
        self.start_edit_input(EditField::Labels);
    }

    pub fn start_components_edit_input(&mut self) {
        self.start_edit_input(EditField::Components);
    }

    pub fn start_selected_custom_field_edit_input(&mut self) {
        if self.custom_fields.is_empty() {
            self.status_line = "No custom fields configured".to_string();
            return;
        }

        let selected_index = self.custom_field_selected.min(self.custom_fields.len() - 1);
        self.active_custom_field = Some(self.custom_fields[selected_index].clone());
        self.start_edit_input(EditField::CustomField);
    }

    fn start_edit_input(&mut self, field: EditField) {
        if self.edit_submit_in_flight {
            self.status_line = "Issue update in progress...".to_string();
            return;
        }

        let Some(issue) = self.selected_issue() else {
            self.status_line = "No issue selected".to_string();
            return;
        };
        let issue_key = issue.key.clone();
        let issue_summary = issue.summary.clone();

        self.comment_input_mode = false;
        self.comment_input.clear();
        self.edit_input_mode = true;
        self.edit_target = field;
        if field != EditField::CustomField {
            self.active_custom_field = None;
        }
        let initial_input = match field {
            EditField::Summary => issue_summary,
            EditField::Description => self
                .detail_cache
                .get(&issue_key)
                .map(|detail| detail.description.clone())
                .unwrap_or_default(),
            EditField::Labels => self
                .detail_cache
                .get(&issue_key)
                .map(|detail| detail.labels.join(", "))
                .unwrap_or_default(),
            EditField::Components => self
                .detail_cache
                .get(&issue_key)
                .map(|detail| detail.components.join(", "))
                .unwrap_or_default(),
            EditField::CustomField => String::new(),
        };
        self.edit_input = Self::normalize_edit_input_seed(initial_input);
        self.status_line = format!(
            "Editing {}: Ctrl+s save, Esc cancel",
            self.edit_target_label()
        );
    }

    pub fn cancel_edit_input(&mut self) {
        self.edit_input_mode = false;
        self.edit_input.clear();
        self.active_custom_field = None;
        self.status_line = "Edit canceled".to_string();
    }

    fn normalize_edit_value(&self, value: String) -> String {
        match self.edit_target {
            EditField::Summary => value
                .replace(['\r', '\n'], " ")
                .split_whitespace()
                .collect::<Vec<_>>()
                .join(" "),
            EditField::Labels | EditField::Components => value.replace(['\r', '\n'], ","),
            EditField::Description | EditField::CustomField => value,
        }
    }

    fn normalize_edit_input_seed(value: String) -> String {
        value.replace("\r\n", "\n").replace('\r', "\n")
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

    pub fn next_board(&mut self) {
        if self.boards.is_empty() {
            return;
        }
        self.board_selected = (self.board_selected + 1) % self.boards.len();
    }

    pub fn prev_board(&mut self) {
        if self.boards.is_empty() {
            return;
        }
        self.board_selected = if self.board_selected == 0 {
            self.boards.len() - 1
        } else {
            self.board_selected - 1
        };
    }

    pub fn next_custom_field(&mut self) {
        if self.custom_fields.is_empty() {
            return;
        }
        self.custom_field_selected = (self.custom_field_selected + 1) % self.custom_fields.len();
    }

    pub fn prev_custom_field(&mut self) {
        if self.custom_fields.is_empty() {
            return;
        }
        self.custom_field_selected = if self.custom_field_selected == 0 {
            self.custom_fields.len() - 1
        } else {
            self.custom_field_selected - 1
        };
    }

    pub fn next_edit_menu(&mut self) {
        const EDIT_MENU_COUNT: usize = 4;
        self.edit_menu_selected = (self.edit_menu_selected + 1) % EDIT_MENU_COUNT;
    }

    pub fn prev_edit_menu(&mut self) {
        const EDIT_MENU_COUNT: usize = 4;
        self.edit_menu_selected = if self.edit_menu_selected == 0 {
            EDIT_MENU_COUNT - 1
        } else {
            self.edit_menu_selected - 1
        };
    }

    pub fn apply_selected_edit_menu(&mut self) {
        match self.edit_menu_selected {
            0 => self.start_summary_edit_input(),
            1 => self.start_description_edit_input(),
            2 => self.start_labels_edit_input(),
            3 => self.start_components_edit_input(),
            _ => {}
        }
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
        self.edit_input_mode = false;
        self.edit_input.clear();
        self.edit_target = EditField::Summary;
        self.active_custom_field = None;
        self.edit_submit_in_flight = false;
        self.transitions_cache.clear();
        self.transitions_errors.clear();
        self.transitions_loading_key = None;
        self.transition_selected = 0;
        self.transition_apply_in_flight = false;
        self.custom_fields.clear();
        self.custom_field_selected = 0;
        self.edit_menu_selected = 0;
        self.detail_scroll = 0;

        if self.source.mock_only {
            self.issues = mock_issues(self.reload_count);
            self.using_adapter = false;
            self.status_line = format!("Reloaded mock issues ({})", self.reload_count);
            self.normalize_selection_with_preferred_key(preferred_key.as_deref());
            return;
        }

        let started = Instant::now();
        match load_issues_from_adapter(&self.source) {
            Ok(issues) => {
                telemetry::emit_success("issues.reload", None, started.elapsed());
                self.using_adapter = true;
                self.issues = issues;
                self.status_line = format!(
                    "Loaded {} issues from adapter ({})",
                    self.issues.len(),
                    self.source.describe()
                );
            }
            Err(error) => {
                telemetry::emit_failure(
                    "issues.reload",
                    None,
                    started.elapsed(),
                    &error.to_string(),
                );
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
            self.edit_input_mode = false;
            self.edit_input.clear();
            self.active_custom_field = None;
            self.transition_selected = 0;
            self.custom_field_selected = 0;
            self.edit_menu_selected = 0;
            self.detail_scroll = 0;
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

    fn load_boards(&mut self) {
        if self.source.mock_only {
            self.boards = mock_boards();
        } else {
            let started = Instant::now();
            match load_boards_from_adapter() {
                Ok(boards) => {
                    telemetry::emit_success("boards.load", None, started.elapsed());
                    self.boards = boards;
                }
                Err(error) => {
                    telemetry::emit_failure(
                        "boards.load",
                        None,
                        started.elapsed(),
                        &error.to_string(),
                    );
                    self.boards.clear();
                    self.status_line = format!(
                        "Failed to load boards ({})",
                        compact_error(&error.to_string())
                    );
                    return;
                }
            }
        }

        if self.boards.is_empty() {
            self.status_line = "No boards configured".to_string();
            self.board_selected = 0;
            return;
        }

        if let Some(current_board) = self.source.board.as_deref() {
            if let Some(position) = self
                .boards
                .iter()
                .position(|board| board.name.as_str() == current_board)
            {
                self.board_selected = position;
                return;
            }
        }

        self.board_selected = 0;
    }

    fn load_custom_fields(&mut self) {
        if self.source.mock_only {
            self.custom_fields = mock_custom_fields();
        } else {
            let started = Instant::now();
            match load_custom_fields_from_adapter() {
                Ok(fields) => {
                    telemetry::emit_success("custom_fields.load", None, started.elapsed());
                    self.custom_fields = fields;
                }
                Err(error) => {
                    telemetry::emit_failure(
                        "custom_fields.load",
                        None,
                        started.elapsed(),
                        &error.to_string(),
                    );
                    self.custom_fields.clear();
                    self.status_line = format!(
                        "Failed to load custom fields ({})",
                        compact_error(&error.to_string())
                    );
                    return;
                }
            }
        }

        if self.custom_fields.is_empty() {
            self.status_line = "No custom fields configured".to_string();
            self.custom_field_selected = 0;
            return;
        }

        self.custom_field_selected = 0;
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

    pub fn submit_edit_input(&mut self, submit_tx: &Sender<EditIssueRequest>) {
        self.submit_edit_value(self.edit_input.clone(), submit_tx);
    }

    pub fn submit_edit_value(&mut self, value: String, submit_tx: &Sender<EditIssueRequest>) {
        let Some(key) = self.selected_issue_key() else {
            self.status_line = "No issue selected".to_string();
            return;
        };

        let value = self.normalize_edit_value(value);
        if self.edit_target == EditField::Summary && value.trim().is_empty() {
            self.status_line = "Summary cannot be empty".to_string();
            return;
        }

        if self.edit_submit_in_flight {
            self.status_line = "Issue update in progress...".to_string();
            return;
        }

        if !self.using_adapter {
            match self.edit_target {
                EditField::Summary => {
                    self.update_issue_summary(&key, &value);
                    self.detail_cache.remove(&key);
                }
                EditField::Description => {
                    if let Some(detail) = self.detail_cache.get_mut(&key) {
                        detail.description = value.clone();
                    }
                }
                EditField::Labels => {
                    if let Some(detail) = self.detail_cache.get_mut(&key) {
                        detail.labels = Self::csv_to_values(&value);
                    }
                }
                EditField::Components => {
                    if let Some(detail) = self.detail_cache.get_mut(&key) {
                        detail.components = Self::csv_to_values(&value);
                    }
                }
                EditField::CustomField => {}
            }
            self.edit_input_mode = false;
            self.edit_input.clear();
            self.status_line = format!("Updated {} in mock mode", self.edit_target_label());
            return;
        }

        if submit_tx
            .send(EditIssueRequest {
                key: key.clone(),
                field: self.edit_target,
                value: value.clone(),
                custom_field: if self.edit_target == EditField::CustomField {
                    self.active_custom_field.clone()
                } else {
                    None
                },
            })
            .is_ok()
        {
            self.edit_submit_in_flight = true;
            self.edit_input_mode = false;
            self.edit_input.clear();
            self.status_line = format!("Updating {} for {}...", self.edit_target_label(), key);
        } else {
            self.status_line = format!("Failed to queue issue update for {key}");
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

    pub fn apply_selected_board(&mut self) {
        if self.boards.is_empty() {
            self.status_line = "No boards available".to_string();
            return;
        }

        let selected_index = self.board_selected.min(self.boards.len() - 1);
        let selected = self.boards[selected_index].clone();
        let replaced_query_mode = self.source.query.is_some();
        self.source.board = Some(selected.name.clone());
        self.source.query = None;
        self.enter_detail_mode();
        self.reload_issues();
        self.status_line = if replaced_query_mode {
            format!(
                "Switched to board '{}' (replaced active raw query mode)",
                selected.name
            )
        } else {
            format!("Switched to board '{}'", selected.name)
        };
    }

    fn update_issue_status(&mut self, key: &str, status: &str) {
        if let Some(issue) = self.issues.iter_mut().find(|issue| issue.key == key) {
            issue.status = status.to_string();
        }
    }

    fn update_issue_summary(&mut self, key: &str, summary: &str) {
        if let Some(issue) = self.issues.iter_mut().find(|issue| issue.key == key) {
            issue.summary = summary.to_string();
        }
    }

    fn csv_to_values(value: &str) -> Vec<String> {
        value
            .split(',')
            .map(|entry| entry.trim())
            .filter(|entry| !entry.is_empty())
            .map(|entry| entry.to_string())
            .collect()
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

    pub fn ingest_edit_issue_result(&mut self, message: EditIssueResult) {
        self.edit_submit_in_flight = false;
        self.active_custom_field = None;
        match message.result {
            Ok(()) => {
                match message.field {
                    EditField::Summary => {
                        self.update_issue_summary(&message.key, &message.value);
                        self.detail_cache.remove(&message.key);
                    }
                    EditField::Description => {
                        if let Some(detail) = self.detail_cache.get_mut(&message.key) {
                            detail.description = message.value.clone();
                        } else {
                            self.detail_cache.remove(&message.key);
                        }
                    }
                    EditField::Labels => {
                        if let Some(detail) = self.detail_cache.get_mut(&message.key) {
                            detail.labels = Self::csv_to_values(&message.value);
                        } else {
                            self.detail_cache.remove(&message.key);
                        }
                    }
                    EditField::Components => {
                        if let Some(detail) = self.detail_cache.get_mut(&message.key) {
                            detail.components = Self::csv_to_values(&message.value);
                        } else {
                            self.detail_cache.remove(&message.key);
                        }
                    }
                    EditField::CustomField => {}
                }
                if self.selected_issue_key().as_deref() == Some(message.key.as_str()) {
                    self.status_line = format!(
                        "Updated {} for {}",
                        match message.field {
                            EditField::Summary => "summary",
                            EditField::Description => "description",
                            EditField::Labels => "labels",
                            EditField::Components => "components",
                            EditField::CustomField => message
                                .custom_field
                                .as_ref()
                                .map(|field| field.name.as_str())
                                .unwrap_or("custom field"),
                        },
                        message.key
                    );
                }
            }
            Err(error) => {
                if self.selected_issue_key().as_deref() == Some(message.key.as_str()) {
                    self.status_line = format!(
                        "Failed to update {} ({})",
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
        format_detail_view_model_plain_text(&self.detail_view_model_for_selected())
    }

    pub fn detail_view_model_for_selected(&self) -> DetailViewModel {
        let Some(issue) = self.selected_issue() else {
            return DetailViewModel {
                mode: DetailViewMode::EmptySelection,
                key: None,
                summary: String::new(),
                meta_fields: Vec::new(),
                description: String::new(),
                source: None,
                error_message: None,
            };
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

            return DetailViewModel {
                mode: DetailViewMode::Loaded,
                key: Some(detail.key.clone()),
                summary: detail.summary.clone(),
                meta_fields: vec![
                    DetailMetaField {
                        label: "Status",
                        value: detail.status.clone(),
                    },
                    DetailMetaField {
                        label: "Priority",
                        value: detail.priority.clone(),
                    },
                    DetailMetaField {
                        label: "Type",
                        value: detail.issue_type.clone(),
                    },
                    DetailMetaField {
                        label: "Assignee",
                        value: detail.assignee.clone(),
                    },
                    DetailMetaField {
                        label: "Reporter",
                        value: detail.reporter.clone(),
                    },
                    DetailMetaField {
                        label: "Created",
                        value: detail.created.clone(),
                    },
                    DetailMetaField {
                        label: "Updated",
                        value: detail.updated.clone(),
                    },
                    DetailMetaField {
                        label: "Labels",
                        value: labels,
                    },
                    DetailMetaField {
                        label: "Components",
                        value: components,
                    },
                    DetailMetaField {
                        label: "Fix Versions",
                        value: fix_versions,
                    },
                ],
                description: description.to_string(),
                source: None,
                error_message: None,
            };
        }

        if let Some(error) = self.detail_errors.get(key) {
            return DetailViewModel {
                mode: DetailViewMode::Error,
                key: Some(issue.key.clone()),
                summary: issue.summary.clone(),
                meta_fields: vec![
                    DetailMetaField {
                        label: "Status",
                        value: issue.status.clone(),
                    },
                    DetailMetaField {
                        label: "Assignee",
                        value: issue.assignee.clone(),
                    },
                ],
                description: String::new(),
                source: None,
                error_message: Some(compact_error(error)),
            };
        }

        if self.detail_loading_key.as_deref() == Some(key) {
            return DetailViewModel {
                mode: DetailViewMode::Loading,
                key: Some(issue.key.clone()),
                summary: issue.summary.clone(),
                meta_fields: Vec::new(),
                description: String::new(),
                source: Some(self.source.describe()),
                error_message: None,
            };
        }

        DetailViewModel {
            mode: DetailViewMode::SummaryOnly,
            key: Some(issue.key.clone()),
            summary: issue.summary.clone(),
            meta_fields: vec![
                DetailMetaField {
                    label: "Status",
                    value: issue.status.clone(),
                },
                DetailMetaField {
                    label: "Assignee",
                    value: issue.assignee.clone(),
                },
            ],
            description: String::new(),
            source: Some(self.source.describe()),
            error_message: None,
        }
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
                    "Transitions for {}\n\nTransition {}/{}\nName: {}\nTo: {}\nDescription: {}\n\nUse j/k or n/p to choose and Enter to apply.",
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

    pub fn boards_text(&self) -> String {
        if self.boards.is_empty() {
            return "No boards loaded.\n\nPress b to retry loading configured boards.".to_string();
        }

        let current_source = if let Some(board) = self.source.board.as_deref() {
            board.to_string()
        } else if self.source.query.is_some() {
            "<raw query mode>".to_string()
        } else {
            "myissue".to_string()
        };
        let mut out = format!(
            "Configured Boards\nCurrent: {}\n\nUse j/k or n/p to choose and Enter to switch.\n\n",
            current_source
        );
        if self.source.query.is_some() {
            out.push_str("Note: switching boards will replace the active raw query.\n\n");
        }
        for (index, board) in self.boards.iter().enumerate() {
            let marker = if index == self.board_selected {
                ">"
            } else {
                " "
            };
            out.push_str(&format!(
                "{marker} {} - {}\n",
                board.name, board.description
            ));
        }
        out
    }

    pub fn custom_fields_text(&self) -> String {
        if self.custom_fields.is_empty() {
            return "No custom fields configured.\n\nPress u to retry loading configured custom fields."
                .to_string();
        }

        let mut out = "Configured Custom Fields\n\nUse j/k or n/p to choose and Enter to edit selected field.\n\n".to_string();
        for (index, field) in self.custom_fields.iter().enumerate() {
            let marker = if index == self.custom_field_selected {
                ">"
            } else {
                " "
            };
            out.push_str(&format!(
                "{marker} {} ({}, {}) - {}\n",
                field.name, field.field_id, field.field_type, field.description
            ));
        }
        out
    }

    pub fn edit_menu_text(&self) -> String {
        let items = ["Summary", "Description", "Labels", "Components"];
        let mut out =
            "Edit Issue Fields\n\nUse j/k or n/p to choose and Enter to edit selected field.\n\n"
                .to_string();
        for (index, item) in items.iter().enumerate() {
            let marker = if index == self.edit_menu_selected {
                ">"
            } else {
                " "
            };
            out.push_str(&format!("{marker} {item}\n"));
        }
        out
    }

    pub fn actions_text(&self) -> String {
        let mode = if self.choose_mode { "choose" } else { "normal" };
        format!(
            "Jayrah Actions ({mode} mode)\n\nNavigation (detail mode)\n  j/k or arrows: move issue selection\n  J/K: scroll detail pane\n  Ctrl+d/Ctrl+u: page detail pane down/up\n  TAB: toggle horizontal/vertical layout\n  Alt+h/Alt+l: resize first/second pane\n  1: toggle issues pane zoom\n  2: toggle detail pane zoom\n  f: filter issues\n  /: search visible issues\n  n/N: next/previous search match\n  r: reload issues\n\nIssue Actions\n  o: open selected issue in browser\n  e: edit menu popup (summary/description/labels/components)\n  u: custom field editor popup\n  b: board switcher popup\n  c: comments popup\n  t: transitions popup\n  ?: actions/help popup\n\nActions Popup\n  j/k or arrows: scroll help\n  Ctrl+d/Ctrl+u: page down/up\n\nEdit Menu Popup\n  j/k or n/p: previous/next editable field\n  Enter: edit selected field\n\nComments Popup\n  j/k or n/p: previous/next comment\n  a: compose comment\n  Enter: submit comment draft\n\nTransitions Popup\n  j/k or n/p: previous/next transition\n  Enter: apply selected transition\n\nBoards Popup\n  j/k or n/p: previous/next board\n  Enter: switch active board\n\nCustom Fields Popup\n  j/k or n/p: previous/next field\n  Enter: edit selected custom field\n\nGlobal\n  q: quit (or close active popup)\n  Esc: close active popup; clear filter/search while focused"
        )
    }

    pub fn right_pane_text(&self) -> String {
        match self.pane_mode {
            DetailPaneMode::Detail => self.detail_text_for_selected(),
            DetailPaneMode::Comments => self.comments_text_for_selected(),
            DetailPaneMode::Transitions => self.transitions_text_for_selected(),
            DetailPaneMode::Boards => self.boards_text(),
            DetailPaneMode::CustomFields => self.custom_fields_text(),
            DetailPaneMode::Actions => self.actions_text(),
            DetailPaneMode::EditMenu => self.edit_menu_text(),
        }
    }

    pub fn right_pane_title(&self) -> &'static str {
        match self.pane_mode {
            DetailPaneMode::Detail => "Detail",
            DetailPaneMode::Comments => "Comments",
            DetailPaneMode::Transitions => "Transitions",
            DetailPaneMode::Boards => "Boards",
            DetailPaneMode::CustomFields => "Custom Fields",
            DetailPaneMode::Actions => "Actions",
            DetailPaneMode::EditMenu => "Edit",
        }
    }

    pub fn pane_width_percentages(&self) -> (u16, u16) {
        let first_pane_percent = self.active_first_pane_percent();
        (first_pane_percent, 100u16 - first_pane_percent)
    }

    pub fn pane_orientation(&self) -> PaneOrientation {
        self.pane_orientation
    }

    pub fn pane_zoom(&self) -> PaneZoom {
        self.pane_zoom
    }

    pub fn toggle_zoom_issues(&mut self) {
        self.pane_zoom = if self.pane_zoom == PaneZoom::Issues {
            PaneZoom::None
        } else {
            PaneZoom::Issues
        };
        self.status_line = match self.pane_zoom {
            PaneZoom::None => "Pane zoom: split".to_string(),
            PaneZoom::Issues => "Pane zoom: issues".to_string(),
            PaneZoom::Detail => "Pane zoom: detail".to_string(),
        };
    }

    pub fn toggle_zoom_detail(&mut self) {
        self.pane_zoom = if self.pane_zoom == PaneZoom::Detail {
            PaneZoom::None
        } else {
            PaneZoom::Detail
        };
        self.status_line = match self.pane_zoom {
            PaneZoom::None => "Pane zoom: split".to_string(),
            PaneZoom::Issues => "Pane zoom: issues".to_string(),
            PaneZoom::Detail => "Pane zoom: detail".to_string(),
        };
    }

    pub fn toggle_pane_orientation(&mut self) {
        self.pane_orientation = match self.pane_orientation {
            PaneOrientation::Horizontal => PaneOrientation::Vertical,
            PaneOrientation::Vertical => PaneOrientation::Horizontal,
        };
        let layout = match self.pane_orientation {
            PaneOrientation::Horizontal => "horizontal",
            PaneOrientation::Vertical => "vertical",
        };
        self.status_line = format!("Layout: {layout}");
    }

    fn active_first_pane_percent(&self) -> u16 {
        match self.pane_orientation {
            PaneOrientation::Horizontal => self.horizontal_first_pane_percent,
            PaneOrientation::Vertical => self.vertical_first_pane_percent,
        }
    }

    fn set_active_first_pane_percent(&mut self, value: u16) {
        match self.pane_orientation {
            PaneOrientation::Horizontal => self.horizontal_first_pane_percent = value,
            PaneOrientation::Vertical => self.vertical_first_pane_percent = value,
        }
    }

    pub fn grow_left_pane(&mut self) {
        let new_value = self
            .active_first_pane_percent()
            .saturating_add(PANE_RESIZE_STEP_PERCENT)
            .min(MAX_LEFT_PANE_PERCENT);
        self.set_active_first_pane_percent(new_value);
        self.status_line = format!(
            "Pane resize: first {}% | second {}%",
            new_value,
            100u16 - new_value
        );
    }

    pub fn grow_right_pane(&mut self) {
        let new_value = self
            .active_first_pane_percent()
            .saturating_sub(PANE_RESIZE_STEP_PERCENT)
            .max(MIN_LEFT_PANE_PERCENT);
        self.set_active_first_pane_percent(new_value);
        self.status_line = format!(
            "Pane resize: first {}% | second {}%",
            new_value,
            100u16 - new_value
        );
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

        let started = Instant::now();
        match open_issue_in_browser(&key) {
            Ok(()) => {
                telemetry::emit_success(
                    "issue.open_browser",
                    Some(key.as_str()),
                    started.elapsed(),
                );
                self.status_line = format!("Opened {key} in browser");
            }
            Err(error) => {
                telemetry::emit_failure(
                    "issue.open_browser",
                    Some(key.as_str()),
                    started.elapsed(),
                    &error.to_string(),
                );
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

    use super::{
        App, DetailViewMode, PaneOrientation, PaneZoom, StartupLayoutConfig, MAX_LEFT_PANE_PERCENT,
        MIN_LEFT_PANE_PERCENT,
    };
    use crate::types::AdapterSource;

    fn mock_source() -> AdapterSource {
        AdapterSource {
            board: None,
            query: None,
            mock_only: true,
        }
    }

    fn mock_query_source() -> AdapterSource {
        AdapterSource {
            board: None,
            query: Some("project = DEMO".to_string()),
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
    fn submit_search_query_selects_first_match_from_current_position() {
        let mut app = App::new(mock_source(), false);
        app.selected = 1;
        app.search_input = "measure".to_string();

        app.submit_search_query();

        assert_eq!(app.selected_issue_key().as_deref(), Some("JAY-104"));
        assert!(app.status_line.contains("Search 'measure'"));
        assert_eq!(app.last_search_query(), "measure");
    }

    #[test]
    fn repeat_search_wraps_forward_and_backward() {
        let mut app = App::new(mock_source(), false);
        app.search_input = "jay".to_string();
        app.submit_search_query();
        assert_eq!(app.selected_issue_key().as_deref(), Some("JAY-101"));

        app.repeat_last_search_forward();
        assert_eq!(app.selected_issue_key().as_deref(), Some("JAY-102"));

        app.repeat_last_search_backward();
        assert_eq!(app.selected_issue_key().as_deref(), Some("JAY-101"));

        app.repeat_last_search_backward();
        assert_eq!(app.selected_issue_key().as_deref(), Some("JAY-104"));
    }

    #[test]
    fn submit_search_uses_visible_rows_after_filter() {
        let mut app = App::new(mock_source(), false);
        app.filter_input = "adapter".to_string();
        app.normalize_selection();
        app.search_input = "jay-103".to_string();

        app.submit_search_query();

        assert_eq!(app.selected_issue_key().as_deref(), Some("JAY-102"));
        assert!(app.status_line.contains("found no matches"));
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
    fn detail_view_model_loaded_contains_expected_sections() {
        let mut app = App::new(mock_source(), false);
        let (tx, _) = mpsc::channel();
        app.maybe_request_detail(&tx);

        let view = app.detail_view_model_for_selected();
        assert_eq!(view.mode, DetailViewMode::Loaded);
        assert_eq!(view.key.as_deref(), Some("JAY-101"));
        assert!(view
            .meta_fields
            .iter()
            .any(|field| field.label == "Priority" && !field.value.is_empty()));
        assert!(view
            .meta_fields
            .iter()
            .any(|field| field.label == "Labels" && field.value.contains("mock")));
        assert!(view.description.contains("Mock detail payload"));
    }

    #[test]
    fn detail_view_model_loading_state_has_source() {
        let mut app = App::new(mock_source(), false);
        app.source.mock_only = false;
        app.using_adapter = true;
        let key = app.selected_issue_key().expect("selected key");
        app.detail_loading_key = Some(key);

        let view = app.detail_view_model_for_selected();
        assert_eq!(view.mode, DetailViewMode::Loading);
        assert_eq!(view.source.as_deref(), Some("board=myissue"));
    }

    #[test]
    fn detail_view_model_error_state_has_compact_error() {
        let mut app = App::new(mock_source(), false);
        let key = app.selected_issue_key().expect("selected key");
        app.detail_errors.insert(
            key,
            String::from("top-level failure caused by nested adapter timeout details"),
        );

        let view = app.detail_view_model_for_selected();
        assert_eq!(view.mode, DetailViewMode::Error);
        assert!(view
            .error_message
            .as_deref()
            .expect("error message")
            .contains("top-level failure"));
    }

    #[test]
    fn detail_view_model_empty_selection_state() {
        let mut app = App::new(mock_source(), false);
        app.filter_input = String::from("no-such-issue");
        app.normalize_selection();

        let view = app.detail_view_model_for_selected();
        assert_eq!(view.mode, DetailViewMode::EmptySelection);
        assert_eq!(view.key, None);
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
        assert!(text.contains("J/K: scroll detail pane"));
        assert!(text.contains("Ctrl+d/Ctrl+u: page detail pane down/up"));
        assert!(text.contains("TAB: toggle horizontal/vertical layout"));
        assert!(text.contains("Alt+h/Alt+l: resize first/second pane"));
        assert!(text.contains("1: toggle issues pane zoom"));
        assert!(text.contains("2: toggle detail pane zoom"));
        assert!(text.contains("f: filter issues"));
        assert!(text.contains("/: search visible issues"));
        assert!(text.contains("n/N: next/previous search match"));
        assert!(text.contains("b: board switcher popup"));
        assert!(text.contains("c: comments popup"));
        assert!(text.contains("t: transitions popup"));
        assert!(text.contains("e: edit menu popup"));
        assert!(text.contains("Edit Menu Popup"));
        assert!(text.contains("u: custom field editor popup"));
        assert!(text.contains("?: actions/help popup"));
        assert!(text.contains("Ctrl+d/Ctrl+u: page down/up"));
    }

    #[test]
    fn actions_scroll_obeys_bounds() {
        let mut app = App::new(mock_source(), false);
        app.enter_actions_mode();
        app.set_actions_viewport_height(4);

        app.scroll_actions_down(500);
        let after_down = app.actions_scroll();
        assert!(after_down > 0);

        app.scroll_actions_up(2);
        assert_eq!(app.actions_scroll(), after_down - 2);

        app.scroll_actions_up(500);
        assert_eq!(app.actions_scroll(), 0);
    }

    #[test]
    fn detail_scroll_obeys_bounds() {
        let mut app = App::new(mock_source(), false);
        let (tx, _) = mpsc::channel();
        app.maybe_request_detail(&tx);
        app.set_detail_viewport_height(4);

        app.scroll_detail_down(500);
        let after_down = app.detail_scroll();
        assert!(after_down > 0);

        app.scroll_detail_up(2);
        assert_eq!(app.detail_scroll(), after_down - 2);

        app.scroll_detail_up(500);
        assert_eq!(app.detail_scroll(), 0);
    }

    #[test]
    fn detail_scroll_resets_when_selection_changes() {
        let mut app = App::new(mock_source(), false);
        let (tx, _) = mpsc::channel();
        app.maybe_request_detail(&tx);
        app.set_detail_viewport_height(4);
        app.scroll_detail_down(3);
        assert!(app.detail_scroll() > 0);

        app.next();
        app.maybe_request_detail(&tx);
        assert_eq!(app.detail_scroll(), 0);
    }

    #[test]
    fn non_detail_modes_are_popup_modes() {
        let mut app = App::new(mock_source(), false);
        assert!(!app.in_popup_mode());

        app.enter_boards_mode();
        assert!(app.in_popup_mode());

        app.enter_detail_mode();
        assert!(!app.in_popup_mode());
    }

    #[test]
    fn enter_boards_mode_loads_mock_boards() {
        let mut app = App::new(mock_source(), false);
        app.enter_boards_mode();

        assert!(app.in_boards_mode());
        let text = app.boards_text();
        assert!(text.contains("Configured Boards"));
        assert!(text.contains("myissue"));
    }

    #[test]
    fn apply_selected_board_updates_source() {
        let mut app = App::new(mock_source(), false);
        app.enter_boards_mode();
        app.next_board();
        app.apply_selected_board();

        assert_eq!(app.source.board.as_deref(), Some("team"));
        assert!(!app.in_boards_mode());
        assert!(app.status_line.contains("Switched to board 'team'"));
    }

    #[test]
    fn apply_selected_board_replaces_query_mode_with_board_mode() {
        let mut app = App::new(mock_query_source(), false);
        app.enter_boards_mode();
        app.next_board();
        app.apply_selected_board();

        assert_eq!(app.source.board.as_deref(), Some("team"));
        assert_eq!(app.source.query, None);
        assert!(app.status_line.contains("replaced active raw query mode"));
    }

    #[test]
    fn boards_text_warns_when_in_query_mode() {
        let mut app = App::new(mock_query_source(), false);
        app.enter_boards_mode();

        let text = app.boards_text();
        assert!(text.contains("Current: <raw query mode>"));
        assert!(text.contains("switching boards will replace the active raw query"));
    }

    #[test]
    fn submit_summary_edit_in_mock_mode_updates_issue() {
        let mut app = App::new(mock_source(), false);
        let (tx, _) = mpsc::channel();

        app.start_summary_edit_input();
        app.edit_input = "Updated summary".to_string();
        app.submit_edit_input(&tx);

        let issue = app.selected_issue().expect("selected issue");
        assert_eq!(issue.summary, "Updated summary");
    }

    #[test]
    fn submit_summary_edit_normalizes_newlines_to_spaces() {
        let mut app = App::new(mock_source(), false);
        let (tx, _) = mpsc::channel();

        app.start_summary_edit_input();
        app.submit_edit_value("line one\nline   two".to_string(), &tx);

        let issue = app.selected_issue().expect("selected issue");
        assert_eq!(issue.summary, "line one line two");
    }

    #[test]
    fn submit_description_edit_in_mock_mode_updates_detail_cache() {
        let mut app = App::new(mock_source(), false);
        let (detail_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        app.maybe_request_detail(&detail_tx);
        app.start_description_edit_input();
        app.edit_input = "Updated description".to_string();
        app.submit_edit_input(&edit_tx);

        let detail = app.detail_text_for_selected();
        assert!(detail.contains("Updated description"));
    }

    #[test]
    fn start_description_edit_input_normalizes_crlf_and_carriage_returns() {
        let mut app = App::new(mock_source(), false);
        let (detail_tx, _) = mpsc::channel();

        app.maybe_request_detail(&detail_tx);
        let key = app.selected_issue_key().expect("selected issue key");
        let detail = app
            .detail_cache
            .get_mut(&key)
            .expect("detail cache entry for selected issue");
        detail.description = "line one\r\nline two\rline three".to_string();

        app.start_description_edit_input();

        assert_eq!(app.edit_input, "line one\nline two\nline three");
    }

    #[test]
    fn submit_labels_edit_in_mock_mode_updates_detail_cache() {
        let mut app = App::new(mock_source(), false);
        let (detail_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        app.maybe_request_detail(&detail_tx);
        app.start_labels_edit_input();
        app.edit_input = "alpha, beta".to_string();
        app.submit_edit_input(&edit_tx);

        let detail = app.detail_text_for_selected();
        assert!(detail.contains("Labels: alpha, beta"));
    }

    #[test]
    fn submit_labels_edit_normalizes_newlines_to_csv_delimiters() {
        let mut app = App::new(mock_source(), false);
        let (detail_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        app.maybe_request_detail(&detail_tx);
        app.start_labels_edit_input();
        app.submit_edit_value("alpha\nbeta".to_string(), &edit_tx);

        let detail = app.detail_text_for_selected();
        assert!(detail.contains("Labels: alpha, beta"));
    }

    #[test]
    fn submit_components_edit_in_mock_mode_updates_detail_cache() {
        let mut app = App::new(mock_source(), false);
        let (detail_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        app.maybe_request_detail(&detail_tx);
        app.start_components_edit_input();
        app.edit_input = "core, ui".to_string();
        app.submit_edit_input(&edit_tx);

        let detail = app.detail_text_for_selected();
        assert!(detail.contains("Components: core, ui"));
    }

    #[test]
    fn submit_components_edit_normalizes_newlines_to_csv_delimiters() {
        let mut app = App::new(mock_source(), false);
        let (detail_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        app.maybe_request_detail(&detail_tx);
        app.start_components_edit_input();
        app.submit_edit_value("core\nui".to_string(), &edit_tx);

        let detail = app.detail_text_for_selected();
        assert!(detail.contains("Components: core, ui"));
    }

    #[test]
    fn enter_custom_fields_mode_loads_mock_custom_fields() {
        let mut app = App::new(mock_source(), false);
        app.enter_custom_fields_mode();

        assert!(app.in_custom_fields_mode());
        let text = app.custom_fields_text();
        assert!(text.contains("Configured Custom Fields"));
        assert!(text.contains("Story Points"));
    }

    #[test]
    fn enter_edit_menu_mode_shows_edit_popup() {
        let mut app = App::new(mock_source(), false);
        app.enter_edit_menu_mode();

        assert!(app.in_edit_menu_mode());
        assert!(app.in_popup_mode());
        assert_eq!(app.right_pane_title(), "Edit");
        assert!(app.edit_menu_text().contains("Edit Issue Fields"));
        assert!(app.edit_menu_text().contains("> Summary"));
    }

    #[test]
    fn edit_menu_selection_wraps() {
        let mut app = App::new(mock_source(), false);
        app.enter_edit_menu_mode();

        app.prev_edit_menu();
        assert!(app.edit_menu_text().contains("> Components"));

        app.next_edit_menu();
        assert!(app.edit_menu_text().contains("> Summary"));
    }

    #[test]
    fn apply_selected_edit_menu_starts_selected_edit_input() {
        let mut app = App::new(mock_source(), false);
        app.enter_edit_menu_mode();
        app.next_edit_menu();
        app.next_edit_menu();
        app.apply_selected_edit_menu();

        assert!(app.in_edit_input_mode());
        assert_eq!(app.edit_target_label(), "labels");
    }

    #[test]
    fn start_selected_custom_field_edit_input_sets_custom_target() {
        let mut app = App::new(mock_source(), false);
        app.enter_custom_fields_mode();
        app.start_selected_custom_field_edit_input();

        assert!(app.in_edit_input_mode());
        assert_eq!(app.edit_target_label(), "custom field");
        assert!(app.edit_target_display().contains("Story Points"));
    }

    #[test]
    fn submit_custom_field_edit_in_mock_mode_sets_status() {
        let mut app = App::new(mock_source(), false);
        let (edit_tx, _) = mpsc::channel();

        app.enter_custom_fields_mode();
        app.start_selected_custom_field_edit_input();
        app.edit_input = "8".to_string();
        app.submit_edit_input(&edit_tx);

        assert!(app
            .status_line
            .contains("Updated custom field in mock mode"));
    }

    #[test]
    fn default_pane_orientation_is_horizontal() {
        let app = App::new(mock_source(), false);
        assert_eq!(app.pane_orientation(), PaneOrientation::Horizontal);
        assert_eq!(app.pane_width_percentages(), (40, 60));
    }

    #[test]
    fn new_with_layout_applies_startup_orientation_and_zoom() {
        let app = App::new_with_layout(
            mock_source(),
            false,
            StartupLayoutConfig {
                orientation: PaneOrientation::Vertical,
                zoom: PaneZoom::Issues,
            },
        );
        assert_eq!(app.pane_orientation(), PaneOrientation::Vertical);
        assert_eq!(app.pane_zoom(), PaneZoom::Issues);
        assert_eq!(app.pane_width_percentages(), (30, 70));
    }

    #[test]
    fn pane_zoom_toggles_between_split_and_target_panes() {
        let mut app = App::new(mock_source(), false);
        assert_eq!(app.pane_zoom(), PaneZoom::None);

        app.toggle_zoom_issues();
        assert_eq!(app.pane_zoom(), PaneZoom::Issues);

        app.toggle_zoom_issues();
        assert_eq!(app.pane_zoom(), PaneZoom::None);

        app.toggle_zoom_detail();
        assert_eq!(app.pane_zoom(), PaneZoom::Detail);

        app.toggle_zoom_issues();
        assert_eq!(app.pane_zoom(), PaneZoom::Issues);

        app.toggle_zoom_detail();
        assert_eq!(app.pane_zoom(), PaneZoom::Detail);

        app.toggle_zoom_detail();
        assert_eq!(app.pane_zoom(), PaneZoom::None);
    }

    #[test]
    fn toggle_pane_orientation_flips_between_horizontal_and_vertical() {
        let mut app = App::new(mock_source(), false);
        assert_eq!(app.pane_orientation(), PaneOrientation::Horizontal);

        app.toggle_pane_orientation();
        assert_eq!(app.pane_orientation(), PaneOrientation::Vertical);
        assert_eq!(app.pane_width_percentages(), (30, 70));

        app.toggle_pane_orientation();
        assert_eq!(app.pane_orientation(), PaneOrientation::Horizontal);
        assert_eq!(app.pane_width_percentages(), (40, 60));
    }

    #[test]
    fn pane_resize_values_are_independent_per_orientation() {
        let mut app = App::new(mock_source(), false);

        app.grow_left_pane();
        assert_eq!(app.pane_width_percentages(), (45, 55));

        app.toggle_pane_orientation();
        assert_eq!(app.pane_width_percentages(), (30, 70));
        app.grow_left_pane();
        assert_eq!(app.pane_width_percentages(), (35, 65));

        app.toggle_pane_orientation();
        assert_eq!(app.pane_width_percentages(), (45, 55));
    }

    #[test]
    fn pane_resize_bounds_are_enforced() {
        let mut app = App::new(mock_source(), false);

        for _ in 0..10 {
            app.grow_left_pane();
        }
        let (left, right) = app.pane_width_percentages();
        assert_eq!(left, MAX_LEFT_PANE_PERCENT);
        assert_eq!(left + right, 100);

        for _ in 0..20 {
            app.grow_right_pane();
        }
        let (left, right) = app.pane_width_percentages();
        assert_eq!(left, MIN_LEFT_PANE_PERCENT);
        assert_eq!(left + right, 100);

        app.toggle_pane_orientation();
        for _ in 0..10 {
            app.grow_left_pane();
        }
        let (top, bottom) = app.pane_width_percentages();
        assert_eq!(top, MAX_LEFT_PANE_PERCENT);
        assert_eq!(top + bottom, 100);

        for _ in 0..20 {
            app.grow_right_pane();
        }
        let (top, bottom) = app.pane_width_percentages();
        assert_eq!(top, MIN_LEFT_PANE_PERCENT);
        assert_eq!(top + bottom, 100);
    }
}
