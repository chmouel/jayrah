use std::{io, time::Duration};

use anyhow::Result;
use crossterm::event::{
    self, Event, KeyCode, KeyEvent, KeyEventKind, KeyModifiers, MouseButton, MouseEvent,
    MouseEventKind,
};
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout, Rect},
    text::{Line, Span, Text},
    widgets::{
        Block, Borders, Cell, Clear, Paragraph, Row, Scrollbar, ScrollbarOrientation,
        ScrollbarState, Table, TableState, Wrap,
    },
    Frame, Terminal,
};
use tui_textarea::TextArea;

use crate::{
    app::{App, DetailViewMode, DetailViewModel, PaneOrientation, PaneZoom},
    theme::{status_tone, Theme},
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

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
struct MouseHitAreas {
    issues: Option<Rect>,
    detail: Option<Rect>,
    popup: Option<Rect>,
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
    let theme = Theme::solarized_warm();
    let normalized = value.replace("\r\n", "\n").replace('\r', "\n");
    let mut textarea = TextArea::from(normalized.split('\n'));
    textarea.set_style(theme.popup());
    textarea.set_cursor_style(theme.table_selected());
    textarea.set_cursor_line_style(theme.filter_bar(true));
    textarea.set_selection_style(theme.filter_bar(true));
    textarea
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

fn focus_filter_input(app: &mut App) {
    app.search_mode = false;
    app.filter_mode = true;
    if app.has_active_filter() {
        app.status_line = format!(
            "Filter focused: '{}'. Esc/Enter exit, Ctrl-U clear",
            app.filter_query()
        );
    } else {
        app.status_line =
            String::from("Filter focused: type to filter, Esc/Enter exit, Ctrl-U clear");
    }
}

fn focus_search_input(app: &mut App) {
    app.filter_mode = false;
    app.search_mode = true;
    app.search_input = app.last_search_query().to_string();
    if app.has_active_search_query() {
        app.status_line = format!(
            "Search focused: '{}'. Enter search, Esc cancel, Ctrl-U clear",
            app.last_search_query()
        );
    } else {
        app.status_line =
            String::from("Search focused: type query, Enter search, Esc cancel, Ctrl-U clear");
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
    let mut mouse_hit_areas = MouseHitAreas::default();

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
        terminal.draw(|frame| {
            mouse_hit_areas = draw_ui(frame, &mut app, edit_session.as_ref());
        })?;

        if event::poll(Duration::from_millis(100))? {
            match event::read()? {
                Event::Key(key) => {
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
                Event::Mouse(mouse) => handle_mouse_event(&mut app, mouse, mouse_hit_areas),
                _ => {}
            }
        }
    }
}

fn rect_contains(area: Rect, column: u16, row: u16) -> bool {
    let max_x = area.x.saturating_add(area.width);
    let max_y = area.y.saturating_add(area.height);
    column >= area.x && column < max_x && row >= area.y && row < max_y
}

fn handle_mouse_event(app: &mut App, mouse: MouseEvent, hit_areas: MouseHitAreas) {
    let is_scroll_down = matches!(mouse.kind, MouseEventKind::ScrollDown);
    let is_scroll_up = matches!(mouse.kind, MouseEventKind::ScrollUp);
    let is_left_click = matches!(mouse.kind, MouseEventKind::Down(MouseButton::Left));
    if !is_scroll_down && !is_scroll_up {
        if !is_left_click {
            return;
        }
    }

    if app.filter_mode || app.search_mode || app.in_comment_input_mode() || app.in_edit_input_mode()
    {
        return;
    }

    if let Some(popup_area) = hit_areas.popup {
        if rect_contains(popup_area, mouse.column, mouse.row) {
            if app.in_actions_mode() {
                if is_scroll_down {
                    app.scroll_actions_down(1);
                } else {
                    app.scroll_actions_up(1);
                }
            } else if app.in_comments_mode() {
                if is_scroll_down {
                    app.next_comment();
                } else {
                    app.prev_comment();
                }
            } else if app.in_transitions_mode() {
                if is_scroll_down {
                    app.next_transition();
                } else {
                    app.prev_transition();
                }
            } else if app.in_boards_mode() {
                if is_scroll_down {
                    app.next_board();
                } else {
                    app.prev_board();
                }
            } else if app.in_custom_fields_mode() {
                if is_scroll_down {
                    app.next_custom_field();
                } else {
                    app.prev_custom_field();
                }
            } else if app.in_edit_menu_mode() {
                if is_scroll_down {
                    app.next_edit_menu();
                } else {
                    app.prev_edit_menu();
                }
            }
        }
        return;
    }

    if is_left_click {
        if let Some(issues_area) = hit_areas.issues {
            if let Some(position) =
                issue_row_position_from_click(issues_area, mouse.column, mouse.row)
            {
                app.select_visible_row(position);
            }
        }
        return;
    }

    if let Some(detail_area) = hit_areas.detail {
        if rect_contains(detail_area, mouse.column, mouse.row) {
            if is_scroll_down {
                app.scroll_detail_down(1);
            } else {
                app.scroll_detail_up(1);
            }
            return;
        }
    }

    if let Some(issues_area) = hit_areas.issues {
        if rect_contains(issues_area, mouse.column, mouse.row) {
            if is_scroll_down {
                app.next();
            } else {
                app.prev();
            }
        }
    }
}

fn issue_row_position_from_click(issues_area: Rect, column: u16, row: u16) -> Option<usize> {
    if !rect_contains(issues_area, column, row) {
        return None;
    }

    if issues_area.width < 2 || issues_area.height < 3 {
        return None;
    }

    let content_x_start = issues_area.x.saturating_add(1);
    let content_x_end = issues_area
        .x
        .saturating_add(issues_area.width.saturating_sub(1));
    if column < content_x_start || column >= content_x_end {
        return None;
    }

    let header_row = issues_area.y.saturating_add(1);
    if row <= header_row {
        return None;
    }

    Some(usize::from(
        row.saturating_sub(header_row.saturating_add(1)),
    ))
}

#[cfg(test)]
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
                if app.has_active_filter() {
                    app.status_line =
                        format!("Filter active: '{}'. f edit, F clear", app.filter_query());
                } else {
                    app.status_line = String::from("Filter exited");
                }
            }
            KeyCode::Char('u') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                let selected_key = app.selected_issue_key();
                app.filter_input.clear();
                app.normalize_selection_with_preferred_key(selected_key.as_deref());
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

    if app.search_mode {
        match key.code {
            KeyCode::Esc => {
                app.search_mode = false;
                app.search_input.clear();
                app.status_line = String::from("Search cancelled");
            }
            KeyCode::Enter => {
                app.search_mode = false;
                if app.search_input.is_empty() {
                    app.status_line = String::from("Search exited");
                } else {
                    app.submit_search_query();
                    app.search_input.clear();
                }
            }
            KeyCode::Char('u') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                app.search_input.clear();
            }
            KeyCode::Backspace => {
                app.search_input.pop();
            }
            KeyCode::Char(c) => {
                if !key.modifiers.contains(KeyModifiers::CONTROL) {
                    app.search_input.push(c);
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
                app.set_edit_input(value);
                app.submit_edit_input(edit_issue_request_tx);
                sync_edit_input_session(app, edit_session);
            }
            _ => {
                session.textarea.input(key);
                app.set_edit_input(session.textarea.lines().join("\n"));
            }
        }
        return None;
    }

    if matches!(key.code, KeyCode::Tab) {
        app.toggle_pane_orientation();
        return None;
    }

    if app.in_comments_mode() {
        match key.code {
            KeyCode::Char('q') | KeyCode::Esc | KeyCode::Char('c') => app.enter_detail_mode(),
            KeyCode::Char('j') | KeyCode::Down | KeyCode::Char('n') => app.next_comment(),
            KeyCode::Char('k') | KeyCode::Up | KeyCode::Char('p') => app.prev_comment(),
            KeyCode::Char('a') => app.start_comment_input(),
            KeyCode::Char('e') => app.enter_edit_menu_mode(),
            KeyCode::Char('u') => app.enter_custom_fields_mode(),
            KeyCode::Char('?') => app.enter_actions_mode(),
            KeyCode::Char('r') => app.reload_issues(),
            KeyCode::Char('f') => {
                focus_filter_input(app);
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
            KeyCode::Char('e') => app.enter_edit_menu_mode(),
            KeyCode::Char('u') => app.enter_custom_fields_mode(),
            KeyCode::Char('b') => app.enter_boards_mode(),
            KeyCode::Char('c') => app.enter_comments_mode(),
            KeyCode::Char('t') => app.enter_transitions_mode(),
            KeyCode::Char('r') => app.reload_issues(),
            KeyCode::Char('o') => app.open_selected_issue(),
            KeyCode::Char('f') => {
                focus_filter_input(app);
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
            KeyCode::Char('e') => app.enter_edit_menu_mode(),
            KeyCode::Char('u') => app.enter_custom_fields_mode(),
            KeyCode::Char('c') => app.enter_comments_mode(),
            KeyCode::Char('t') => app.enter_transitions_mode(),
            KeyCode::Char('?') => app.enter_actions_mode(),
            KeyCode::Char('r') => app.reload_issues(),
            KeyCode::Char('o') => app.open_selected_issue(),
            KeyCode::Char('f') => {
                focus_filter_input(app);
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
            KeyCode::Char('f') => {
                focus_filter_input(app);
            }
            KeyCode::Enter => app.start_selected_custom_field_edit_input(),
            _ => {}
        }
        return None;
    }

    if app.in_edit_menu_mode() {
        match key.code {
            KeyCode::Char('q') | KeyCode::Esc | KeyCode::Char('e') => app.enter_detail_mode(),
            KeyCode::Char('j') | KeyCode::Down | KeyCode::Char('n') => app.next_edit_menu(),
            KeyCode::Char('k') | KeyCode::Up | KeyCode::Char('p') => app.prev_edit_menu(),
            KeyCode::Char('b') => app.enter_boards_mode(),
            KeyCode::Char('c') => app.enter_comments_mode(),
            KeyCode::Char('t') => app.enter_transitions_mode(),
            KeyCode::Char('u') => app.enter_custom_fields_mode(),
            KeyCode::Char('?') => app.enter_actions_mode(),
            KeyCode::Char('r') => app.reload_issues(),
            KeyCode::Char('o') => app.open_selected_issue(),
            KeyCode::Char('f') => {
                focus_filter_input(app);
            }
            KeyCode::Enter => app.apply_selected_edit_menu(),
            _ => {}
        }
        return None;
    }

    if app.in_transitions_mode() {
        match key.code {
            KeyCode::Char('q') | KeyCode::Esc | KeyCode::Char('t') => app.enter_detail_mode(),
            KeyCode::Char('j') | KeyCode::Down | KeyCode::Char('n') => app.next_transition(),
            KeyCode::Char('k') | KeyCode::Up | KeyCode::Char('p') => app.prev_transition(),
            KeyCode::Char('e') => app.enter_edit_menu_mode(),
            KeyCode::Char('u') => app.enter_custom_fields_mode(),
            KeyCode::Char('c') => app.enter_comments_mode(),
            KeyCode::Char('?') => app.enter_actions_mode(),
            KeyCode::Char('r') => app.reload_issues(),
            KeyCode::Char('f') => {
                focus_filter_input(app);
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
        KeyCode::Char('e') => app.enter_edit_menu_mode(),
        KeyCode::Char('u') => app.enter_custom_fields_mode(),
        KeyCode::Char('b') => app.enter_boards_mode(),
        KeyCode::Char('c') => app.enter_comments_mode(),
        KeyCode::Char('t') => app.enter_transitions_mode(),
        KeyCode::Char('?') => app.enter_actions_mode(),
        KeyCode::Char('r') => app.reload_issues(),
        KeyCode::Char('1') => app.toggle_zoom_issues(),
        KeyCode::Char('2') => app.toggle_zoom_detail(),
        KeyCode::Char('f') => focus_filter_input(app),
        KeyCode::Char('F') => {
            let selected_key = app.selected_issue_key();
            app.filter_input.clear();
            app.normalize_selection_with_preferred_key(selected_key.as_deref());
            app.status_line = String::from("Filter cleared");
        }
        KeyCode::Char('/') => focus_search_input(app),
        KeyCode::Char('n') => app.repeat_last_search_forward(),
        KeyCode::Char('N') => app.repeat_last_search_backward(),
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

fn detail_key_value_line(label: &str, value: &str, theme: Theme) -> Line<'static> {
    let value_style = if value == "<no description>" {
        theme.detail_placeholder()
    } else {
        theme.detail_value()
    };
    Line::from(vec![
        Span::styled(format!("{label}: "), theme.detail_label()),
        Span::styled(value.to_string(), value_style),
    ])
}

fn append_multiline_value(
    lines: &mut Vec<Line<'static>>,
    value: &str,
    style: ratatui::style::Style,
) {
    let rendered = if value.is_empty() {
        vec![String::new()]
    } else {
        value.lines().map(ToString::to_string).collect()
    };
    lines.extend(
        rendered
            .into_iter()
            .map(|line| Line::from(Span::styled(line, style))),
    );
}

fn build_detail_lines(view: &DetailViewModel, theme: Theme) -> Vec<Line<'static>> {
    match view.mode {
        DetailViewMode::EmptySelection => vec![Line::from(Span::styled(
            "No issue selected",
            theme.detail_placeholder(),
        ))],
        DetailViewMode::Loaded => {
            let mut lines = Vec::new();
            if let Some(key) = &view.key {
                lines.push(detail_key_value_line("Key", key, theme));
            }
            lines.push(detail_key_value_line(
                "Summary",
                view.summary.as_str(),
                theme,
            ));
            lines.extend(
                view.meta_fields
                    .iter()
                    .map(|field| detail_key_value_line(field.label, field.value.as_str(), theme)),
            );
            lines.push(Line::default());
            lines.push(Line::from(Span::styled(
                "Description",
                theme.detail_section_title(),
            )));
            let description_style = if view.description == "<no description>" {
                theme.detail_placeholder()
            } else {
                theme.detail_value()
            };
            append_multiline_value(&mut lines, view.description.as_str(), description_style);
            lines
        }
        DetailViewMode::Error => {
            let mut lines = Vec::new();
            let key = view.key.as_deref().unwrap_or("<no issue>");
            lines.push(Line::from(Span::styled(
                format!("Detail load failed for {key}"),
                theme.detail_error(),
            )));
            lines.push(Line::default());
            for field in &view.meta_fields {
                lines.push(detail_key_value_line(
                    field.label,
                    field.value.as_str(),
                    theme,
                ));
            }
            lines.push(Line::default());
            lines.push(Line::from(Span::styled(
                "Summary",
                theme.detail_section_title(),
            )));
            lines.push(Line::from(Span::styled(
                view.summary.clone(),
                theme.detail_value(),
            )));
            lines.push(Line::default());
            lines.push(Line::from(Span::styled(
                "Detail load failed",
                theme.detail_error(),
            )));
            append_multiline_value(
                &mut lines,
                view.error_message.as_deref().unwrap_or("unknown error"),
                theme.detail_value(),
            );
            lines
        }
        DetailViewMode::Loading => {
            let mut lines = Vec::new();
            let key = view.key.as_deref().unwrap_or("<no issue>");
            lines.push(Line::from(Span::styled(
                format!("Loading detail for {key}..."),
                theme.detail_loading(),
            )));
            lines.push(Line::default());
            lines.push(Line::from(Span::styled(
                "Summary",
                theme.detail_section_title(),
            )));
            lines.push(Line::from(Span::styled(
                view.summary.clone(),
                theme.detail_value(),
            )));
            lines.push(Line::default());
            lines.push(Line::from(Span::styled(
                "Source",
                theme.detail_section_title(),
            )));
            lines.push(Line::from(Span::styled(
                view.source.as_deref().unwrap_or("<none>").to_string(),
                theme.detail_value(),
            )));
            lines
        }
        DetailViewMode::SummaryOnly => {
            let mut lines = Vec::new();
            if let Some(key) = &view.key {
                lines.push(detail_key_value_line("Key", key, theme));
            }
            for field in &view.meta_fields {
                lines.push(detail_key_value_line(
                    field.label,
                    field.value.as_str(),
                    theme,
                ));
            }
            lines.push(Line::default());
            lines.push(Line::from(Span::styled(
                "Summary",
                theme.detail_section_title(),
            )));
            lines.push(Line::from(Span::styled(
                view.summary.clone(),
                theme.detail_value(),
            )));
            lines.push(Line::default());
            lines.push(Line::from(Span::styled(
                "Source",
                theme.detail_section_title(),
            )));
            lines.push(Line::from(Span::styled(
                view.source.as_deref().unwrap_or("<none>").to_string(),
                theme.detail_value(),
            )));
            lines
        }
    }
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

fn vertical_scrollbar_state(
    content_lines: usize,
    viewport_height: u16,
    scroll_offset: u16,
) -> Option<ScrollbarState> {
    let viewport_lines = usize::from(viewport_height.max(1));
    if content_lines <= viewport_lines {
        return None;
    }

    let max_scroll = content_lines.saturating_sub(viewport_lines);
    let clamped_scroll = usize::from(scroll_offset).min(max_scroll);
    Some(
        ScrollbarState::new(content_lines)
            .viewport_content_length(viewport_lines)
            .position(clamped_scroll),
    )
}

fn draw_ui(
    frame: &mut Frame,
    app: &mut App,
    edit_session: Option<&EditInputSession>,
) -> MouseHitAreas {
    let theme = Theme::solarized_warm();
    frame.render_widget(Block::default().style(theme.screen()), frame.area());
    let mut mouse_hit_areas = MouseHitAreas::default();

    let show_filter_bar = app.filter_mode || app.has_active_filter();
    let show_search_bar = app.search_mode;
    let mut root_constraints = Vec::new();
    if show_filter_bar {
        root_constraints.push(Constraint::Length(1));
    }
    if show_search_bar {
        root_constraints.push(Constraint::Length(1));
    }
    root_constraints.push(Constraint::Min(0));
    root_constraints.push(Constraint::Length(1));
    let root_chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints(root_constraints)
        .split(frame.area());
    let mut chunk_index = 0usize;
    let filter_bar_area = if show_filter_bar {
        let area = Some(root_chunks[chunk_index]);
        chunk_index += 1;
        area
    } else {
        None
    };
    let search_bar_area = if show_search_bar {
        let area = Some(root_chunks[chunk_index]);
        chunk_index += 1;
        area
    } else {
        None
    };
    let main_area = root_chunks[chunk_index];
    let footer_area = root_chunks[chunk_index + 1];

    let (first_pane_percent, second_pane_percent) = app.pane_width_percentages();
    let main_direction = match app.pane_orientation() {
        PaneOrientation::Horizontal => Direction::Vertical,
        PaneOrientation::Vertical => Direction::Horizontal,
    };
    let main_chunks = Layout::default()
        .direction(main_direction)
        .constraints([
            Constraint::Percentage(first_pane_percent),
            Constraint::Percentage(second_pane_percent),
        ])
        .split(main_area);
    let pane_zoom = app.pane_zoom();

    let visible = app.visible_indices();

    let rows: Vec<Row> = visible
        .iter()
        .filter_map(|index| app.issues.get(*index))
        .map(|issue| {
            Row::new(vec![
                Cell::from(issue.key.clone()),
                Cell::from(issue.summary.clone()),
                Cell::from(issue.status.clone()).style(theme.table_status(issue.status.as_str())),
                Cell::from(issue.assignee.clone()),
            ])
            .style(theme.table_row())
        })
        .collect();

    let issues_title = if app.using_adapter {
        "Issues (adapter) (1)"
    } else {
        "Issues (mock) (1)"
    };

    let issues_active = pane_zoom == PaneZoom::Issues;
    let mut issues_block = Block::default()
        .title(Line::from(Span::styled(
            issues_title,
            theme.panel_title(issues_active),
        )))
        .borders(Borders::ALL)
        .border_style(theme.panel_border(issues_active))
        .style(theme.panel());
    if issues_active {
        issues_block = issues_block
            .title(Line::from(Span::styled("ZOOMED", theme.panel_title(true))).right_aligned());
    }

    let table = Table::new(
        rows,
        [
            Constraint::Length(12),
            Constraint::Percentage(52),
            Constraint::Length(14),
            Constraint::Length(14),
        ],
    )
    .header(Row::new(vec!["Key", "Summary", "Status", "Assignee"]).style(theme.table_header()))
    .block(issues_block)
    .row_highlight_style(theme.table_selected())
    .highlight_symbol(">> ");

    let mut state = TableState::default();
    if !visible.is_empty() {
        state.select(Some(app.selected));
    }

    if pane_zoom != PaneZoom::Detail {
        let issues_area = if pane_zoom == PaneZoom::Issues {
            main_area
        } else {
            main_chunks[0]
        };
        mouse_hit_areas.issues = Some(issues_area);
        frame.render_stateful_widget(table, issues_area, &mut state);
    }

    if pane_zoom != PaneZoom::Issues {
        let detail_area = if pane_zoom == PaneZoom::Detail {
            main_area
        } else {
            main_chunks[1]
        };
        mouse_hit_areas.detail = Some(detail_area);
        let detail_viewport_height = detail_area.height.saturating_sub(2);
        app.set_detail_viewport_height(detail_viewport_height);
        let detail_active = pane_zoom == PaneZoom::Detail;
        let mut detail_block = Block::default()
            .title(Line::from(Span::styled(
                "Detail (2)",
                theme.panel_title(detail_active),
            )))
            .borders(Borders::ALL)
            .border_style(theme.panel_border(detail_active))
            .style(theme.panel());
        if detail_active {
            detail_block = detail_block
                .title(Line::from(Span::styled("ZOOMED", theme.panel_title(true))).right_aligned());
        }
        let detail_view = app.detail_view_model_for_selected();
        let detail_lines = build_detail_lines(&detail_view, theme);
        let detail_line_count = detail_lines.len().max(1);
        let detail_inner = detail_block.inner(detail_area);
        let detail_scroll = app.detail_scroll();
        let detail = Paragraph::new(Text::from(detail_lines))
            .style(theme.panel())
            .block(detail_block)
            .scroll((detail_scroll, 0))
            .wrap(Wrap { trim: false });
        frame.render_widget(detail, detail_area);
        if let Some(mut scrollbar_state) =
            vertical_scrollbar_state(detail_line_count, detail_viewport_height, detail_scroll)
        {
            frame.render_stateful_widget(
                Scrollbar::new(ScrollbarOrientation::VerticalRight)
                    .begin_symbol(None)
                    .end_symbol(None)
                    .thumb_style(theme.panel_title(detail_active))
                    .track_style(theme.panel_border(detail_active)),
                detail_inner,
                &mut scrollbar_state,
            );
        }
    }

    if app.in_popup_mode() && !app.in_edit_input_mode() {
        let popup_title = app.right_pane_title();
        let popup_text = app.right_pane_text();
        let popup_area = adaptive_popup_area(main_area, popup_title, popup_text.as_str());
        mouse_hit_areas.popup = Some(popup_area);

        if app.in_actions_mode() {
            let popup_viewport_height = popup_area.height.saturating_sub(2);
            app.set_actions_viewport_height(popup_viewport_height);
        }

        let popup_block = Block::default()
            .title(Line::from(Span::styled(
                popup_title.to_string(),
                theme.popup_title(),
            )))
            .borders(Borders::ALL)
            .border_style(theme.popup_border())
            .style(theme.popup());
        let popup_inner = popup_block.inner(popup_area);
        let popup_line_count = popup_text.lines().count().max(1);
        let actions_scroll = app.actions_scroll();
        let mut popup = Paragraph::new(popup_text)
            .style(theme.popup())
            .block(popup_block)
            .wrap(Wrap { trim: false });
        if app.in_actions_mode() {
            popup = popup.scroll((actions_scroll, 0));
        }
        frame.render_widget(Clear, popup_area);
        frame.render_widget(popup, popup_area);
        if app.in_actions_mode() {
            let popup_viewport_height = popup_area.height.saturating_sub(2);
            if let Some(mut scrollbar_state) =
                vertical_scrollbar_state(popup_line_count, popup_viewport_height, actions_scroll)
            {
                frame.render_stateful_widget(
                    Scrollbar::new(ScrollbarOrientation::VerticalRight)
                        .begin_symbol(None)
                        .end_symbol(None)
                        .thumb_style(theme.popup_title())
                        .track_style(theme.popup_border()),
                    popup_inner,
                    &mut scrollbar_state,
                );
            }
        }
    }

    if app.in_edit_input_mode() {
        let is_description_target = app.edit_target_label() == "description";
        let is_summary_target = app.edit_target_label() == "summary";
        let edit_popup_area = edit_popup_area(main_area, is_description_target, is_summary_target);
        frame.render_widget(Clear, edit_popup_area);
        let issue_key = app
            .selected_issue_key()
            .unwrap_or_else(|| String::from("<no issue>"));
        let edit_title = format!("Edit {} ({issue_key})", app.edit_target_display());
        let popup_block = Block::default()
            .title(Line::from(Span::styled(edit_title, theme.popup_title())))
            .borders(Borders::ALL)
            .border_style(theme.popup_border())
            .style(theme.popup());
        frame.render_widget(popup_block.clone(), edit_popup_area);

        let inner = popup_block.inner(edit_popup_area);
        if inner.width > 0 && inner.height > 0 {
            if inner.height > 1 {
                let input_height = edit_input_height(inner.height, is_summary_target);
                let sections = Layout::default()
                    .direction(Direction::Vertical)
                    .constraints([Constraint::Length(input_height), Constraint::Length(1)])
                    .split(inner);
                frame.render_widget(Clear, sections[0]);
                if let Some(session) = edit_session {
                    frame.render_widget(&session.textarea, sections[0]);
                } else {
                    frame.render_widget(
                        Paragraph::new(app.edit_input())
                            .style(theme.popup())
                            .wrap(Wrap { trim: false }),
                        sections[0],
                    );
                }
                let controls = Paragraph::new("Ctrl+s save  Esc cancel")
                    .style(theme.edit_help())
                    .wrap(Wrap { trim: true });
                frame.render_widget(Clear, sections[1]);
                frame.render_widget(controls, sections[1]);
            } else if let Some(session) = edit_session {
                frame.render_widget(Clear, inner);
                frame.render_widget(&session.textarea, inner);
            } else {
                frame.render_widget(Clear, inner);
                frame.render_widget(
                    Paragraph::new(app.edit_input())
                        .style(theme.popup())
                        .wrap(Wrap { trim: false }),
                    inner,
                );
            }
        }
    }

    let mode = if app.filter_mode {
        "FILTER"
    } else if app.search_mode {
        "SEARCH"
    } else if app.in_comment_input_mode() {
        "COMMENT-INPUT"
    } else if app.in_edit_input_mode() {
        "EDIT-INPUT"
    } else if app.in_actions_mode() {
        "ACTIONS"
    } else if app.in_edit_menu_mode() {
        "EDIT"
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
    if let Some(filter_bar_area) = filter_bar_area {
        let display_filter = if app.filter_mode {
            app.filter_input.as_str()
        } else {
            app.filter_query()
        };
        let filter_label = if display_filter.is_empty() {
            "<empty>"
        } else {
            display_filter
        };
        let filter_line = Line::from(vec![
            Span::styled("[FILTER]", theme.footer_mode()),
            Span::styled(format!(" {filter_label}"), theme.footer_hint()),
            Span::styled(
                if app.filter_mode {
                    " | Esc/Enter exit | Ctrl-U clear"
                } else {
                    " | f edit | F clear"
                },
                theme.footer_hint(),
            ),
        ]);
        frame.render_widget(
            Paragraph::new(filter_line).style(theme.filter_bar(app.filter_mode)),
            filter_bar_area,
        );
        if app.filter_mode {
            // "[FILTER] " prefix is 9 chars, then the input text length
            let cursor_x = filter_bar_area.x + 9 + app.filter_input.len() as u16;
            let cursor_y = filter_bar_area.y;
            frame.set_cursor_position((
                cursor_x.min(filter_bar_area.right().saturating_sub(1)),
                cursor_y,
            ));
        }
    }
    if let Some(search_bar_area) = search_bar_area {
        let display_search = app.search_input.as_str();
        let search_label = if display_search.is_empty() {
            "<empty>"
        } else {
            display_search
        };
        let search_line = Line::from(vec![
            Span::styled("[SEARCH]", theme.footer_mode()),
            Span::styled(format!(" {search_label}"), theme.footer_hint()),
            Span::styled(" | Enter search | Esc cancel", theme.footer_hint()),
        ]);
        frame.render_widget(
            Paragraph::new(search_line).style(theme.search_bar(app.search_mode)),
            search_bar_area,
        );
        if app.search_mode {
            // "[SEARCH] " prefix is 9 chars, then the input text length
            let cursor_x = search_bar_area.x + 9 + app.search_input.len() as u16;
            let cursor_y = search_bar_area.y;
            frame.set_cursor_position((
                cursor_x.min(search_bar_area.right().saturating_sub(1)),
                cursor_y,
            ));
        }
    }
    let (footer_hint, include_status) = if app.filter_mode {
        (
            String::from("type to filter | Esc/Enter exit | Ctrl-U clear | Backspace delete"),
            false,
        )
    } else if app.search_mode {
        (
            String::from("type query | Enter search | Esc cancel | Ctrl-U clear"),
            false,
        )
    } else if app.in_comment_input_mode() {
        (
            format!("draft: {} | Enter submit | Esc cancel", app.comment_input()),
            true,
        )
    } else if app.in_edit_input_mode() {
        (
            format!(
                "editor open | target: {} | Ctrl+s save | Esc cancel",
                app.edit_target_display()
            ),
            true,
        )
    } else if app.in_actions_mode() {
        (
            String::from("j/k scroll | Ctrl+d/u page | ? close | q quit"),
            true,
        )
    } else if app.in_custom_fields_mode() {
        (
            String::from("j/k pick | Enter edit | u close | q quit"),
            true,
        )
    } else if app.in_edit_menu_mode() {
        (
            String::from("j/k/n/p pick | Enter edit | e close | q quit"),
            true,
        )
    } else if app.in_boards_mode() {
        (
            String::from("j/k pick | Enter switch | b close | q quit"),
            true,
        )
    } else if app.in_transitions_mode() {
        (
            String::from("j/k pick | Enter apply | t close | q quit"),
            true,
        )
    } else if app.in_comments_mode() {
        (String::from("j/k move | a add | c close | q quit"), true)
    } else if app.choose_mode {
        (
            String::from(
                "j/k zoom | Enter choose | f filter | / search | n/N repeat | 1/2 zoom | TAB layout | ? help | q quit",
            ),
            true,
        )
    } else {
        (
            String::from(
                "j/k scroll | f filter | / search | n/N repeat | r reload | o open | 1/2 zoom | TAB layout | ? help | q quit",
            ),
            true,
        )
    };
    let mut footer_spans = vec![
        Span::styled(format!("[{mode}]"), theme.footer_mode()),
        Span::styled(format!(" {footer_hint}"), theme.footer_hint()),
    ];
    if include_status && !app.status_line.is_empty() {
        footer_spans.push(Span::styled(" | ", theme.footer_hint()));
        footer_spans.push(Span::styled(
            app.status_line.clone(),
            theme.status(status_tone(app.status_line.as_str())),
        ));
    }
    frame.render_widget(
        Paragraph::new(Line::from(footer_spans)).style(theme.footer_base()),
        footer_area,
    );
    mouse_hit_areas
}

#[cfg(test)]
mod tests {
    use std::sync::mpsc;

    use crossterm::event::KeyEventState;
    use crossterm::event::{
        KeyCode, KeyEvent, KeyEventKind, KeyModifiers, MouseButton, MouseEvent, MouseEventKind,
    };
    use ratatui::{
        backend::TestBackend, buffer::Buffer, layout::Rect, widgets::ScrollbarState, Terminal,
    };

    use super::{
        adaptive_popup_area, build_detail_lines, build_edit_textarea, draw_ui, edit_input_height,
        edit_popup_area, handle_key_event, handle_key_event_with_edit_session, handle_mouse_event,
        percent_popup_area, vertical_scrollbar_state, EditInputSession, MouseHitAreas, RunOutcome,
    };
    use crate::{
        app::{App, DetailMetaField, DetailViewMode, DetailViewModel, PaneOrientation, PaneZoom},
        theme::Theme,
        types::AdapterSource,
    };

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

    fn mouse_scroll(kind: MouseEventKind, column: u16, row: u16) -> MouseEvent {
        MouseEvent {
            kind,
            column,
            row,
            modifiers: KeyModifiers::empty(),
        }
    }

    fn mouse_click(column: u16, row: u16) -> MouseEvent {
        MouseEvent {
            kind: MouseEventKind::Down(MouseButton::Left),
            column,
            row,
            modifiers: KeyModifiers::empty(),
        }
    }

    fn buffer_contains_text(buffer: &Buffer, needle: &str) -> bool {
        for y in 0..buffer.area.height {
            let mut row = String::new();
            for x in 0..buffer.area.width {
                if let Some(cell) = buffer.cell((x, y)) {
                    row.push_str(cell.symbol());
                }
            }
            if row.contains(needle) {
                return true;
            }
        }
        false
    }

    #[test]
    fn build_detail_lines_loaded_orders_sections_and_fields() {
        let view = DetailViewModel {
            mode: DetailViewMode::Loaded,
            key: Some(String::from("JAY-500")),
            summary: String::from("Structured detail rendering"),
            meta_fields: vec![
                DetailMetaField {
                    label: "Status",
                    value: String::from("In Progress"),
                },
                DetailMetaField {
                    label: "Assignee",
                    value: String::from("alice"),
                },
            ],
            description: String::from("First line\nSecond line"),
            source: None,
            error_message: None,
        };

        let lines = build_detail_lines(&view, Theme::solarized_warm());
        assert_eq!(lines[0].spans[0].content, "Key: ");
        assert_eq!(lines[0].spans[1].content, "JAY-500");
        assert_eq!(lines[1].spans[0].content, "Summary: ");
        assert_eq!(lines[2].spans[0].content, "Status: ");
        assert_eq!(lines[3].spans[0].content, "Assignee: ");
        assert_eq!(lines[5].spans[0].content, "Description");
        assert_eq!(lines[6].spans[0].content, "First line");
        assert_eq!(lines[7].spans[0].content, "Second line");
    }

    #[test]
    fn build_detail_lines_loading_includes_loading_banner() {
        let view = DetailViewModel {
            mode: DetailViewMode::Loading,
            key: Some(String::from("JAY-501")),
            summary: String::from("Loading summary"),
            meta_fields: Vec::new(),
            description: String::new(),
            source: Some(String::from("board=myissue")),
            error_message: None,
        };

        let lines = build_detail_lines(&view, Theme::solarized_warm());
        assert_eq!(lines[0].spans[0].content, "Loading detail for JAY-501...");
        assert_eq!(lines[2].spans[0].content, "Summary");
        assert_eq!(lines[5].spans[0].content, "Source");
        assert_eq!(lines[6].spans[0].content, "board=myissue");
    }

    #[test]
    fn build_detail_lines_error_includes_error_banner_and_message() {
        let view = DetailViewModel {
            mode: DetailViewMode::Error,
            key: Some(String::from("JAY-502")),
            summary: String::from("Problematic issue"),
            meta_fields: vec![
                DetailMetaField {
                    label: "Status",
                    value: String::from("Open"),
                },
                DetailMetaField {
                    label: "Assignee",
                    value: String::from("bob"),
                },
            ],
            description: String::new(),
            source: None,
            error_message: Some(String::from("adapter timeout")),
        };

        let lines = build_detail_lines(&view, Theme::solarized_warm());
        assert_eq!(lines[0].spans[0].content, "Detail load failed for JAY-502");
        assert_eq!(lines[5].spans[0].content, "Summary");
        assert_eq!(lines[8].spans[0].content, "Detail load failed");
        assert_eq!(lines[9].spans[0].content, "adapter timeout");
    }

    #[test]
    fn build_detail_lines_marks_missing_description_as_placeholder() {
        let view = DetailViewModel {
            mode: DetailViewMode::Loaded,
            key: Some(String::from("JAY-503")),
            summary: String::from("No description"),
            meta_fields: vec![DetailMetaField {
                label: "Status",
                value: String::from("Open"),
            }],
            description: String::from("<no description>"),
            source: None,
            error_message: None,
        };

        let lines = build_detail_lines(&view, Theme::solarized_warm());
        let description_line = lines.last().expect("description line");
        assert_eq!(description_line.spans[0].content, "<no description>");
        assert!(description_line.spans[0]
            .style
            .add_modifier
            .contains(ratatui::style::Modifier::DIM));
    }

    #[test]
    fn vertical_scrollbar_state_is_none_when_content_fits_viewport() {
        let state = vertical_scrollbar_state(5, 5, 0);
        assert_eq!(state, None);
    }

    #[test]
    fn vertical_scrollbar_state_clamps_scroll_position_to_max() {
        let state = vertical_scrollbar_state(20, 6, 50).expect("scrollbar state");
        assert_eq!(
            state,
            ScrollbarState::new(20)
                .viewport_content_length(6)
                .position(14)
        );
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
    fn e_enters_edit_menu_mode() {
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
        assert!(app.in_edit_menu_mode());
        assert!(!app.in_edit_input_mode());
    }

    #[test]
    fn e_then_enter_starts_summary_edit_input_mode() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('e')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Enter),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );

        assert_eq!(outcome, None);
        assert!(app.in_edit_input_mode());
        assert_eq!(app.edit_target_label(), "summary");
    }

    #[test]
    fn e_then_j_j_then_enter_starts_labels_edit_input_mode() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('e')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('j')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('j')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Enter),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );

        assert_eq!(outcome, None);
        assert!(app.in_edit_input_mode());
        assert_eq!(app.edit_target_label(), "labels");
    }

    #[test]
    fn e_in_comments_mode_opens_edit_menu() {
        let mut app = App::new(mock_source(), false);
        app.enter_comments_mode();
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
        assert!(app.in_edit_menu_mode());
    }

    #[test]
    fn e_closes_edit_menu_before_quit() {
        let mut app = App::new(mock_source(), false);
        app.enter_edit_menu_mode();
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
        assert!(!app.in_edit_menu_mode());
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
    fn ctrl_v_toggles_layout_in_normal_mode() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Tab),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.pane_orientation(), PaneOrientation::Vertical);
    }

    #[test]
    fn ctrl_v_toggles_layout_in_popup_mode() {
        let mut app = App::new(mock_source(), false);
        app.enter_actions_mode();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Tab),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.pane_orientation(), PaneOrientation::Vertical);
    }

    #[test]
    fn ctrl_v_is_ignored_in_filter_mode() {
        let mut app = App::new(mock_source(), false);
        app.filter_mode = true;
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key_with_modifiers(KeyCode::Char('v'), KeyModifiers::CONTROL),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.pane_orientation(), PaneOrientation::Horizontal);
    }

    #[test]
    fn enter_unfocuses_filter_and_keeps_input() {
        let mut app = App::new(mock_source(), false);
        app.filter_mode = true;
        app.filter_input = "adapter".to_string();
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
        assert!(!app.filter_mode);
        assert_eq!(app.filter_input, "adapter");
        assert!(app.status_line.contains("Filter active"));
    }

    #[test]
    fn esc_exits_filter_mode_and_keeps_text() {
        let mut app = App::new(mock_source(), false);
        app.filter_mode = true;
        app.filter_input = "adapter".to_string();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Esc),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert!(!app.filter_mode);
        assert_eq!(app.filter_input, "adapter");
        assert!(app.status_line.contains("Filter active"));
    }

    #[test]
    fn f_refocuses_when_filter_is_active() {
        let mut app = App::new(mock_source(), false);
        app.filter_input = "adapter".to_string();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('f')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert!(app.filter_mode);
        assert_eq!(app.filter_input, "adapter");
        assert!(app.status_line.contains("Filter focused"));
    }

    #[test]
    fn slash_enters_search_mode_in_detail_mode() {
        let mut app = App::new(mock_source(), false);
        app.filter_input = "adapter".to_string();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('/')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert!(app.search_mode);
        assert!(!app.filter_mode);
        assert_eq!(app.search_input, "");
        assert!(app.status_line.contains("Search focused"));
    }

    #[test]
    fn enter_submits_search_and_jumps_selection() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('/')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('m')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('e')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('a')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('s')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('u')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('r')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Enter),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert!(!app.search_mode);
        assert_eq!(app.selected_issue_key().as_deref(), Some("JAY-104"));
        assert!(app.status_line.contains("Search 'measur'"));
    }

    #[test]
    fn esc_exits_search_mode_and_discards_input() {
        let mut app = App::new(mock_source(), false);
        app.selected = 2;
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('/')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('j')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Esc),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.selected_issue_key().as_deref(), Some("JAY-103"));
        assert!(!app.search_mode);
        assert!(app.search_input.is_empty());
        assert!(app.status_line.contains("Search cancelled"));
    }

    #[test]
    fn ctrl_u_clears_filter_text_and_stays_in_mode() {
        let mut app = App::new(mock_source(), false);
        app.filter_mode = true;
        app.filter_input = "adapter".to_string();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key_with_modifiers(KeyCode::Char('u'), KeyModifiers::CONTROL),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert!(app.filter_mode);
        assert!(app.filter_input.is_empty());
    }

    #[test]
    fn ctrl_u_clears_search_text_and_stays_in_mode() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('/')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('t')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        let _ = handle_key_event(
            &mut app,
            key(KeyCode::Char('e')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(app.search_input, "te");

        let outcome = handle_key_event(
            &mut app,
            key_with_modifiers(KeyCode::Char('u'), KeyModifiers::CONTROL),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert!(app.search_mode);
        assert!(app.search_input.is_empty());
    }

    #[test]
    fn uppercase_f_clears_filter_from_normal_mode() {
        let mut app = App::new(mock_source(), false);
        app.filter_input = "adapter".to_string();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('F')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert!(!app.filter_mode);
        assert!(app.filter_input.is_empty());
        assert!(app.status_line.contains("Filter cleared"));
    }

    #[test]
    fn n_and_uppercase_n_repeat_last_search() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        app.search_input = "jay".to_string();
        app.submit_search_query();
        assert_eq!(app.selected_issue_key().as_deref(), Some("JAY-101"));

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('n')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.selected_issue_key().as_deref(), Some("JAY-102"));

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('N')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.selected_issue_key().as_deref(), Some("JAY-101"));
    }

    #[test]
    fn slash_is_ignored_in_comments_mode() {
        let mut app = App::new(mock_source(), false);
        app.enter_comments_mode();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('/')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert!(!app.search_mode);
        assert!(app.in_comments_mode());
    }

    #[test]
    fn ctrl_v_is_ignored_in_search_mode() {
        let mut app = App::new(mock_source(), false);
        app.search_mode = true;
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key_with_modifiers(KeyCode::Char('v'), KeyModifiers::CONTROL),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.pane_orientation(), PaneOrientation::Horizontal);
    }

    #[test]
    fn ctrl_v_is_ignored_in_comment_input_mode() {
        let mut app = App::new(mock_source(), false);
        app.enter_comments_mode();
        app.start_comment_input();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key_with_modifiers(KeyCode::Char('v'), KeyModifiers::CONTROL),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.pane_orientation(), PaneOrientation::Horizontal);
    }

    #[test]
    fn ctrl_v_is_ignored_in_edit_input_mode() {
        let mut app = App::new(mock_source(), false);
        app.start_summary_edit_input();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();
        let mut edit_session = None;

        let outcome = handle_key_event_with_edit_session(
            &mut app,
            &mut edit_session,
            key_with_modifiers(KeyCode::Char('v'), KeyModifiers::CONTROL),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert!(app.in_edit_input_mode());
        assert_eq!(app.pane_orientation(), PaneOrientation::Horizontal);
    }

    #[test]
    fn one_and_two_toggle_zoom_in_normal_mode() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('1')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.pane_zoom(), PaneZoom::Issues);

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('1')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.pane_zoom(), PaneZoom::None);

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('2')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.pane_zoom(), PaneZoom::Detail);
    }

    #[test]
    fn one_and_two_switch_zoom_target_when_other_pane_is_zoomed() {
        let mut app = App::new(mock_source(), false);
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('2')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.pane_zoom(), PaneZoom::Detail);

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('1')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.pane_zoom(), PaneZoom::Issues);
    }

    #[test]
    fn one_and_two_do_not_toggle_zoom_in_filter_mode() {
        let mut app = App::new(mock_source(), false);
        app.filter_mode = true;
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('1')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.pane_zoom(), PaneZoom::None);
        assert_eq!(app.filter_input, "1");
    }

    #[test]
    fn one_and_two_do_not_toggle_zoom_in_popup_mode() {
        let mut app = App::new(mock_source(), false);
        app.enter_actions_mode();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('1')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.pane_zoom(), PaneZoom::None);
    }

    #[test]
    fn one_and_two_do_not_toggle_zoom_in_comment_input_mode() {
        let mut app = App::new(mock_source(), false);
        app.enter_comments_mode();
        app.start_comment_input();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('2')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.pane_zoom(), PaneZoom::None);
    }

    #[test]
    fn one_and_two_do_not_toggle_zoom_in_edit_input_mode() {
        let mut app = App::new(mock_source(), false);
        app.start_summary_edit_input();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();
        let mut edit_session = None;

        let outcome = handle_key_event_with_edit_session(
            &mut app,
            &mut edit_session,
            key(KeyCode::Char('2')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.pane_zoom(), PaneZoom::None);
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
    fn lowercase_j_and_k_move_issue_selection_when_detail_pane_is_zoomed() {
        let mut app = App::new(mock_source(), false);
        let (detail_tx, _) = mpsc::channel();
        app.maybe_request_detail(&detail_tx);
        app.set_detail_viewport_height(4);
        app.toggle_zoom_detail();
        let (add_tx, _) = mpsc::channel();
        let (transition_tx, _) = mpsc::channel();
        let (edit_tx, _) = mpsc::channel();

        let initial_selected = app.selected;
        let initial_scroll = app.detail_scroll();

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('j')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.selected, initial_selected + 1);
        assert_eq!(app.detail_scroll(), initial_scroll);

        let outcome = handle_key_event(
            &mut app,
            key(KeyCode::Char('k')),
            &add_tx,
            &transition_tx,
            &edit_tx,
        );
        assert_eq!(outcome, None);
        assert_eq!(app.selected, initial_selected);
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
    fn mouse_scroll_on_detail_pane_in_vertical_layout_scrolls_detail_only() {
        let mut app = App::new(mock_source(), false);
        let (detail_tx, _) = mpsc::channel();
        app.maybe_request_detail(&detail_tx);
        app.set_detail_viewport_height(4);
        app.toggle_pane_orientation();
        let hit_areas = MouseHitAreas {
            issues: Some(Rect::new(0, 0, 40, 20)),
            detail: Some(Rect::new(40, 0, 40, 20)),
            popup: None,
        };

        let initial_selected = app.selected;
        let initial_scroll = app.detail_scroll();

        handle_mouse_event(
            &mut app,
            mouse_scroll(MouseEventKind::ScrollDown, 60, 2),
            hit_areas,
        );

        assert_eq!(app.selected, initial_selected);
        assert!(app.detail_scroll() > initial_scroll);
    }

    #[test]
    fn mouse_scroll_on_issues_pane_moves_issue_selection() {
        let mut app = App::new(mock_source(), false);
        let hit_areas = MouseHitAreas {
            issues: Some(Rect::new(0, 0, 40, 20)),
            detail: Some(Rect::new(40, 0, 40, 20)),
            popup: None,
        };
        let initial_selected = app.selected;

        handle_mouse_event(
            &mut app,
            mouse_scroll(MouseEventKind::ScrollDown, 10, 2),
            hit_areas,
        );

        assert_eq!(app.selected, initial_selected + 1);
    }

    #[test]
    fn mouse_click_on_issue_row_moves_selection_to_clicked_row() {
        let mut app = App::new(mock_source(), false);
        let hit_areas = MouseHitAreas {
            issues: Some(Rect::new(0, 0, 60, 20)),
            detail: Some(Rect::new(60, 0, 40, 20)),
            popup: None,
        };

        handle_mouse_event(&mut app, mouse_click(10, 4), hit_areas);
        assert_eq!(app.selected, 2);
        assert_eq!(app.selected_issue_key().as_deref(), Some("JAY-103"));
    }

    #[test]
    fn mouse_click_on_issue_header_does_not_move_selection() {
        let mut app = App::new(mock_source(), false);
        let hit_areas = MouseHitAreas {
            issues: Some(Rect::new(0, 0, 60, 20)),
            detail: Some(Rect::new(60, 0, 40, 20)),
            popup: None,
        };
        let initial = app.selected;

        handle_mouse_event(&mut app, mouse_click(10, 1), hit_areas);
        assert_eq!(app.selected, initial);
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
    fn mouse_scroll_in_edit_menu_moves_selection() {
        let mut app = App::new(mock_source(), false);
        app.enter_edit_menu_mode();
        let hit_areas = MouseHitAreas {
            issues: Some(Rect::new(0, 0, 40, 20)),
            detail: Some(Rect::new(40, 0, 40, 20)),
            popup: Some(Rect::new(20, 5, 40, 10)),
        };

        handle_mouse_event(
            &mut app,
            mouse_scroll(MouseEventKind::ScrollDown, 25, 8),
            hit_areas,
        );
        assert!(app.edit_menu_text().contains("> Description"));

        handle_mouse_event(
            &mut app,
            mouse_scroll(MouseEventKind::ScrollUp, 25, 8),
            hit_areas,
        );
        assert!(app.edit_menu_text().contains("> Summary"));
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
    fn build_edit_textarea_normalizes_carriage_returns() {
        let textarea = build_edit_textarea("alpha\r\nbeta\rgamma");
        let lines = textarea.lines();
        assert_eq!(lines[0], "alpha");
        assert_eq!(lines[1], "beta");
        assert_eq!(lines[2], "gamma");
    }

    #[test]
    fn edit_input_overlay_hides_popup_copy_and_keeps_panes_visible() {
        let backend = TestBackend::new(120, 40);
        let mut terminal = Terminal::new(backend).expect("terminal");
        let mut app = App::new(mock_source(), false);
        app.enter_edit_menu_mode();
        app.start_description_edit_input();
        let edit_session = EditInputSession {
            textarea: build_edit_textarea(app.edit_input()),
        };

        terminal
            .draw(|frame| {
                let _ = draw_ui(frame, &mut app, Some(&edit_session));
            })
            .expect("draw edit overlay");

        let buffer = terminal.backend().buffer();
        assert!(buffer_contains_text(buffer, "Issues (mock) (1)"));
        assert!(buffer_contains_text(buffer, "Edit description"));
        assert!(!buffer_contains_text(buffer, "Edit Issue Fields"));
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
