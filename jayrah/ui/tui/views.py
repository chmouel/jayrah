"""UI views and screens for the issue browser."""

from jayrah.commands import issue_view
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Input, Label, Markdown

from .base import BaseModalScreen


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
        # Import here to avoid circular imports
        from .. import boards

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

    def update_issue(
        self, ticket: str | None, config: dict | None, use_cache: bool = True
    ) -> None:
        """
        Schedule fetching and updating the Markdown widget's content in a background worker.
        """
        self.ticket = ticket
        if config is not None:
            self.config = config
        markdown_widget = self.query_one("#detail-markdown", Markdown)
        if not ticket:
            markdown_widget.update("Select an issue to view details")
            return
        # Show loading message immediately
        markdown_widget.update(f"🔄 Loading details for {ticket}...")
        self.app.refresh()
        # Run the blocking fetch in a worker (threaded)
        self.run_worker(
            lambda: self._fetch_and_update_issue(ticket, self.config, use_cache),
            exclusive=True,
            thread=True,
        )

    def _fetch_and_update_issue(
        self, ticket: str, config: dict, use_cache: bool = True
    ) -> None:
        markdown_widget = self.query_one("#detail-markdown", Markdown)
        self.log(f"Ticket cache: {self.ticket_cache}")
        self.log(f"Use cache: {use_cache}")
        self.log(f"Ticket: {ticket}")
        try:
            all_content = ""
            if ticket not in self.ticket_cache or not use_cache:
                issue_data = self.jayrah_obj.jira.get_issue(
                    ticket, fields=None, use_cache=use_cache
                )
                header_content, markdown_content = issue_view.build_issue(
                    issue_data, config, 0
                )
                if isinstance(markdown_content, list):
                    markdown_content = "\n".join(markdown_content)
                all_content = str(header_content) + "\n" + str(markdown_content)
                self.ticket_cache[ticket] = all_content
            else:
                all_content = self.ticket_cache.get(ticket, "")
            # Update the UI in the main thread
            self.app.call_from_thread(
                lambda: self._update_markdown(markdown_widget, all_content)
            )
        except Exception as e:
            error_message = f"⚠️ Error loading issue {ticket}:\n\n```\n{str(e)}\n```\n\nPlease check the ticket ID and your connection."
            self.app.call_from_thread(
                lambda: self._update_markdown(markdown_widget, error_message)
            )
            self.app.log.error(f"Failed to load or build issue {ticket}: {e}")

    def _update_markdown(self, markdown_widget, content):
        markdown_widget.update(content)
        markdown_widget.scroll_home(animate=False, immediate=True)

    async def on_mount(self) -> None:
        """Load initial ticket details if a ticket was provided during initialization."""
        if self.ticket:
            self.update_issue(self.ticket, self.config)


class LabelsEditScreen(BaseModalScreen):
    """Modal screen for editing issue labels."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "apply", "Apply"),
        Binding("f1", "help", "Help"),
    ]

    CSS = """
    #labels-container {
        dock: bottom;
        padding: 1;
        width: 100%;
        height: auto;
        background: $surface;
        border-top: thick $primary;
        margin: 0;
    }
    
    #labels-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        height: 1;
        content-align: center middle;
    }
    
    #labels-current {
        width: 100%;
        margin: 0 0 1 0;
        text-align: center;
        color: $text-muted;
    }
    
    #labels-input {
        width: 100%;
        margin: 0;
    }
    
    #labels-help {
        text-align: center;
        color: $text-muted;
        margin-top: 0;
    }
    """

    def __init__(self, parent, issue_key: str, current_labels: list):
        super().__init__(parent)
        self.issue_key = issue_key
        self.current_labels = current_labels or []

    def compose(self) -> ComposeResult:
        current_labels_text = (
            ", ".join(self.current_labels) if self.current_labels else "No labels"
        )

        with Vertical(id="labels-container"):
            yield Label(f"Edit Labels for {self.issue_key}", id="labels-title")
            yield Label(f"Current: {current_labels_text}", id="labels-current")
            yield Input(
                placeholder="Enter labels separated by commas (e.g., bug, frontend, urgent)",
                id="labels-input",
                value=", ".join(self.current_labels),
            )
            yield Label("Press Enter to update, Escape to cancel", id="labels-help")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle when user presses Enter in the input field."""
        self.action_apply()

    def action_apply(self) -> None:
        """Apply the label changes."""
        labels_input = self.query_one("#labels-input", Input).value.strip()

        # Parse the labels from input (split by comma and strip whitespace)
        if labels_input:
            new_labels = [
                label.strip() for label in labels_input.split(",") if label.strip()
            ]
        else:
            new_labels = []

        # Update the issue with new labels
        try:
            self._parent.jayrah_obj.jira.update_issue(
                self.issue_key, {"labels": new_labels}
            )

            # Update the issue cache to reflect changes
            detail_panel = self._parent.query_one(IssueDetailPanel)
            if detail_panel.ticket == self.issue_key:
                detail_panel.update_issue(
                    self.issue_key, self._parent.config, use_cache=False
                )

            # Show success notification
            labels_text = ", ".join(new_labels) if new_labels else "No labels"
            self._parent.notify(f"✅ Labels updated: {labels_text}")

        except Exception as exc:
            self._parent.notify(f"Error updating labels: {exc}", severity="error")

        self._parent.pop_screen()


class FuzzyFilterScreen(BaseModalScreen):
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

    def compose(self) -> ComposeResult:
        with Vertical(id="filter-container"):
            yield Label("Filter", id="filter-title")
            yield Input(
                placeholder="Search in issues (fuzzy matching across all fields)",
                id="filter-text",
                value="",
            )
            yield Label("Press Enter to search, Escape to cancel", id="filter-help")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle when user presses Enter in the input field."""
        self.action_apply()

    def action_apply(self) -> None:
        """Apply the fuzzy filter."""
        filter_text = self.query_one("#filter-text", Input).value
        self._parent.apply_fuzzy_filter(filter_text)
        self._parent.pop_screen()
