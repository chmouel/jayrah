use std::{
    collections::HashMap,
    env, io,
    process::Command,
    sync::mpsc::{self, Receiver, Sender},
    thread,
    time::{Duration, Instant},
};

use anyhow::{anyhow, bail, Result};
use crossterm::{
    event::{self, Event, KeyCode, KeyEvent, KeyEventKind, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout},
    style::{Modifier, Style},
    widgets::{Block, Borders, Cell, Paragraph, Row, Table, TableState, Wrap},
    Frame, Terminal,
};
use serde::Deserialize;

const DETAIL_FETCH_DEBOUNCE_MS: u64 = 120;

#[derive(Clone, Debug)]
struct Issue {
    key: String,
    summary: String,
    status: String,
    assignee: String,
}

#[derive(Clone, Debug)]
struct IssueDetail {
    key: String,
    summary: String,
    status: String,
    priority: String,
    issue_type: String,
    assignee: String,
    reporter: String,
    created: String,
    updated: String,
    labels: Vec<String>,
    components: Vec<String>,
    fix_versions: Vec<String>,
    description: String,
}

#[derive(Clone, Debug)]
struct AdapterSource {
    board: Option<String>,
    query: Option<String>,
    mock_only: bool,
}

impl AdapterSource {
    fn from_args() -> Result<Self> {
        let mut board = None;
        let mut query = None;
        let mut mock_only = false;

        let mut args = env::args().skip(1);
        while let Some(arg) = args.next() {
            match arg.as_str() {
                "--board" => {
                    board = Some(
                        args.next()
                            .ok_or_else(|| anyhow!("--board requires a value"))?,
                    );
                }
                "--query" | "-q" => {
                    query = Some(
                        args.next()
                            .ok_or_else(|| anyhow!("--query requires a value"))?,
                    );
                }
                "--mock" => {
                    mock_only = true;
                }
                "--help" | "-h" => {
                    print_help();
                    std::process::exit(0);
                }
                other => return Err(anyhow!("Unknown argument: {other}")),
            }
        }

        if board.is_some() && query.is_some() {
            return Err(anyhow!("Use either --board or --query, not both"));
        }

        // If nothing is provided, use the legacy default board name.
        if !mock_only && board.is_none() && query.is_none() {
            board = Some("myissue".to_string());
        }

        Ok(Self {
            board,
            query,
            mock_only,
        })
    }

    fn describe(&self) -> String {
        if self.mock_only {
            return "mock-only".to_string();
        }

        if let Some(query) = &self.query {
            return format!("query={query}");
        }

        if let Some(board) = &self.board {
            return format!("board={board}");
        }

        "board=myissue".to_string()
    }
}

#[derive(Debug)]
struct App {
    issues: Vec<Issue>,
    selected: usize,
    filter_mode: bool,
    filter_input: String,
    reload_count: usize,
    status_line: String,
    source: AdapterSource,
    using_adapter: bool,
    detail_cache: HashMap<String, IssueDetail>,
    detail_errors: HashMap<String, String>,
    detail_loading_key: Option<String>,
    last_selected_key: Option<String>,
    selected_changed_at: Instant,
}

impl App {
    fn new(source: AdapterSource) -> Self {
        let mut app = Self {
            issues: Vec::new(),
            selected: 0,
            filter_mode: false,
            filter_input: String::new(),
            reload_count: 0,
            status_line: String::new(),
            source,
            using_adapter: false,
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

    fn visible_indices(&self) -> Vec<usize> {
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

    fn normalize_selection(&mut self) {
        let len = self.visible_indices().len();
        if len == 0 {
            self.selected = 0;
            return;
        }

        if self.selected >= len {
            self.selected = len - 1;
        }
    }

    fn next(&mut self) {
        let len = self.visible_indices().len();
        if len == 0 {
            return;
        }
        self.selected = (self.selected + 1) % len;
    }

    fn prev(&mut self) {
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

    fn selected_issue(&self) -> Option<&Issue> {
        let visible = self.visible_indices();
        let issue_index = visible.get(self.selected)?;
        self.issues.get(*issue_index)
    }

    fn selected_issue_key(&self) -> Option<String> {
        self.selected_issue().map(|issue| issue.key.clone())
    }

    fn reload_issues(&mut self) {
        self.reload_count += 1;
        self.detail_cache.clear();
        self.detail_errors.clear();
        self.detail_loading_key = None;

        if self.source.mock_only {
            self.issues = mock_issues(self.reload_count);
            self.using_adapter = false;
            self.status_line = format!("Reloaded mock issues ({})", self.reload_count);
            self.normalize_selection();
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

        self.normalize_selection();
        self.sync_selected_tracking();
    }

    fn sync_selected_tracking(&mut self) {
        let current = self.selected_issue_key();
        if current != self.last_selected_key {
            self.last_selected_key = current;
            self.selected_changed_at = Instant::now();
        }
    }

    fn maybe_request_detail(&mut self, request_tx: &Sender<DetailRequest>) {
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

    fn ingest_detail_result(&mut self, message: DetailResult) {
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

    fn detail_text_for_selected(&self) -> String {
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

    fn open_selected_issue(&mut self) {
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

#[derive(Debug)]
struct DetailRequest {
    key: String,
}

#[derive(Debug)]
struct DetailResult {
    key: String,
    result: std::result::Result<IssueDetail, String>,
}

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

fn load_issues_from_adapter(source: &AdapterSource) -> Result<Vec<Issue>> {
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

    let payload: BrowseListPayload = serde_json::from_slice(&output.stdout)?;

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

fn load_issue_detail_from_adapter(key: &str) -> Result<IssueDetail> {
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

    let payload: IssueShowPayload = serde_json::from_slice(&output.stdout)?;
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

fn open_issue_in_browser(key: &str) -> Result<()> {
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

fn compact_error(value: &str) -> String {
    const LIMIT: usize = 60;
    let cleaned = value.replace('\n', " ");
    if cleaned.len() <= LIMIT {
        return cleaned;
    }
    format!("{}...", &cleaned[..LIMIT])
}

fn join_or_dash(values: &[String]) -> String {
    if values.is_empty() {
        return "-".to_string();
    }
    values.join(", ")
}

fn mock_issues(reload_count: usize) -> Vec<Issue> {
    let suffix = if reload_count == 0 {
        String::new()
    } else {
        format!(" [reload {}]", reload_count)
    };

    vec![
        Issue {
            key: "JAY-101".to_string(),
            summary: format!("Build ratatui scaffold{}", suffix),
            status: "In Progress".to_string(),
            assignee: "alice".to_string(),
        },
        Issue {
            key: "JAY-102".to_string(),
            summary: format!("Add adapter JSON contract{}", suffix),
            status: "To Do".to_string(),
            assignee: "bob".to_string(),
        },
        Issue {
            key: "JAY-103".to_string(),
            summary: format!("Wire issue detail pane{}", suffix),
            status: "Blocked".to_string(),
            assignee: "carol".to_string(),
        },
        Issue {
            key: "JAY-104".to_string(),
            summary: format!("Measure navigation latency{}", suffix),
            status: "Review".to_string(),
            assignee: "dave".to_string(),
        },
    ]
}

fn mock_detail_from_issue(issue: &Issue) -> IssueDetail {
    IssueDetail {
        key: issue.key.clone(),
        summary: issue.summary.clone(),
        status: issue.status.clone(),
        priority: "Mock".to_string(),
        issue_type: "Task".to_string(),
        assignee: issue.assignee.clone(),
        reporter: "mock-reporter".to_string(),
        created: "2026-02-20T00:00:00Z".to_string(),
        updated: "2026-02-20T00:00:00Z".to_string(),
        labels: vec!["mock".to_string()],
        components: vec!["tui".to_string()],
        fix_versions: Vec::new(),
        description: "Mock detail payload used while adapter data is unavailable.".to_string(),
    }
}

fn setup_terminal() -> Result<Terminal<CrosstermBackend<io::Stdout>>> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let terminal = Terminal::new(backend)?;
    Ok(terminal)
}

fn restore_terminal(terminal: &mut Terminal<CrosstermBackend<io::Stdout>>) -> Result<()> {
    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    terminal.show_cursor()?;
    Ok(())
}

fn run_app(terminal: &mut Terminal<CrosstermBackend<io::Stdout>>, mut app: App) -> Result<()> {
    let (detail_request_tx, detail_result_rx) = start_detail_worker();

    loop {
        while let Ok(message) = detail_result_rx.try_recv() {
            app.ingest_detail_result(message);
        }

        app.maybe_request_detail(&detail_request_tx);
        terminal.draw(|frame| draw_ui(frame, &app))?;

        if event::poll(Duration::from_millis(100))? {
            let Event::Key(key) = event::read()? else {
                continue;
            };

            if key.kind != KeyEventKind::Press {
                continue;
            }

            if handle_key_event(&mut app, key) {
                break;
            }
        }
    }

    Ok(())
}

fn start_detail_worker() -> (Sender<DetailRequest>, Receiver<DetailResult>) {
    let (request_tx, request_rx) = mpsc::channel::<DetailRequest>();
    let (result_tx, result_rx) = mpsc::channel::<DetailResult>();

    thread::spawn(move || {
        while let Ok(request) = request_rx.recv() {
            let result =
                load_issue_detail_from_adapter(&request.key).map_err(|error| error.to_string());

            if result_tx
                .send(DetailResult {
                    key: request.key,
                    result,
                })
                .is_err()
            {
                break;
            }
        }
    });

    (request_tx, result_rx)
}

fn handle_key_event(app: &mut App, key: KeyEvent) -> bool {
    if app.filter_mode {
        match key.code {
            KeyCode::Esc | KeyCode::Enter => {
                app.filter_mode = false;
                app.normalize_selection();
                app.status_line = format!("Filter applied: '{}'", app.filter_input);
            }
            KeyCode::Backspace => {
                app.filter_input.pop();
                app.normalize_selection();
            }
            KeyCode::Char(c) => {
                if !key.modifiers.contains(KeyModifiers::CONTROL) {
                    app.filter_input.push(c);
                    app.normalize_selection();
                }
            }
            _ => {}
        }
        return false;
    }

    match key.code {
        KeyCode::Char('q') | KeyCode::Esc => return true,
        KeyCode::Char('j') | KeyCode::Down => app.next(),
        KeyCode::Char('k') | KeyCode::Up => app.prev(),
        KeyCode::Char('r') => app.reload_issues(),
        KeyCode::Char('f') | KeyCode::Char('/') => {
            app.filter_mode = true;
            app.status_line = String::from("Filter mode: type to filter, Enter to apply");
        }
        KeyCode::Char('o') | KeyCode::Enter => app.open_selected_issue(),
        _ => {}
    }

    false
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

    let detail = Paragraph::new(app.detail_text_for_selected())
        .block(Block::default().title("Detail").borders(Borders::ALL))
        .wrap(Wrap { trim: false });
    frame.render_widget(detail, main_chunks[1]);

    let mode = if app.filter_mode { "FILTER" } else { "NORMAL" };
    let footer = if app.filter_mode {
        format!(
            "[{}] filter: {}  | Enter/Esc apply  Backspace delete",
            mode, app.filter_input
        )
    } else {
        format!(
            "[{}] j/k or arrows move | f filter | r reload | o open | q quit | {}",
            mode, app.status_line
        )
    };
    frame.render_widget(Paragraph::new(footer), vertical[1]);
}

fn print_help() {
    println!("jayrah-tui (phase 1 preview)");
    println!("Usage:");
    println!("  cargo run -p jayrah-tui -- [--board <name>] [--query <jql>] [--mock]");
    println!("Options:");
    println!("  --board <name>   Load issues from a configured board");
    println!("  --query <jql>    Load issues from a raw JQL query");
    println!("  --mock           Skip adapter calls and use built-in mock issues");
}

fn main() -> Result<()> {
    let source = AdapterSource::from_args()?;

    let mut terminal = setup_terminal()?;
    let run_result = run_app(&mut terminal, App::new(source));
    let restore_result = restore_terminal(&mut terminal);

    if let Err(error) = restore_result {
        return Err(error);
    }
    run_result
}
