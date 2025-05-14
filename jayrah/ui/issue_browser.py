from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Label, Static
from textual import on
from textual.binding import Binding
import subprocess

from .. import utils, defaults


class IssueDetailPanel(Static):
    """Panel showing detailed information about the selected issue."""

    def __init__(self, ticket=None, config=None):
        super().__init__()
        self.ticket = ticket
        self.config = config
        
    def compose(self) -> ComposeResult:
        if not self.ticket:
            yield Label("Select an issue to view details", id="no-selection")
            return
        
        yield Label(f"Loading issue {self.ticket}...", id="loading-label")
    
    def update_issue(self, ticket, config):
        """Update the panel with a new issue."""
        self.ticket = ticket
        self.config = config
        if not ticket:
            self.query_one("#loading-label").update("Select an issue to view details")
            return
        
        try:
            result = subprocess.run(
                [config.get('jayrah_path'), "issue", "view", ticket, "--no-format"],
                capture_output=True,
                text=True,
                check=False
            )
            self.query_one("#loading-label").update(result.stdout)
        except Exception as e:
            self.query_one("#loading-label").update(f"Error loading issue details: {e}")


class IssueBrowserApp(App):
    """A Textual app to browse Jira issues."""
    
    # Using inline CSS instead of external file
    CSS = """
    /* Main layout */
    #left-panel {
        width: 70%;
        height: 100%;
    }
    
    #right-panel {
        width: 30%;
        height: 100%;
        border-left: solid $primary;
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
    
    /* Set up grid widths for the table */
    #issues-table .datatable--header-cell-Type {
        width: 5;
    }
    
    #issues-table .datatable--header-cell-Key {
        width: 12;
    }
    
    #issues-table .datatable--header-cell-Summary {
        width: 40%;
    }
    
    #issues-table .datatable--header-cell-Assignee {
        width: 15;
    }
    
    #issues-table .datatable--header-cell-Reporter {
        width: 15;
    }
    
    #issues-table .datatable--header-cell-Created {
        width: 10;
    }
    
    #issues-table .datatable--header-cell-Updated {
        width: 10;
    }
    
    #issues-table .datatable--header-cell-Status {
        width: 10;
    }
    
    /* Issue detail panel */
    #loading-label {
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
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "reload", "Reload"),
        Binding("o", "open_issue", "Open in Browser"),
        Binding("a", "action_menu", "Actions"),
        Binding("f", "filter", "Filter"),
        Binding("h", "help", "Help"),
    ]
    
    def __init__(self, issues=None, config=None, command=None):
        super().__init__()
        self.issues = issues or []
        self.config = config or {}
        self.command = command
        self.selected_issue = None
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        with Container():
            with Horizontal():
                with Vertical(id="left-panel"):
                    yield Label("🔍 Jayrah - Jira Issues", id="title")
                    yield self.create_datatable()
                with Vertical(id="right-panel"):
                    yield IssueDetailPanel(config=self.config)
        yield Footer()

    def create_datatable(self):
        """Create and populate the DataTable widget."""
        table = DataTable(id="issues-table")
        table.cursor_type = "row"
        
        # Add columns
        table.add_columns(
            "Type", 
            "Key", 
            "Summary", 
            "Assignee", 
            "Reporter", 
            "Created", 
            "Updated", 
            "Status"
        )
        
        # Add rows
        for issue in self.issues:
            # Extract data from issue
            issue_type = issue["fields"]["issuetype"]["name"]
            if issue_type in defaults.ISSUE_TYPE_EMOJIS:
                issue_type = defaults.ISSUE_TYPE_EMOJIS[issue_type][0]
            else:
                issue_type = issue_type[:4]
            
            key = issue["key"]
            
            summary = issue["fields"]["summary"]
            if len(summary) > defaults.SUMMARY_MAX_LENGTH:
                summary = summary[:defaults.SUMMARY_MAX_LENGTH-3] + "…"
            
            assignee = "None"
            if issue["fields"].get("assignee"):
                assignee = utils.parse_email(issue["fields"]["assignee"])
            
            reporter = utils.parse_email(issue["fields"].get("reporter", ""))
            
            created = utils.show_time(issue["fields"].get("created", ""))
            updated = utils.show_time(issue["fields"].get("updated", ""))
            
            status = issue["fields"]["status"]["name"]
            
            table.add_row(
                issue_type,
                key,
                summary,
                assignee,
                reporter,
                created,
                updated,
                status
            )
            
        return table

    def on_mount(self) -> None:
        """Called when app is mounted."""
        self.title = "Jayrah - Jira Issues"
        
    @on(DataTable.RowSelected)
    def handle_row_selected(self, event: DataTable.RowSelected) -> None:
        """Called when a row is selected in the DataTable."""
        table = self.query_one("#issues-table")
        row = table.get_row(event.row_key)
        # Key column is index 1
        issue_key = row[1] if row and len(row) > 1 else None
        self.selected_issue = issue_key
        detail_panel = self.query_one(IssueDetailPanel)
        detail_panel.update_issue(issue_key, self.config)
    
    def action_action_menu(self) -> None:
        """Open the action menu for the selected issue."""
        if not self.selected_issue:
            self.notify("No issue selected", severity="error")
            return
        
        self.notify("Starting action menu...")
        # Exit the app temporarily to go to the action menu
        self.exit()
        subprocess.run([self.config.get('jayrah_path'), "issue", "action", self.selected_issue])
    
    def action_reload(self) -> None:
        """Reload the issue list."""
        self.notify("Reloading issues...")
        # This would normally refresh the data
        # For now we'll simulate it by just redrawing
        
    def action_help(self) -> None:
        """Show help information."""
        self.notify("Showing help...")
        # In a real implementation, this would show a help dialog
        
    def action_filter(self) -> None:
        """Show filter options."""
        self.notify("Filter functionality coming soon...")
    
    def action_open_issue(self) -> None:
        """Open the selected issue in a web browser and exit."""
        if not self.selected_issue:
            self.notify("No issue selected", severity="error")
            return
        
        try:
            utils.browser_open_ticket(self.selected_issue, self.config)
            self.notify(f"Opening {self.selected_issue} in browser")
            # Exit after opening the issue in browser
            self.exit()
        except Exception as e:
            self.notify(f"Error opening issue: {e}", severity="error")
    
    def action_quit(self) -> None:
        """Quit the application."""
        # The selected issue will be returned through app.selected_issue
        self.exit()


def run_textual_browser(issues, config, command):
    """Run the Textual UI for browsing issues.
    
    Returns:
        str or None: The selected issue key or None if no issue was selected.
    """
    app = IssueBrowserApp(issues, config, command)
    app.run()
    
    # Return the selected issue key
    return app.selected_issue
