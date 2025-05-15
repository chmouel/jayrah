import subprocess

from textual import log, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import DataTable, Footer, Header, Label

from jayrah import defaults, utils


class IssueDetailPanel(Vertical):
    """Panel showing detailed information about the selected issue."""

    def __init__(self, ticket: str | None = None, config: dict | None = None):
        super().__init__()
        self.ticket = ticket
        self.config = config or {}

    def compose(self) -> ComposeResult:  # type: ignore[override]
        # Single label for all states
        text = (
            f"Loading issue {self.ticket}…"
            if self.ticket
            else "Select an issue to view details"
        )
        yield Label(text, id="detail-label")

    def update_issue(self, ticket: str | None, config: dict | None) -> None:
        """Refresh the panel by updating the existing label's text."""
        self.ticket = ticket
        self.config = config or {}

        # Retrieve the single label
        label = self.query_one("#detail-label", Label)

        # Update based on presence of ticket
        if not ticket:
            label.update("Select an issue to view details")
        else:
            label.update(f"Issue {ticket} selected.")


class IssueBrowserApp(App):
    """A **Textual** app for browsing Jira issues via *jayrah*."""

    ### ─────────────────────────  Style  ──────────────────────────
    CSS = """
    /* Main layout */
    #main-panel {
        height: 60%;
        width: 100%;
    }
    #bottom-panel {
        height: 40%;
        width: 100%;
        border-top: solid $primary;
        padding: 1;
    }

    /* Header styling */
    #title {
        background: $accent;
        color: $text;
        padding: 1;
        width: 100%;
        text-align: center;
    }

    /* Issue table styling */
    #issues-table {
        height: 100%;
        border: solid $primary;
    }
    #issues-table .datatable--header-cell-Type    { width: 5;  }
    #issues-table .datatable--header-cell-Key     { width: 12; }
    #issues-table .datatable--header-cell-Summary { width: 40%;}
    #issues-table .datatable--header-cell-Assignee{ width: 15; }
    #issues-table .datatable--header-cell-Reporter{ width: 15; }
    #issues-table .datatable--header-cell-Created { width: 10; }
    #issues-table .datatable--header-cell-Updated { width: 10; }
    #issues-table .datatable--header-cell-Status  { width: 10; }

    /* Issue detail panel */
    #detail-label {
        padding: 1;
        height: 100%;
        width: 100%;
        overflow: auto;
    }
    #no-selection {
        padding: 1;
        color: $text-muted;
        text-align: center;
    }
    """

    ### ─────────────────────────  Key bindings  ──────────────────────────
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "reload", "Reload"),
        Binding("o", "open_issue", "Open in Browser"),
        Binding("a", "action_menu", "Actions"),
        Binding("f", "filter", "Filter"),
        Binding("h", "help", "Help"),
    ]

    ### ─────────────────────────  Lifecycle  ──────────────────────────
    def __init__(
        self,
        issues: list | None = None,
        config: dict | None = None,
        command: str | None = None,
    ):
        super().__init__()
        self.issues = issues or []
        self.config = config or {}
        self.command = command or ""
        self.selected_issue: str | None = None

    def compose(self) -> ComposeResult:  # type: ignore[override]
        """Create the widget tree."""
        yield Header(show_clock=True)
        with Container():
            with Vertical():
                yield Label("🔍 Jayrah – Jira Issues", id="title")
                # Main content area
                with Vertical(id="main-panel"):
                    yield self._create_datatable()
                # Detail panel at the bottom
                with Vertical(id="bottom-panel"):
                    yield IssueDetailPanel(config=self.config)
        yield Footer()

    ### ─────────────────────────  Helpers  ──────────────────────────
    def _create_datatable(self) -> DataTable:
        table = DataTable(id="issues-table")
        table.cursor_type = "row"  # Highlights whole rows

        table.add_columns(
            "Type",
            "Key",
            "Summary",
            "Assignee",
            "Reporter",
            "Created",
            "Updated",
            "Status",
        )

        for issue in self.issues:
            issue_type = issue["fields"]["issuetype"]["name"]
            issue_type = defaults.ISSUE_TYPE_EMOJIS.get(issue_type, (issue_type[:4],))[
                0
            ]

            key = issue["key"]

            summary = issue["fields"]["summary"]
            if len(summary) > defaults.SUMMARY_MAX_LENGTH:
                summary = f"{summary[: defaults.SUMMARY_MAX_LENGTH - 1]}…"

            assignee = "None"
            if assignee_field := issue["fields"].get("assignee"):
                assignee = utils.parse_email(assignee_field)

            reporter = utils.parse_email(issue["fields"].get("reporter", ""))
            created = utils.show_time(issue["fields"].get("created", ""))
            updated = utils.show_time(issue["fields"].get("updated", ""))
            status = issue["fields"]["status"]["name"]

            table.add_row(
                issue_type, key, summary, assignee, reporter, created, updated, status
            )
        return table

    def on_mount(self) -> None:  # noqa: D401 – Textual lifecycle method
        self.title = "Jayrah – Jira Issues"

    ### ─────────────────────────  Events  ──────────────────────────
    @on(DataTable.RowHighlighted)
    def _handle_row_highlighted(self, event: DataTable.RowHighlighted) -> None:  # type: ignore[name-defined]
        """Update the detail pane whenever the cursor highlights a new row."""
        table: DataTable = self.query_one("#issues-table")
        row = table.get_row(event.row_key)
        issue_key = str(row[1]) if row and len(row) > 1 else None

        # Log inside the Textual log (visible with `textual run --dev`)

        if issue_key and issue_key != self.selected_issue:
            log(f"Row highlighted → {issue_key}")
            self.selected_issue = issue_key
            self.query_one(IssueDetailPanel).update_issue(issue_key, self.config)

    ### ─────────────────────────  Actions  ──────────────────────────
    def action_action_menu(self) -> None:  # noqa: D401
        if not self.selected_issue:
            self.notify("No issue selected", severity="error")
            return
        self.notify("Starting action menu…")
        self.exit()  # Switch back to shell for the action menu
        subprocess.run(
            [self.config.get("jayrah_path"), "issue", "action", self.selected_issue]
        )

    def action_reload(self) -> None:  # noqa: D401
        self.notify("Reloading issues…")
        # Placeholder for real refresh logic

    def action_help(self) -> None:  # noqa: D401
        self.notify("Showing help…")

    def action_filter(self) -> None:  # noqa: D401
        self.notify("Filter functionality coming soon…")

    def action_open_issue(self) -> None:  # noqa: D401
        if not self.selected_issue:
            self.notify("No issue selected", severity="error")
            return
        try:
            utils.browser_open_ticket(self.selected_issue, self.config)
            self.notify(f"Opening {self.selected_issue} in browser")
            self.exit()
        except Exception as exc:
            self.notify(f"Error opening issue: {exc}", severity="error")

    def action_quit(self) -> None:  # noqa: D401
        self.exit()  # *app.selected_issue* persists after exit


### ─────────────────────────  Public helper  ──────────────────────────
def run_textual_browser(issues: list, config: dict, command: str):
    """Launch the **IssueBrowserApp** and return the ticket selected by the user."""
    app = IssueBrowserApp(issues, config, command)
    app.run()
    return app.selected_issue
