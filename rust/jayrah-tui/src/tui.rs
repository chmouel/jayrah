use std::{io, time::Duration};

use anyhow::Result;
use crossterm::event::{self, Event, KeyCode, KeyEvent, KeyEventKind, KeyModifiers};
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout, Rect},
    style::{Modifier, Style},
    widgets::{Block, Borders, Cell, Clear, Paragraph, Row, Table, TableState, Wrap},
    Frame, Terminal,
};
use tui_textarea::TextArea;

use crate::{
    app::App,
    worker::{
        start_add_comment_worker, start_apply_transition_worker, start_comment_worker,
        start_detail_worker, start_edit_issue_worker, start_transition_worker,
    },
};

#[derive(Debug, PartialEq, Eq)]
pub enum RunOutcome {
    Quit,
    Chosen(Option<String>),
}

const POPUP_HORIZONTAL_MARGIN: u16 = 2;
const POPUP_VERTICAL_MARGIN: u16 = 1;
const POPUP_MIN_WIDTH: u16 = 28;
const POPUP_MIN_HEIGHT: u16 = 6;
const POPUP_HORIZONTAL_PADDING: u16 = 4;
const POPUP_VERTICAL_PADDING: u16 = 2;
const DESCRIPTION_EDIT_POPUP_WIDTH_PERCENT: u16 = 80;
const DESCRIPTION_EDIT_POPUP_HEIGHT_PERCENT: u16 = 80;
const SUMMARY_EDIT_POPUP_HEIGHT_PERCENT: u16 = 35;
const SUMMARY_EDIT_POPUP_MIN_HEIGHT: u16 = 7;
const SUMMARY_EDIT_POPUP_MAX_HEIGHT: u16 = 10;
const EDIT_POPUP_WIDTH_PERCENT: u16 = 70;
const EDIT_POPUP_HEIGHT_PERCENT: u16 = 55;
const EDIT_POPUP_MIN_WIDTH: u16 = 44;
const EDIT_POPUP_MAX_WIDTH: u16 = 84;
const EDIT_POPUP_MIN_HEIGHT: u16 = 8;
const EDIT_POPUP_MAX_HEIGHT: u16 = 20;
const EDIT_POPUP_MARGIN: u16 = 1;

#[derive(Debug)]
struct EditInputSession {
    textarea: TextArea<'static>,
}

fn build_edit_textarea(value: &str) -> TextArea<'static> {
    TextArea::from(value.split('\n'))
}

fn sync_edit_input_session(app: &App, edit_session: &mut Option<EditInputSession>) {
    if app.in_edit_input_mode() {
        if edit_session.is_none() {
            *edit_session = Some(EditInputSession {
                textarea: build_edit_textarea(app.edit_input()),
            });
        }
    } else {
        *edit_session = None;
    }
}

pub fn run_app(
    terminal: &mut Terminal<CrosstermBackend<io::Stdout>>,
    mut app: App,
) -> Result<RunOutcome> {
    let (detail_request_tx, detail_result_rx) = start_detail_worker();
    let (comment_request_tx, comment_result_rx) = start_comment_worker();
    let (add_comment_request_tx, add_comment_result_rx) = start_add_comment_worker();
    let (transition_request_tx, transition_result_rx) = start_transition_worker();
    let (apply_transition_request_tx, apply_transition_result_rx) = start_apply_transition_worker();
    let (edit_issue_request_tx, edit_issue_result_rx) = start_edit_issue_worker();
    let mut edit_session: Option<EditInputSession> = None;

    loop {
        while let Ok(message) = detail_result_rx.try_recv() {
            app.ingest_detail_result(message);
        }
        while let Ok(message) = comment_result_rx.try_recv() {
            app.ingest_comment_result(message);
        }
        while let Ok(message) = add_comment_result_rx.try_recv() {
            app.ingest_add_comment_result(message);
        }
        while let Ok(message) = transition_result_rx.try_recv() {
            app.ingest_transition_result(message);
        }
        while let Ok(message) = apply_transition_result_rx.try_recv() {
            app.ingest_apply_transition_result(message);
        }
        while let Ok(message) = edit_issue_result_rx.try_recv() {
            app.ingest_edit_issue_result(message);
        }

        app.maybe_request_detail(&detail_request_tx);
        app.maybe_request_comments(&comment_request_tx);
        app.maybe_request_transitions(&transition_request_tx);
        sync_edit_input_session(&app, &mut edit_session);
        terminal.draw(|frame| draw_ui(frame, &mut app, edit_session.as_ref()))?;

        if event::poll(Duration::from_millis(100))? {
            let Event::Key(key) = event::read()? else {
                continue;
            };

            if key.kind != KeyEventKind::Press {
                continue;
            }

            if let Some(outcome) = handle_key_event_with_edit_session(
                &mut app,
                &mut edit_session,
                key,
                &add_comment_request_tx,
                &apply_transition_request_tx,
                &edit_issue_request_tx,
            ) {
                return Ok(outcome);
            }
        }
    }
}

fn handle_key_event(
    app: &mut App,
    key: KeyEvent,
    add_comment_request_tx: &std::sync::mpsc::Sender<crate::app::AddCommentRequest>,
    apply_transition_request_tx: &std::sync::mpsc::Sender<crate::app::ApplyTransitionRequest>,
    edit_issue_request_tx: &std::sync::mpsc::Sender<crate::app::EditIssueRequest>,
) -> Option<RunOutcome> {
    let mut edit_session = None;
    handle_key_event_with_edit_session(
        app,
        &mut edit_session,
        key,
        add_comment_request_tx,
        apply_transition_request_tx,
        edit_issue_request_tx,
    )
}

fn handle_key_event_with_edit_session(
    app: &mut App,
    edit_session: &mut Option<EditInputSession>,
    key: KeyEvent,
    add_comment_request_tx: &std::sync::mpsc::Sender<crate::app::AddCommentRequest>,
    apply_transition_request_tx: &std::sync::mpsc::Sender<crate::app::ApplyTransitionRequest>,
    edit_issue_request_tx: &std::sync::mpsc::Sender<crate::app::EditIssueRequest>,
) -> Option<RunOutcome> {
    if key.modifiers.contains(KeyModifiers::ALT) {
        match key.code {
            KeyCode::Char('h') => {
                app.grow_right_pane();
                return None;
            }
            KeyCode::Char('l') => {
                app.grow_left_pane();
                return None;
            }
            _ => {}
        }
    }

    if app.filter_mode {
        match key.code {
            KeyCode::Esc | KeyCode::Enter => {
                app.filter_mode = false;
                app.normalize_selection();
                app.status_line = format!("Filter applied: '{}'", app.filter_input);
            }
            KeyCode::Backspace => {
                let selected_key = app.selected_issue_key();
                app.filter_input.pop();
                app.normalize_selection_with_preferred_key(selected_key.as_deref());
            }
            KeyCode::Char(c) => {
                if !key.modifiers.contains(KeyModifiers::CONTROL) {
                    let selected_key = app.selected_issue_key();
                    app.filter_input.push(c);
                    app.normalize_selection_with_preferred_key(selected_key.as_deref());
                }
            }
            _ => {}
        }
        return None;
    }

    if app.in_comment_input_mode() {
        match key.code {
            KeyCode::Esc => app.cancel_comment_input(),
            KeyCode::Enter => app.submit_comment_input(add_comment_request_tx),
            KeyCode::Backspace => app.pop_comment_input_char(),
            KeyCode::Char(c) => {
                if !key.modifiers.contains(KeyModifiers::CONTROL) {
                    app.push_comment_input_char(c);
                }
            }
            _ => {}
        }
        return None;
    }

    if app.in_edit_input_mode() {
        sync_edit_input_session(app, edit_session);
        let Some(session) = edit_session.as_mut() else {
            app.status_line = "Edit input unavailable".to_string();
            return None;
        };

        match key {
            KeyEvent {
                code: KeyCode::Esc, ..
            } => {
                app.cancel_edit_input();
                *edit_session = None;
            }
            KeyEvent {
                code: KeyCode::Char(c),
                modifiers,
                ..
            } if modifiers.contains(KeyModifiers::CONTROL) && c.eq_ignore_ascii_case(&'s') => {
                let value = session.textarea.lines().join("\n");
                app.set_edit_input(value.clone());
                app.submit_edit_value(value, edit_issue_request_tx);
                sync_edit_input_session(app, edit_session);
            }
            _ => {
                session.textarea.input(key);
                app.set_edit_input(session.textarea.lines().join("\n"));
            }
        }
        return None;
    }

    if app.in_comments_mode() {
        match key.code {
            KeyCode::Char('q') | KeyCode::Esc | KeyCode::Char('c') => app.enter_detail_mode(),
            KeyCode::Char('j') | KeyCode::Down | KeyCode::Char('n') => app.next_comment(),
            KeyCode::Char('k') | KeyCode::Up | KeyCode::Char('p') => app.prev_comment(),
            KeyCode::Char('a') => app.start_comment_input(),
            KeyCode::Char('e') => app.start_summary_edit_input(),
            KeyCode::Char('E') => app.start_description_edit_input(),
            KeyCode::Char('l') => app.start_labels_edit_input(),
            KeyCode::Char('m') => app.start_components_edit_input(),
            KeyCode::Char('u') => app.enter_custom_fields_mode(),
            KeyCode::Char('?') => app.enter_actions_mode(),
            KeyCode::Char('r') => app.reload_issues(),
            KeyCode::Char('f') | KeyCode::Char('/') => {
                app.filter_mode = true;
                app.status_line = String::from("Filter mode: type to filter, Enter to apply");
            }
            KeyCode::Char('o') => app.open_selected_issue(),
            KeyCode::Enter => {
                if app.choose_mode {
                    return Some(RunOutcome::Chosen(app.selected_issue_key()));
                }
                app.open_selected_issue();
            }
            _ => {}
        }
        return None;
    }

    if app.in_actions_mode() {
        match key.code {
            KeyCode::Char('q') | KeyCode::Esc | KeyCode::Char('?') => app.enter_detail_mode(),
            KeyCode::Char('j') | KeyCode::Down => app.scroll_actions_down(1),
            KeyCode::Char('k') | KeyCode::Up => app.scroll_actions_up(1),
            KeyCode::Char('d') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                app.scroll_actions_down(app.actions_half_page_step())
            }
            KeyCode::Char('u') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                app.scroll_actions_up(app.actions_half_page_step())
            }
            KeyCode::Char('e') => app.start_summary_edit_input(),
            KeyCode::Char('E') => app.start_description_edit_input(),
            KeyCode::Char('l') => app.start_labels_edit_input(),
            KeyCode::Char('m') => app.start_components_edit_input(),
            KeyCode::Char('u') => app.enter_custom_fields_mode(),
            KeyCode::Char('b') => app.enter_boards_mode(),
            KeyCode::Char('c') => app.enter_comments_mode(),
            KeyCode::Char('t') => app.enter_transitions_mode(),
            KeyCode::Char('r') => app.reload_issues(),
            KeyCode::Char('o') => app.open_selected_issue(),
            KeyCode::Char('f') | KeyCode::Char('/') => {
                app.filter_mode = true;
                app.status_line = String::from("Filter mode: type to filter, Enter to apply");
            }
            _ => {}
        }
        return None;
    }

    if app.in_boards_mode() {
        match key.code {
            KeyCode::Char('q') | KeyCode::Esc | KeyCode::Char('b') => app.enter_detail_mode(),
            KeyCode::Char('j') | KeyCode::Down | KeyCode::Char('n') => app.next_board(),
            KeyCode::Char('k') | KeyCode::Up | KeyCode::Char('p') => app.prev_board(),
            KeyCode::Char('e') => app.start_summary_edit_input(),
            KeyCode::Char('E') => app.start_description_edit_input(),
            KeyCode::Char('l') => app.start_labels_edit_input(),
            KeyCode::Char('m') => app.start_components_edit_input(),
            KeyCode::Char('u') => app.enter_custom_fields_mode(),
            KeyCode::Char('c') => app.enter_comments_mode(),
            KeyCode::Char('t') => app.enter_transitions_mode(),
            KeyCode::Char('?') => app.enter_actions_mode(),
            KeyCode::Char('r') => app.reload_issues(),
            KeyCode::Char('o') => app.open_selected_issue(),
            KeyCode::Char('f') | KeyCode::Char('/') => {
                app.filter_mode = true;
                app.status_line = String::from("Filter mode: type to filter, Enter to apply");
            }
            KeyCode::Enter => app.apply_selected_board(),
            _ => {}
        }
        return None;
    }

    if app.in_custom_fields_mode() {
        match key.code {
            KeyCode::Char('q') | KeyCode::Esc | KeyCode::Char('u') => app.enter_detail_mode(),
            KeyCode::Char('j') | KeyCode::Down | KeyCode::Char('n') => app.next_custom_field(),
            KeyCode::Char('k') | KeyCode::Up | KeyCode::Char('p') => app.prev_custom_field(),
            KeyCode::Char('b') => app.enter_boards_mode(),
            KeyCode::Char('c') => app.enter_comments_mode(),
            KeyCode::Char('t') => app.enter_transitions_mode(),
            KeyCode::Char('?') => app.enter_actions_mode(),
            KeyCode::Char('r') => app.reload_issues(),
            KeyCode::Char('o') => app.open_selected_issue(),
            KeyCode::Char('f') | KeyCode::Char('/') => {
                app.filter_mode = true;
                app.status_line = String::from("Filter mode: type to filter, Enter to apply");
            }
            KeyCode::Enter => app.start_selected_custom_field_edit_input(),
            _ => {}
        }
        return None;
    }

    if app.in_transitions_mode() {
        match key.code {
            KeyCode::Char('q') | KeyCode::Esc | KeyCode::Char('t') => app.enter_detail_mode(),
            KeyCode::Char('j') | KeyCode::Down | KeyCode::Char('n') => app.next_transition(),
            KeyCode::Char('k') | KeyCode::Up | KeyCode::Char('p') => app.prev_transition(),
            KeyCode::Char('e') => app.start_summary_edit_input(),
            KeyCode::Char('E') => app.start_description_edit_input(),
            KeyCode::Char('l') => app.start_labels_edit_input(),
            KeyCode::Char('m') => app.start_components_edit_input(),
            KeyCode::Char('u') => app.enter_custom_fields_mode(),
            KeyCode::Char('c') => app.enter_comments_mode(),
            KeyCode::Char('?') => app.enter_actions_mode(),
            KeyCode::Char('r') => app.reload_issues(),
            KeyCode::Char('f') | KeyCode::Char('/') => {
                app.filter_mode = true;
                app.status_line = String::from("Filter mode: type to filter, Enter to apply");
            }
            KeyCode::Char('o') => app.open_selected_issue(),
            KeyCode::Enter => app.apply_selected_transition(apply_transition_request_tx),
            _ => {}
        }
        return None;
    }

    match key.code {
        KeyCode::Char('q') | KeyCode::Esc => return Some(RunOutcome::Quit),
        KeyCode::Char('j') | KeyCode::Down => app.next(),
        KeyCode::Char('k') | KeyCode::Up => app.prev(),
        KeyCode::Char('J') => app.scroll_detail_down(1),
        KeyCode::Char('K') => app.scroll_detail_up(1),
        KeyCode::Char('d') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            app.scroll_detail_down(app.detail_half_page_step())
        }
        KeyCode::Char('u') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            app.scroll_detail_up(app.detail_half_page_step())
        }
        KeyCode::Char('e') => app.start_summary_edit_input(),
        KeyCode::Char('E') => app.start_description_edit_input(),
        KeyCode::Char('l') => app.start_labels_edit_input(),
        KeyCode::Char('m') => app.start_components_edit_input(),
        KeyCode::Char('u') => app.enter_custom_fields_mode(),
        KeyCode::Char('b') => app.enter_boards_mode(),
        KeyCode::Char('c') => app.enter_comments_mode(),
        KeyCode::Char('t') => app.enter_transitions_mode(),
        KeyCode::Char('?') => app.enter_actions_mode(),
        KeyCode::Char('r') => app.reload_issues(),
        KeyCode::Char('f') | KeyCode::Char('/') => {
            app.filter_mode = true;
            app.status_line = String::from("Filter mode: type to filter, Enter to apply");
        }
        KeyCode::Char('o') => app.open_selected_issue(),
        KeyCode::Enter => {
            if app.choose_mode {
                return Some(RunOutcome::Chosen(app.selected_issue_key()));
            }
            app.open_selected_issue();
        }
        _ => {}
    }

    None
}

fn popup_text_dimensions(text: &str) -> (u16, u16) {
    let mut width = 0u16;
    let mut height = 0u16;

    for line in text.split('\n') {
        height = height.saturating_add(1);
        let line_width = u16::try_from(line.chars().count()).unwrap_or(u16::MAX);
        width = width.max(line_width);
    }

    if height == 0 {
        height = 1;
    }
    if width == 0 {
        width = 1;
    }

    (width, height)
}

fn centered_rect(area: Rect, width: u16, height: u16) -> Rect {
    let popup_width = width.max(1).min(area.width.max(1));
    let popup_height = height.max(1).min(area.height.max(1));
    let x = area.x + area.width.saturating_sub(popup_width) / 2;
    let y = area.y + area.height.saturating_sub(popup_height) / 2;
    Rect::new(x, y, popup_width, popup_height)
}

fn percent_popup_area(area: Rect, width_percent: u16, height_percent: u16) -> Rect {
    let width = area
        .width
        .saturating_mul(width_percent.clamp(1, 100))
        .saturating_div(100)
        .max(1);
    let height = area
        .height
        .saturating_mul(height_percent.clamp(1, 100))
        .saturating_div(100)
        .max(1);
    centered_rect(area, width, height)
}

fn adaptive_popup_area(area: Rect, title: &str, text: &str) -> Rect {
    let available_width = area
        .width
        .saturating_sub(POPUP_HORIZONTAL_MARGIN.saturating_mul(2))
        .max(1);
    let available_height = area
        .height
        .saturating_sub(POPUP_VERTICAL_MARGIN.saturating_mul(2))
        .max(1);
    let (content_width, content_height) = popup_text_dimensions(text);
    let title_width = u16::try_from(title.chars().count())
        .unwrap_or(u16::MAX)
        .saturating_add(4);
    let desired_width = content_width
        .saturating_add(POPUP_HORIZONTAL_PADDING)
        .max(title_width);
    let desired_height = content_height.saturating_add(POPUP_VERTICAL_PADDING);
    let popup_width = desired_width.clamp(POPUP_MIN_WIDTH.min(available_width), available_width);
    let popup_height =
        desired_height.clamp(POPUP_MIN_HEIGHT.min(available_height), available_height);

    centered_rect(area, popup_width, popup_height)
}

fn edit_popup_area(area: Rect, is_description_target: bool, is_summary_target: bool) -> Rect {
    if is_description_target {
        return percent_popup_area(
            area,
            DESCRIPTION_EDIT_POPUP_WIDTH_PERCENT,
            DESCRIPTION_EDIT_POPUP_HEIGHT_PERCENT,
        );
    }

    let available_width = area
        .width
        .saturating_sub(EDIT_POPUP_MARGIN.saturating_mul(2))
        .max(1);
    let available_height = area
        .height
        .saturating_sub(EDIT_POPUP_MARGIN.saturating_mul(2))
        .max(1);
    let width = available_width
        .saturating_mul(EDIT_POPUP_WIDTH_PERCENT.clamp(1, 100))
        .saturating_div(100)
        .clamp(
            EDIT_POPUP_MIN_WIDTH.min(available_width),
            EDIT_POPUP_MAX_WIDTH.min(available_width),
        );
    let height = if is_summary_target {
        available_height
            .saturating_mul(SUMMARY_EDIT_POPUP_HEIGHT_PERCENT.clamp(1, 100))
            .saturating_div(100)
            .clamp(
                SUMMARY_EDIT_POPUP_MIN_HEIGHT.min(available_height),
                SUMMARY_EDIT_POPUP_MAX_HEIGHT.min(available_height),
            )
    } else {
        available_height
            .saturating_mul(EDIT_POPUP_HEIGHT_PERCENT.clamp(1, 100))
            .saturating_div(100)
            .clamp(
                EDIT_POPUP_MIN_HEIGHT.min(available_height),
                EDIT_POPUP_MAX_HEIGHT.min(available_height),
            )
    };
    centered_rect(area, width, height)
}

fn edit_input_height(inner_height: u16, is_summary_target: bool) -> u16 {
    if inner_height <= 1 {
        return inner_height;
    }

    if is_summary_target {
        4u16.min(inner_height.saturating_sub(1)).max(1)
    } else {
        inner_height.saturating_sub(1)
    }
}

fn draw_ui(frame: &mut Frame, app: &mut App, edit_session: Option<&EditInputSession>) {
    let vertical = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Min(0), Constraint::Length(1)])
        .split(frame.area());

    let (left_pane_percent, right_pane_percent) = app.pane_width_percentages();
    let main_chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(left_pane_percent),
            Constraint::Percentage(right_pane_percent),
        ])
        .split(vertical[0]);

    let visible = app.visible_indices();

    let rows: Vec<Row> = visible
        .iter()
        .filter_map(|index| app.issues.get(*index))
        .map(|issue| {
            Row::new(vec![
                Cell::from(issue.key.clone()),
                Cell::from(issue.summary.clone()),
                Cell::from(issue.status.clone()),
                Cell::from(issue.assignee.clone()),
            ])
        })
        .collect();

    let issues_title = if app.using_adapter {
        "Issues (adapter)"
    } else {
        "Issues (mock)"
    };

    let table = Table::new(
        rows,
        [
            Constraint::Length(12),
            Constraint::Percentage(52),
            Constraint::Length(14),
            Constraint::Length(14),
        ],
    )
    .header(Row::new(vec!["Key", "Summary", "Status", "Assignee"]))
    .block(Block::default().title(issues_title).borders(Borders::ALL))
    .row_highlight_style(Style::default().add_modifier(Modifier::REVERSED))
    .highlight_symbol(">> ");

    let mut state = TableState::default();
    if !visible.is_empty() {
        state.select(Some(app.selected));
    }

    frame.render_stateful_widget(table, main_chunks[0], &mut state);

    let detail_viewport_height = main_chunks[1].height.saturating_sub(2);
    app.set_detail_viewport_height(detail_viewport_height);
    let detail = Paragraph::new(app.detail_text_for_selected())
        .block(Block::default().title("Detail").borders(Borders::ALL))
        .scroll((app.detail_scroll(), 0))
        .wrap(Wrap { trim: false });
    frame.render_widget(detail, main_chunks[1]);

    if app.in_popup_mode() {
        let popup_title = app.right_pane_title();
        let popup_text = app.right_pane_text();
        let popup_area = adaptive_popup_area(vertical[0], popup_title, popup_text.as_str());

        if app.in_actions_mode() {
            let popup_viewport_height = popup_area.height.saturating_sub(2);
            app.set_actions_viewport_height(popup_viewport_height);
        }

        let mut popup = Paragraph::new(popup_text)
            .block(Block::default().title(popup_title).borders(Borders::ALL))
            .wrap(Wrap { trim: false });
        if app.in_actions_mode() {
            popup = popup.scroll((app.actions_scroll(), 0));
        }
        frame.render_widget(Clear, popup_area);
        frame.render_widget(popup, popup_area);
    }

    if app.in_edit_input_mode() {
        let is_description_target = app.edit_target_label() == "description";
        let is_summary_target = app.edit_target_label() == "summary";
        let edit_popup_area =
            edit_popup_area(vertical[0], is_description_target, is_summary_target);
        frame.render_widget(Clear, edit_popup_area);
        let issue_key = app
            .selected_issue_key()
            .unwrap_or_else(|| String::from("<no issue>"));
        let edit_title = format!("Edit {} ({issue_key})", app.edit_target_display());
        let popup_block = Block::default().title(edit_title).borders(Borders::ALL);
        frame.render_widget(popup_block.clone(), edit_popup_area);

        let inner = popup_block.inner(edit_popup_area);
        if inner.width > 0 && inner.height > 0 {
            if inner.height > 1 {
                let input_height = edit_input_height(inner.height, is_summary_target);
                let sections = Layout::default()
                    .direction(Direction::Vertical)
                    .constraints([Constraint::Length(input_height), Constraint::Length(1)])
                    .split(inner);
                if let Some(session) = edit_session {
                    frame.render_widget(&session.textarea, sections[0]);
                } else {
                    frame.render_widget(
                        Paragraph::new(app.edit_input()).wrap(Wrap { trim: false }),
                        sections[0],
                    );
                }
                let controls = Paragraph::new("Ctrl+s save  Esc cancel")
                    .style(Style::default().add_modifier(Modifier::DIM))
                    .wrap(Wrap { trim: true });
                frame.render_widget(controls, sections[1]);
            } else if let Some(session) = edit_session {
                frame.render_widget(&session.textarea, inner);
            } else {
                frame.render_widget(
                    Paragraph::new(app.edit_input()).wrap(Wrap { trim: false }),
                    inner,
                );
            }
        }
    }

    let mode = if app.filter_mode {
        "FILTER"
    } else if app.in_comment_input_mode() {
        "COMMENT-INPUT"
    } else if app.in_edit_input_mode() {
        "EDIT-INPUT"
    } else if app.in_actions_mode() {
        "ACTIONS"
    } else if app.in_custom_fields_mode() {
        "CUSTOM-FIELDS"
    } else if app.in_boards_mode() {
        "BOARDS"
    } else if app.in_transitions_mode() {
        "TRANSITIONS"
    } else if app.in_comments_mode() {
        "COMMENTS"
    } else if app.choose_mode {
        "CHOOSE"
    } else {
        "NORMAL"
    };
    let footer = if app.filter_mode {
        format!(
            "[{}] filter: {}  | Enter/Esc apply  Backspace delete",
            mode, app.filter_input
        )
    } else if app.in_comment_input_mode() {
        format!(
            "[{}] draft: {} | Enter submit | Esc cancel | {}",
            mode,
            app.comment_input(),
            app.status_line
        )
    } else if app.in_edit_input_mode() {
        format!(
            "[{}] editor open | target: {} | Ctrl+s save | Esc cancel | {}",
            mode,
            app.edit_target_display(),
            app.status_line
        )
    } else if app.in_actions_mode() {
        format!(
            "[{}] ? close | j/k scroll | Ctrl+d/u page | e/E/l/m edit | u custom popup | b boards popup | c comments popup | t transitions popup | f filter | r reload | {}",
            mode, app.status_line
        )
    } else if app.in_custom_fields_mode() {
        format!(
            "[{}] j/k/n/p pick field | Enter edit | u close | r reload | o open | {}",
            mode, app.status_line
        )
    } else if app.in_boards_mode() {
        format!(
            "[{}] j/k/n/p pick board | Enter switch | u custom | b close | r reload | o open | {}",
            mode, app.status_line
        )
    } else if app.in_transitions_mode() {
        format!(
            "[{}] j/k/n/p pick transition | Enter apply | e/E/l/m edit | u custom | t close | r reload | o open | {}",
            mode, app.status_line
        )
    } else if app.in_comments_mode() {
        format!(
            "[{}] j/k/n/p move comments | a add | e/E/l/m edit | u custom | c close | r reload | o open | {}",
            mode, app.status_line
        )
    } else if app.choose_mode {
        format!(
            "[{}] j/k move | J/K scroll detail | Ctrl+d/u page detail | Enter choose | e/E/l/m edit | u custom popup | b boards popup | c comments popup | t transitions popup | ? help popup | Alt+h/l resize panes | f filter | o open | q quit | {}",
            mode, app.status_line
        )
    } else {
        format!(
            "[{}] j/k move | J/K scroll detail | Ctrl+d/u page detail | e/E/l/m edit | u custom popup | b boards popup | c comments popup | t transitions popup | ? help popup | Alt+h/l resize panes | f filter | r reload | o open | q quit | {}",
            mode, app.status_line
        )
    };
    frame.render_widget(Paragraph::new(footer), vertical[1]);
}

#[cfg(test)]
mod tests {
    use std::sync::mpsc;

    use crossterm::event::KeyEventState;
    use crossterm::event::{KeyCode, KeyEvent, KeyEventKind, KeyModifiers};
    use ratatui::layout::Rect;

    use super::{
        adaptive_popup_area, build_edit_textarea, edit_input_height, edit_popup_area,
        handle_key_event, handle_key_event_with_edit_session, percent_popup_area, EditInputSession,
        RunOutcome,
    };
    use crate::{app::App, types::AdapterSource};

    fn mock_source() -> AdapterSource {
        AdapterSource {
            board: None,
            query: None,
            mock_only: true,
        }
    }

    fn key(code: KeyCode) -> KeyEvent {
        KeyEvent {
            code,
            modifiers: KeyModifiers::empty(),
            kind: KeyEventKind::Press,
            state: KeyEventState::empty(),
        }
    }

    fn key_with_modifiers(code: KeyCode, modifiers: KeyModifiers) -> KeyEvent {
        KeyEvent {
            code,
            modifiers,
            kind: KeyEventKind::Press,
            state: KeyEventState::empty(),
        }
    }

    #[test]
    fn enter_returns_selected_key_in_choose_mode() {
        let mut app = App::new(mock_source(), true);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Enter),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(
            outcome,
            Some(RunOutcome::Chosen(Some("JAY-101".to_string())))
        );
    }

    #[test]
    fn enter_opens_issue_outside_choose_mode() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Enter),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert!(app
            .status_line
            .contains("Open disabled while using mock data"));
    }

    #[test]
    fn q_closes_comments_mode_before_quit() {
        let mut app = App::new(mock_source(), false);
        app.enter_comments_mode();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('q')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );

        assert_eq!(outcome, None);
        assert!(!app.in_comments_mode());
    }

    #[test]
    fn a_enters_comment_input_mode() {
        let mut app = App::new(mock_source(), false);
        app.enter_comments_mode();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('a')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );

        assert_eq!(outcome, None);
        assert!(app.in_comment_input_mode());
    }

    #[test]
    fn t_enters_transitions_mode() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('t')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );

        assert_eq!(outcome, None);
        assert!(app.in_transitions_mode());
    }

    #[test]
    fn question_mark_enters_actions_mode() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('?')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );

        assert_eq!(outcome, None);
        assert!(app.in_actions_mode());
    }

    #[test]
    fn b_enters_boards_mode() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('b')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );

        assert_eq!(outcome, None);
        assert!(app.in_boards_mode());
    }

    #[test]
    fn e_enters_edit_input_mode() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('e')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );

        assert_eq!(outcome, None);
        assert!(app.in_edit_input_mode());
        assert_eq!(app.edit_target_label(), "summary");
    }

    #[test]
    fn l_enters_labels_edit_input_mode() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('l')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );

        assert_eq!(outcome, None);
        assert!(app.in_edit_input_mode());
        assert_eq!(app.edit_target_label(), "labels");
    }

    #[test]
    fn u_enters_custom_fields_mode() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('u')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );

        assert_eq!(outcome, None);
        assert!(app.in_custom_fields_mode());
    }

    #[test]
    fn alt_h_and_alt_l_resize_panes() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let initial = app.pane_width_percentages();
        let outcome = handle_key_event(
            &mut app,
            key_with_modifiers(KeyCode::Char('h'), KeyModifiers::ALT),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        let after_h = app.pane_width_percentages();
        assert!(after_h.0 < initial.0);

        let outcome = handle_key_event(
            &mut app,
            key_with_modifiers(KeyCode::Char('l'), KeyModifiers::ALT),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        let after_l = app.pane_width_percentages();
        assert_eq!(after_l.0, initial.0);
    }

    #[test]
    fn uppercase_j_and_k_scroll_detail_without_moving_issue_selection() {
        let mut app = App::new(mock_source(), false);
        let (detail_tx, _) = mpsc::channel();
        app.maybe_request_detail(&detail_tx);
        app.set_detail_viewport_height(4);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let initial_selected = app.selected;
        let initial_scroll = app.detail_scroll();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('J')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.selected, initial_selected);
        assert!(app.detail_scroll() > initial_scroll);

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('K')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.detail_scroll(), initial_scroll);
    }

    #[test]
    fn ctrl_d_and_ctrl_u_page_detail_in_normal_mode() {
        let mut app = App::new(mock_source(), false);
        let (detail_tx, _) = mpsc::channel();
        app.maybe_request_detail(&detail_tx);
        app.set_detail_viewport_height(6);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key_with_modifiers(KeyCode::Char('d'), KeyModifiers::CONTROL),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        let after_down = app.detail_scroll();
        assert!(after_down > 0);

        let outcome = handle_key_event(
            &mut app,
            key_with_modifiers(KeyCode::Char('u'), KeyModifiers::CONTROL),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert!(app.detail_scroll() < after_down);
    }

    #[test]
    fn j_and_k_scroll_actions_help_without_moving_issue_selection() {
        let mut app = App::new(mock_source(), false);
        app.enter_actions_mode();
        app.set_actions_viewport_height(5);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let initial_selected = app.selected;
        let initial_scroll = app.actions_scroll();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('j')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.selected, initial_selected);
        assert!(app.actions_scroll() > initial_scroll);

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('k')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.actions_scroll(), initial_scroll);
    }

    #[test]
    fn ctrl_d_and_ctrl_u_page_actions_help() {
        let mut app = App::new(mock_source(), false);
        app.enter_actions_mode();
        app.set_actions_viewport_height(10);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key_with_modifiers(KeyCode::Char('d'), KeyModifiers::CONTROL),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        let after_down = app.actions_scroll();
        assert!(after_down > 0);

        let outcome = handle_key_event(
            &mut app,
            key_with_modifiers(KeyCode::Char('u'), KeyModifiers::CONTROL),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert!(app.actions_scroll() < after_down);
    }

    #[test]
    fn j_advances_board_selection_in_boards_mode() {
        let mut app = App::new(mock_source(), false);
        app.enter_boards_mode();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('j')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        let text = app.boards_text();
        assert!(text.contains("> team - Team board for active sprint work"));
    }

    #[test]
    fn j_advances_transition_selection_in_transitions_mode() {
        let mut app = App::new(mock_source(), false);
        let (list_tx, _) = mpsc::channel();
        app.enter_transitions_mode();
        app.maybe_request_transitions(&list_tx);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('j')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert!(app
            .transitions_text_for_selected()
            .contains("Transition 2/2"));
    }

    #[test]
    fn j_advances_comment_selection_in_comments_mode() {
        let mut app = App::new(mock_source(), false);
        let (list_tx, _) = mpsc::channel();
        app.enter_comments_mode();
        app.maybe_request_comments(&list_tx);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('j')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert!(app.comments_text_for_selected().contains("Comment 2/2"));
    }

    #[test]
    fn j_advances_custom_field_selection_in_custom_fields_mode() {
        let mut app = App::new(mock_source(), false);
        app.enter_custom_fields_mode();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('j')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        let text = app.custom_fields_text();
        assert!(text.contains("> Spec URL (customfield_10100, url)"));
    }

    #[test]
    fn adaptive_popup_area_is_bounded_by_terminal_area() {
        let area = Rect::new(0, 0, 100, 40);
        let content = "x".repeat(500);
        let popup = adaptive_popup_area(area, "Actions", content.as_str());

        assert!(popup.width <= 96);
        assert!(popup.height <= 38);
        assert!(popup.width > 0);
        assert!(popup.height > 0);
    }

    #[test]
    fn adaptive_popup_area_grows_with_content_size() {
        let area = Rect::new(0, 0, 120, 50);
        let small = adaptive_popup_area(area, "Boards", "line");
        let large = adaptive_popup_area(
            area,
            "Boards",
            "line one\nline two\nline three with more text than the short content",
        );

        assert!(large.width >= small.width);
        assert!(large.height >= small.height);
    }

    #[test]
    fn percent_popup_area_uses_requested_percentage() {
        let area = Rect::new(0, 0, 100, 40);
        let popup = percent_popup_area(area, 80, 80);

        assert_eq!(popup.width, 80);
        assert_eq!(popup.height, 32);
        assert_eq!(popup.x, 10);
        assert_eq!(popup.y, 4);
    }

    #[test]
    fn edit_popup_area_stays_within_expected_bounds() {
        let area = Rect::new(0, 0, 140, 60);
        let popup = edit_popup_area(area, false, false);

        assert!(popup.width >= 44);
        assert!(popup.width <= 84);
        assert!(popup.height >= 8);
        assert!(popup.height <= 20);
    }

    #[test]
    fn description_edit_popup_uses_eighty_percent_of_screen() {
        let area = Rect::new(0, 0, 100, 40);
        let popup = edit_popup_area(area, true, false);

        assert_eq!(popup.width, 80);
        assert_eq!(popup.height, 32);
        assert_eq!(popup.x, 10);
        assert_eq!(popup.y, 4);
    }

    #[test]
    fn summary_edit_popup_uses_compact_height_profile() {
        let area = Rect::new(0, 0, 140, 60);
        let popup = edit_popup_area(area, false, true);

        assert!(popup.height >= 7);
        assert!(popup.height <= 10);
    }

    #[test]
    fn summary_edit_input_height_uses_four_lines_when_possible() {
        assert_eq!(edit_input_height(6, true), 4);
        assert_eq!(edit_input_height(2, true), 1);
        assert_eq!(edit_input_height(6, false), 5);
    }

    #[test]
    fn ctrl_s_submits_edit_input_in_mock_mode() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();
        app.start_summary_edit_input();

        let mut edit_session = Some(EditInputSession {
            textarea: build_edit_textarea("Saved with Ctrl+S"),
        });
        let outcome = handle_key_event_with_edit_session(
            &mut app,
            &mut edit_session,
            key_with_modifiers(KeyCode::Char('s'), KeyModifiers::CONTROL),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );

        assert_eq!(outcome, None);
        assert!(!app.in_edit_input_mode());
        let issue = app.selected_issue().expect("selected issue");
        assert_eq!(issue.summary, "Saved with Ctrl+S");
    }

    #[test]
    fn enter_in_edit_mode_inserts_newline_and_does_not_submit() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();
        app.start_description_edit_input();

        let mut edit_session = None;
        let outcome = handle_key_event_with_edit_session(
            &mut app,
            &mut edit_session,
            key(KeyCode::Enter),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );

        assert_eq!(outcome, None);
        assert!(app.in_edit_input_mode());
        assert!(app.edit_input().contains('\n'));
    }
}
