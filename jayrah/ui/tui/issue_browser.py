from jayrah import utils
from jayrah.commands import issue_view
from jayrah.utils import defaults
from textual import log, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Label, Markdown

from .. import boards


class IssueDetailPanel(Vertical):
    """Panel showing detailed information about the selected issue using Markdown."""

    DEFAULT_CSS = """
    IssueDetailPanel {
        width: 1fr;
        height: 1fr;
        overflow: hidden;
    }

    #detail-header {
        width: 100%;
        height: 100%; /* Markdown widget takes full space of its parent */
        overflow: auto; /* Allow Markdown widget to scroll its content */
    }
    #detail-markdown {
        width: 100%;
        height: 100%; /* Markdown widget takes full space of its parent */
        overflow: auto; /* Allow Markdown widget to scroll its content */
    }
    """

    def __init__(self, ticket: str | None = None, config: dict | None = None):
        super().__init__()
        self.ticket = ticket
        self.config = config or {}
        self.ticket_cache: dict = {}
        self.jayrah_obj = boards.Boards(self.config)

    def compose(self) -> ComposeResult:  # type: ignore[override]
        """Compose the widget with a Markdown display area."""
        initial_message = (
            f"Loading issue {self.ticket}…"
            if self.ticket
            else "Select an issue to view details"
        )
        with Container():
            with Vertical(id="detail-label"):
                yield Markdown(initial_message, id="detail-markdown")

    def update_issue(self, ticket: str | None, config: dict | None) -> None:
        """
        Refresh the panel by updating the Markdown widget's content.
        Fetches issue details and uses issue_view.build_issue to generate Markdown.
        """
        self.ticket = ticket
        if config is not None:  # Update config only if a new one is provided
            self.config = config

        # header_widget = self.query_one("#detail-header", Static)
        markdown_widget = self.query_one("#detail-markdown", Markdown)

        if not ticket:
            markdown_widget.update("Select an issue to view details")
            return

        try:
            # Display a loading message while fetching data
            markdown_widget.update(f"🔄 Loading details for {ticket}...")
            self.app.refresh()

            all_content = ""
            if ticket not in self.ticket_cache:
                issue_data = self.jayrah_obj.jira.get_issue(ticket, fields=None)
                header_content, markdown_content = issue_view.build_issue(
                    issue_data, self.config, 0
                )
                all_content = header_content + "\n" + markdown_content
                self.ticket_cache[ticket] = all_content
            else:
                all_content = self.ticket_cache.get(ticket, "")

            markdown_widget.update(all_content)
            markdown_widget.scroll_home(animate=False, immediate=True)
        except Exception as e:
            error_message = f"⚠️ Error loading issue {ticket}:\n\n```\n{str(e)}\n```\n\nPlease check the ticket ID and your connection."
            markdown_widget.update(error_message)
            markdown_widget.scroll_home()
            self.app.log.error(f"Failed to load or build issue {ticket}: {e}")

    async def on_mount(self) -> None:
        """Load initial ticket details if a ticket was provided during initialization."""
        if self.ticket:
            # If update_issue involves blocking I/O, consider running it in a worker thread:
            # self.run_worker(lambda: self.update_issue(self.ticket, self.config), exclusive=True)
            # For simplicity, calling directly. If update_issue is async, await it.
            self.update_issue(self.ticket, self.config)


class IssueBrowserApp(App):
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
        Binding("q", "quit", "Quit"),
        Binding("r", "reload", "Reload"),
        Binding("o", "open_issue", "Open"),
        Binding("a", "action_menu", "Actions"),
        Binding("f", "filter", "Fuzzy Filter"),
        Binding("h", "help", "Help"),
        Binding("j", "cursor_down", "Down"),
        Binding("k", "cursor_up", "Up"),
        Binding("J", "scroll_down", "PrevDown"),
        Binding("K", "scroll_up", "PrevUp"),
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
        super().__init__()
        self.issues = issues or []
        self.config = config or {}
        self.command = command or ""
        self.selected_issue: str | None = None
        self.jayrah_obj = boards.Boards(self.config)
        self.verbose = self.config.get("verbose", False)
        self.jql = jql
        self.order_by: str | None = order_by

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
                issue_type,
                key,
                summary,
                status,
                assignee,
                reporter,
                created,
                updated,
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

    def action_action_menu(self) -> None:  # noqa: D401
        if not self.selected_issue:
            self.notify("No issue selected", severity="error")
            return
        self.notify("Starting action menu…")
        self.exit()  # Switch back to shell for the action menu

    def action_reload(self) -> None:  # noqa: D401
        self.issues = self.jayrah_obj.issues_client.list_issues(
            self.jql, order_by=self.order_by, use_cache=False
        )
        if self.verbose:
            self.log(f"Reloaded Issues are {self.issues}")
        self.apply_fuzzy_filter("", msg="Reloading issues")

    def action_help(self) -> None:  # noqa: D401
        self.notify("Showing help…")

    def action_filter(self) -> None:  # noqa: D401
        """Open a simple filter dialog to search across all visible fields."""

        class FuzzyFilterScreen(ModalScreen):
            """Modal screen for fuzzy filtering issues."""

            BINDINGS = [
                Binding("escape", "cancel", "Cancel"),
                Binding("enter", "apply", "Apply"),
                Binding("f1", "help", "Help"),
            ]

            CSS = """
            #filter-container {
                dock: bottom;
                padding: 1;
                width: 100%;
                height: auto;
                background: $surface;
                border-top: thick $primary;
                margin: 0;
            }
            
            #filter-title {
                text-align: center;
                text-style: bold;
                width: 100%;
                height: 1;
                content-align: center middle;
            }
            
            #filter-text {
                width: 100%;
                margin: 0;
            }
            
            #filter-help {
                text-align: center;
                color: $text-muted;
                margin-top: 0;
            }
            """

            def __init__(self, parent: IssueBrowserApp):
                super().__init__()
                self._parent = parent

            def compose(self) -> ComposeResult:
                with Vertical(id="filter-container"):
                    yield Label("Filter", id="filter-title")
                    yield Input(
                        placeholder="Search in issues (fuzzy matching across all fields)",
                        id="filter-text",
                        value="",
                    )
                    yield Label(
                        "Press Enter to search, Escape to cancel", id="filter-help"
                    )

            def on_input_submitted(self, event: Input.Submitted) -> None:
                """Handle when user presses Enter in the input field."""
                self.action_apply()

            def action_apply(self) -> None:
                """Apply the fuzzy filter."""
                filter_text = self.query_one("#filter-text", Input).value
                self._parent.apply_fuzzy_filter(filter_text)
                self._parent.pop_screen()

            def action_cancel(self) -> None:
                """Cancel filtering."""
                self._parent.pop_screen()

        # Show the filter screen
        self.push_screen(FuzzyFilterScreen(self))

    def action_cursor_down(self) -> None:  # noqa: D401
        """Move cursor down in the issues table."""
        table = self.query_one("#issues-table", DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:  # noqa: D401
        """Move cursor up in the issues table."""
        table = self.query_one("#issues-table", DataTable)
        table.action_cursor_up()

    def action_scroll_down(self) -> None:  # noqa: D401
        """Scroll down the issue detail panel content."""
        detail_panel = self.query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_down()

    def action_scroll_up(self) -> None:  # noqa: D401
        """Scroll up the issue detail panel content."""
        detail_panel = self.query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_up()

    def action_page_scroll_down(self) -> None:  # noqa: D401
        """Scroll down one page in the issue detail panel content."""
        detail_panel = self.query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_page_down()

    def action_page_scroll_up(self) -> None:  # noqa: D401
        """Scroll up one page in the issue detail panel content."""
        detail_panel = self.query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_page_up()

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

    def apply_fuzzy_filter(
        self, text: str = "", msg: str = "Showing all issues"
    ) -> None:
        """Apply a fuzzy filter to all visible fields in the issues table."""
        # Reset the table
        table = self.query_one("#issues-table", DataTable)
        table.clear()

        # Add the headers back
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

        # Empty filter shows all issues
        if not text.strip():
            if msg.strip():
                self.notify(msg)
            # Re-add all rows
            for issue in self.issues:
                if self.verbose:
                    self.log(f"Adding issue {issue['key']} to table")
                self._add_issue_to_table(issue, table)
            return

        # Filter issues
        filtered_issues = []

        for issue in self.issues:
            # Prepare all searchable fields as strings
            issue_key = issue["key"].lower()
            summary = issue["fields"]["summary"].lower()

            assignee = "none"
            if assignee_field := issue["fields"].get("assignee"):
                assignee = utils.parse_email(assignee_field).lower()

            reporter = utils.parse_email(issue["fields"].get("reporter", "")).lower()
            status = issue["fields"]["status"]["name"].lower()

            # Search across all fields
            search_text = text.lower()
            if (
                search_text in issue_key
                or search_text in summary
                or search_text in assignee
                or search_text in reporter
                or search_text in status
            ):
                filtered_issues.append(issue)

        # Add filtered issues to the table
        for issue in filtered_issues:
            self._add_issue_to_table(issue, table)

        # Update UI with filter information
        if filtered_issues:
            self.notify(f"Found {len(filtered_issues)} issues matching '{text}'")
        else:
            self.notify(f"No issues match '{text}'", severity="warning")

        # Clear the selected issue if it doesn't exist in the filtered results
        if self.selected_issue:
            found = False
            for issue in filtered_issues:
                if issue["key"] == self.selected_issue:
                    found = True
                    break
            if not found:
                self.selected_issue = None
                detail_panel = self.query_one(IssueDetailPanel)
                detail_panel.update_issue(None, self.config)

    def _add_issue_to_table(self, issue: dict, table: DataTable) -> None:
        """Helper method to add an issue to the DataTable."""
        issue_type = issue["fields"]["issuetype"]["name"]
        issue_type = defaults.ISSUE_TYPE_EMOJIS.get(issue_type, (issue_type[:4],))[0]

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


### ─────────────────────────  Public helper  ──────────────────────────
def run_textual_browser(
    issues: list, config: dict, command: str, jql: str, order_by: str
):
    """Launch the **IssueBrowserApp** and return the ticket selected by the user."""
    app = IssueBrowserApp(issues, config, command, jql, order_by)
    app.run()
    return app.selected_issue
