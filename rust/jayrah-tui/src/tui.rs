use std::{io, time::Duration};

use anyhow::Result;
use crossterm::event::{self, Event, KeyCode, KeyEvent, KeyEventKind, KeyModifiers};
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout},
    style::{Modifier, Style},
    widgets::{Block, Borders, Cell, Paragraph, Row, Table, TableState, Wrap},
    Frame, Terminal,
};

use crate::{
    app::App,
    worker::{start_comment_worker, start_detail_worker},
};

#[derive(Debug, PartialEq, Eq)]
pub enum RunOutcome {
    Quit,
    Chosen(Option<String>),
}

pub fn run_app(
    terminal: &mut Terminal<CrosstermBackend<io::Stdout>>,
    mut app: App,
) -> Result<RunOutcome> {
    let (detail_request_tx, detail_result_rx) = start_detail_worker();
    let (comment_request_tx, comment_result_rx) = start_comment_worker();

    loop {
        while let Ok(message) = detail_result_rx.try_recv() {
            app.ingest_detail_result(message);
        }
        while let Ok(message) = comment_result_rx.try_recv() {
            app.ingest_comment_result(message);
        }

        app.maybe_request_detail(&detail_request_tx);
        app.maybe_request_comments(&comment_request_tx);
        terminal.draw(|frame| draw_ui(frame, &app))?;

        if event::poll(Duration::from_millis(100))? {
            let Event::Key(key) = event::read()? else {
                continue;
            };

            if key.kind != KeyEventKind::Press {
                continue;
            }

            if let Some(outcome) = handle_key_event(&mut app, key) {
                return Ok(outcome);
            }
        }
    }
}

fn handle_key_event(app: &mut App, key: KeyEvent) -> Option<RunOutcome> {
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

    if app.in_comments_mode() {
        match key.code {
            KeyCode::Char('q') | KeyCode::Esc | KeyCode::Char('c') => app.enter_detail_mode(),
            KeyCode::Char('j') | KeyCode::Down => app.next(),
            KeyCode::Char('k') | KeyCode::Up => app.prev(),
            KeyCode::Char('n') => app.next_comment(),
            KeyCode::Char('p') => app.prev_comment(),
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

    match key.code {
        KeyCode::Char('q') | KeyCode::Esc => return Some(RunOutcome::Quit),
        KeyCode::Char('j') | KeyCode::Down => app.next(),
        KeyCode::Char('k') | KeyCode::Up => app.prev(),
        KeyCode::Char('c') => app.enter_comments_mode(),
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

fn draw_ui(frame: &mut Frame, app: &App) {
    let vertical = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Min(0), Constraint::Length(1)])
        .split(frame.area());

    let main_chunks = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(60), Constraint::Percentage(40)])
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

    let detail = Paragraph::new(app.right_pane_text())
        .block(
            Block::default()
                .title(app.right_pane_title())
                .borders(Borders::ALL),
        )
        .wrap(Wrap { trim: false });
    frame.render_widget(detail, main_chunks[1]);

    let mode = if app.filter_mode {
        "FILTER"
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
    } else if app.in_comments_mode() {
        format!(
            "[{}] j/k move issues | n/p move comments | c close | r reload | o open | {}",
            mode, app.status_line
        )
    } else if app.choose_mode {
        format!(
            "[{}] j/k move | Enter choose | c comments | f filter | o open | q quit | {}",
            mode, app.status_line
        )
    } else {
        format!(
            "[{}] j/k move | c comments | f filter | r reload | o open | q quit | {}",
            mode, app.status_line
        )
    };
    frame.render_widget(Paragraph::new(footer), vertical[1]);
}

#[cfg(test)]
mod tests {
    use crossterm::event::KeyEventState;
    use crossterm::event::{KeyCode, KeyEvent, KeyEventKind, KeyModifiers};

    use super::{handle_key_event, RunOutcome};
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

    #[test]
    fn enter_returns_selected_key_in_choose_mode() {
        let mut app = App::new(mock_source(), true);

        let outcome = handle_key_event(&mut app, key(KeyCode::Enter));
        assert_eq!(
            outcome,
            Some(RunOutcome::Chosen(Some("JAY-101".to_string())))
        );
    }

    #[test]
    fn enter_opens_issue_outside_choose_mode() {
        let mut app = App::new(mock_source(), false);

        let outcome = handle_key_event(&mut app, key(KeyCode::Enter));
        assert_eq!(outcome, None);
        assert!(app
            .status_line
            .contains("Open disabled while using mock data"));
    }

    #[test]
    fn q_closes_comments_mode_before_quit() {
        let mut app = App::new(mock_source(), false);
        app.enter_comments_mode();

        let outcome = handle_key_event(&mut app, key(KeyCode::Char('q')));

        assert_eq!(outcome, None);
        assert!(!app.in_comments_mode());
    }
}
