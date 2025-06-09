"""Main issue browser application combining all components."""

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import DataTable, Footer, Header

from .actions import IssueBrowserActions
from .base import JayrahAppMixin
from .helpers import filter_issues_by_text, get_row_data_for_issue
from .views import IssueDetailPanel


class IssueBrowserApp(App, JayrahAppMixin, IssueBrowserActions):
    """A **Textual** app for browsing Jira issues via *jayrah*."""

    ### ─────────────────────────  Style  ──────────────────────────
    CSS = """
    /* Main layout */
    #main-panel {
        height: 30%;
        width: 100%;
    }
    #bottom-panel {
        height: 70%;
        width: 100%;
        border-top: solid $primary;
        padding: 1;
    }

    /* Issue table styling */
    #issues-table {
        height: 100%;
        border: solid $primary;
    }
    #issues-table .datatable--header-cell-Type    { width: 2;  }
    #issues-table .datatable--header-cell-Ticket     { width: 12; }
    #issues-table .datatable--header-cell-Summary { width: 40%;}
    #issues-table .datatable--header-cell-Assignee{ width: 15; }
    #issues-table .datatable--header-cell-Reporter{ width: 15; }
    #issues-table .datatable--header-cell-Created { width: 10; }
    #issues-table .datatable--header-cell-Updated { width: 10; }
    #issues-table .datatable--header-cell-Status  { width: 10; }

    #issues-table {
        overflow-y: hidden;
        overflow-x: auto;
    }

    /* Issue detail panel */
    #detail-label {
        padding: 0;
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
        Binding("escape", "quit", "Quit", show=False),
        Binding("o", "open_issue", "Open"),
        Binding("r", "reload", "Reload"),
        Binding("a", "show_actions", "Actions"),
        Binding("c", "view_comments", "Comments"),
        Binding("l", "add_labels", "Labels", show=False),
        Binding("C", "edit_components", "Components", show=False),
        Binding("t", "transition_issue", "Transition", show=False),
        Binding("e", "edit_issue", "Edit", show=False),
        Binding("f", "filter", "Fuzzy Filter", show=False),
        Binding("b", "change_board", "Boards", show=False),
        Binding("j", "cursor_down", "Down"),
        Binding("k", "cursor_up", "Up"),
        Binding("J", "scroll_down", "PrevDown"),
        Binding("K", "scroll_up", "PrevUp"),
        Binding("q", "quit", "Quit"),
        Binding("f1", "command_palette", "Palette", show=False),
        Binding("?", "help", "Help"),
    ]

    ### ─────────────────────────  Lifecycle  ──────────────────────────
    def __init__(
        self,
        issues: list | None = None,
        config: dict | None = None,
        command: str | None = None,
        jql: str | None = None,
        order_by: str | None = None,
    ):
        # Initialize mixins first
        JayrahAppMixin.__init__(self, config)
        App.__init__(self)

        self.issues = issues or []
        self.command = command or ""
        self.selected_issue: str | None = None
        self.jql = jql
        self.order_by: str | None = order_by

        if not self.config.get("no_cache"):
            self.jayrah_obj.jira.cache.preload_cache()
            if self.verbose:
                self.log("Preloaded Jira cache into memory for fast access.")

    def compose(self) -> ComposeResult:  # type: ignore[override]
        """Create the widget tree."""
        yield Header(show_clock=True)
        with Container():
            with Vertical():
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
            "",
            "Ticket",
            "Summary",
            "Status",
            "Assignee",
            "Reporter",
            "Created",
            "Updated",
        )

        for issue in self.issues:
            row_data = get_row_data_for_issue(issue)
            table.add_row(*row_data)
        return table

    def on_mount(self) -> None:  # noqa: D401 – Textual lifecycle method
        self.title = "Jayrah – Your friendly Jira browser"

    ### ─────────────────────────  Events  ──────────────────────────
    @on(DataTable.RowHighlighted)
    def _handle_row_highlighted(self, event: DataTable.RowHighlighted) -> None:  # type: ignore[name-defined]
        """Update the detail pane whenever the cursor highlights a new row."""
        if not self.issues:
            return

        table = self.query_one("#issues-table", DataTable)
        if event.row_key is None:
            return

        try:
            row = table.get_row(event.row_key)
            issue_key = str(row[1]) if row and len(row) > 1 else None

            if issue_key and issue_key != self.selected_issue:
                self.log(f"Row highlighted → {issue_key}")
                self.selected_issue = issue_key
                self.query_one(IssueDetailPanel).update_issue(issue_key, self.config)
        except Exception as e:
            self.log(f"Error handling row highlight: {e}")

    def apply_fuzzy_filter(
        self, text: str = "", msg: str = "Showing all issues"
    ) -> None:
        """Apply a fuzzy filter to all visible fields in the issues table."""
        table = self.query_one("#issues-table", DataTable)

        # Add the headers if they don't exist
        if not table.columns:
            table.add_columns(
                "",
                "Ticket",
                "Summary",
                "Status",
                "Assignee",
                "Reporter",
                "Created",
                "Updated",
            )

        # Get current visible rows
        current_rows = {}
        for row_key in table.rows:
            row = table.get_row(row_key)
            if row and len(row) > 1:
                current_rows[row_key] = row  # Use DataTable's row_key

        # Filter issues using helper function
        filtered_issues = filter_issues_by_text(self.issues, text)

        # Update UI with filter information
        if filtered_issues:
            txt_message = f"Found {len(filtered_issues)} issues"
            if text.strip():
                txt_message += f" matching '{text}'"
            self.notify(txt_message)
        else:
            self.notify(f"No issues match '{text}'", severity="warning")

        # Create a set of filtered issue keys for quick lookup
        filtered_keys = {issue["key"] for issue in filtered_issues}

        # Remove rows that are no longer in the filtered set
        for row_key in list(current_rows.keys()):
            if row_key not in filtered_keys:
                table.remove_row(row_key)

        # Add or update rows for filtered issues
        for issue in filtered_issues:
            key = issue["key"]
            row_data = get_row_data_for_issue(issue)

            if key in current_rows:
                # Update existing row if data has changed
                current_row = current_rows[key]
                if current_row != row_data:
                    table.remove_row(key)
                    table.add_row(*row_data, key=key)
            else:
                # Add new row
                table.add_row(*row_data, key=key)

        # Clear the selected issue if it doesn't exist in the filtered results
        if self.selected_issue and self.selected_issue not in filtered_keys:
            self.selected_issue = None
            detail_panel = self.query_one(IssueDetailPanel)
            detail_panel.update_issue(None, self.config)


### ─────────────────────────  Public helper  ──────────────────────────
def run_textual_browser(
    issues: list, config: dict, command: str, jql: str, order_by: str
):
    """Launch the **IssueBrowserApp** and return the ticket selected by the user."""
    app = IssueBrowserApp(issues, config, command, jql, order_by)
    app.run()
    return app.selected_issue
