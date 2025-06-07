"""UI views and screens for the issue browser."""

import re

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.suggester import SuggestFromList
from textual.widgets import DataTable, Label, Markdown

from ...utils import issue_view, adf
from .base import BaseModalScreen
from .enhanced_widgets import EmacsInput, EmacsTextArea


class CommentsViewScreen(BaseModalScreen):
    """Modal screen for viewing comments on an issue."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("q", "cancel", "Close"),
        Binding("f1", "help", "Help"),
        Binding("j", "scroll_down", "Scroll Down"),
        Binding("k", "scroll_up", "Scroll Up"),
        Binding("n", "next_comment", "Next Comment"),
        Binding("p", "prev_comment", "Previous Comment"),
        Binding("a", "add_comment", "Add Comment"),
    ]

    CSS = """
    #comments-container {
        dock: bottom;
        padding: 1;
        width: 100%;
        height: 80%;
        background: $surface;
        border-top: thick $primary;
        margin: 0;
    }
    
    #comments-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        height: 1;
        content-align: center middle;
    }
    
    #comments-content {
        width: 100%;
        height: 1fr;
        margin: 1 0;
        overflow: auto;
    }
    
    #comments-help {
        text-align: center;
        color: $text-muted;
        margin-top: 0;
        height: 1;
    }
    """

    def __init__(self, parent, issue_key: str, config: dict):
        super().__init__(parent)
        self.issue_key = issue_key
        self.config = config or {}
        self.comments: list = []  # Store comments data
        self.current_comment_index = 0  # Track which comment we're viewing

    def compose(self) -> ComposeResult:
        with Vertical(id="comments-container"):
            yield Label(f"💬 Comments for {self.issue_key}", id="comments-title")
            yield Markdown("Loading comments...", id="comments-content")
            yield Label("Press Escape or Q to close", id="comments-help")

    async def on_mount(self) -> None:
        """Load comments when the screen is mounted."""
        await self._load_comments()

    async def _load_comments(self) -> None:
        """Load and format comments for the issue."""
        try:
            # Get issue with comment field expanded
            issue_data = self._parent.jayrah_obj.jira.get_issue(
                self.issue_key, fields=["comment", "summary", "key"], use_cache=False
            )

            # Store comments data for navigation
            fields = issue_data.get("fields", {})
            if "comment" in fields and fields["comment"]["comments"]:
                self.comments = fields["comment"]["comments"]
            else:
                self.comments = []

            comments_content = self._format_comments(issue_data)

            # Update the markdown widget
            markdown_widget = self.query_one("#comments-content", Markdown)
            markdown_widget.update(comments_content)

            # Update help text with navigation info
            help_widget = self.query_one("#comments-help", Label)
            if self.comments:
                help_widget.update(
                    f"Press n/p to navigate comments (1/{len(self.comments)}), a to add comment, Escape or Q to close"
                )
            else:
                help_widget.update("Press a to add comment, Escape or Q to close")

        except Exception as e:
            error_message = f"Error loading comments: {str(e)}"
            markdown_widget = self.query_one("#comments-content", Markdown)
            markdown_widget.update(error_message)
            self._parent.notify(f"Failed to load comments: {e}", severity="error")

    def _format_comments(self, issue_data: dict) -> str:
        """Format comments into markdown."""
        fields = issue_data.get("fields", {})

        if "comment" not in fields or not fields["comment"]["comments"]:
            return "No comments found for this issue."

        comments = fields["comment"]["comments"]
        total = fields["comment"]["total"]

        # Build markdown content
        content = [f"# Comments for {self.issue_key}"]
        content.append(f"*Showing {len(comments)} of {total} comments*")
        content.append("")

        for i, comment in enumerate(comments):
            author = comment.get("author", {}).get("displayName", "Unknown")
            created = comment.get("created", "Unknown date")

            # Format the date if possible
            try:
                from datetime import datetime

                date_obj = datetime.strptime(created, "%Y-%m-%dT%H:%M:%S.%f%z")
                created = date_obj.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                # Keep original format if parsing fails
                pass

            # Highlight current comment
            if i == self.current_comment_index:
                content.append(f"## 👉 Comment {i + 1} - {author} [CURRENT]")
            else:
                content.append(f"## Comment {i + 1} - {author}")

            content.append(f"*{created}*")
            content.append("")

            # Convert Jira markup to markdown
            comment_body = comment.get("body", "")
            try:
                import jira2markdown

                comment_content = jira2markdown.convert(comment_body)
            except ImportError:
                # Fallback if jira2markdown is not available
                comment_content = comment_body

            content.append(comment_content)
            content.append("")
            content.append("---")
            content.append("")

        return "\n".join(content)

    def action_scroll_down(self) -> None:
        """Scroll down in the comments content."""
        markdown_widget = self.query_one("#comments-content", Markdown)
        markdown_widget.scroll_down()

    def action_scroll_up(self) -> None:
        """Scroll up in the comments content."""
        markdown_widget = self.query_one("#comments-content", Markdown)
        markdown_widget.scroll_up()

    def action_next_comment(self) -> None:
        """Navigate to the next comment."""
        if not self.comments:
            return

        # Move to next comment (wrap around to first if at the end)
        self.current_comment_index = (self.current_comment_index + 1) % len(
            self.comments
        )
        self._refresh_comments_display()

    def action_prev_comment(self) -> None:
        """Navigate to the previous comment."""
        if not self.comments:
            return

        # Move to previous comment (wrap around to last if at the beginning)
        self.current_comment_index = (self.current_comment_index - 1) % len(
            self.comments
        )
        self._refresh_comments_display()

    def _refresh_comments_display(self) -> None:
        """Refresh the comments display and scroll to current comment."""
        if not self.comments:
            return

        # Create a fake issue_data structure for _format_comments
        issue_data = {
            "fields": {
                "comment": {"comments": self.comments, "total": len(self.comments)}
            }
        }

        # Update the markdown content
        comments_content = self._format_comments(issue_data)
        markdown_widget = self.query_one("#comments-content", Markdown)
        markdown_widget.update(comments_content)

        # Update help text
        help_widget = self.query_one("#comments-help", Label)
        help_widget.update(
            f"Press n/p to navigate comments ({self.current_comment_index + 1}/{len(self.comments)}), a to add comment, Escape or Q to close"
        )

        # Scroll to the current comment section
        # We'll scroll to roughly where the current comment should be
        if len(self.comments) > 1:
            # Calculate scroll position based on comment index
            scroll_percentage = self.current_comment_index / (len(self.comments) - 1)
            # Get the total content height and scroll to the appropriate position
            markdown_widget.scroll_to(
                y=scroll_percentage * markdown_widget.max_scroll_y, animate=True
            )

    def action_add_comment(self) -> None:
        """Open modal to add a new comment to the issue."""
        self.app.push_screen(
            AddCommentScreen(
                self._parent,
                self.issue_key,
                self.config,
                on_comment_added=self._on_comment_added,
            )
        )

    async def _on_comment_added(self) -> None:
        """Callback when a new comment is added - refresh the comments display."""
        await self._load_comments()


class AddCommentScreen(BaseModalScreen):
    """Modal screen for adding a comment to an issue."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+enter", "apply", "Add Comment"),
        Binding("f1", "help", "Help"),
    ]

    CSS = """
    #comment-container {
        dock: bottom;
        padding: 1;
        width: 100%;
        height: 50%;
        background: $surface;
        border-top: thick $primary;
        margin: 0;
    }
    
    #comment-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        height: 1;
        content-align: center middle;
    }
    
    #comment-textarea {
        width: 100%;
        height: 1fr;
        margin: 1 0;
    }
    
    #comment-help {
        text-align: center;
        color: $text-muted;
        margin-top: 0;
        height: 1;
    }
    """

    def __init__(self, parent, issue_key: str, config: dict, on_comment_added=None):
        super().__init__(parent)
        self.issue_key = issue_key
        self.config = config or {}
        self.on_comment_added = on_comment_added

    def compose(self) -> ComposeResult:
        with Vertical(id="comment-container"):
            yield Label(f"✍️ Add Comment to {self.issue_key}", id="comment-title")
            yield EmacsTextArea(
                text="Enter your comment here...", id="comment-textarea"
            )
            yield Label(
                "Press Ctrl+Enter to add comment, Escape to cancel", id="comment-help"
            )

    def action_apply(self) -> None:
        """Add the comment to the issue."""
        textarea = self.query_one("#comment-textarea", EmacsTextArea)
        comment_text = textarea.text.strip()

        # Check if the text is still the placeholder text or empty
        if not comment_text or comment_text == "Enter your comment here...":
            self._parent.notify("Comment cannot be empty", severity="warning")
            return

        try:
            # Add comment using the Jira API
            self._parent.jayrah_obj.jira.client.add_comment(
                self.issue_key, comment_text
            )

            self._parent.notify(f"✅ Comment added to {self.issue_key}")

            # Call the callback to refresh comments if provided
            if self.on_comment_added:
                self.app.call_later(self.on_comment_added)

            self.action_cancel()

        except Exception as e:
            self._parent.notify(f"Failed to add comment: {e}", severity="error")


class SuggestFromListComma(SuggestFromList):
    """Give completion suggestions based on a fixed list of options with comma support.

    This suggester works with comma-separated values, providing suggestions
    for the current item being typed after the last comma.
    """

    async def get_suggestion(self, value: str) -> str | None:
        """Gets a completion from the given possibilities for comma-separated values.

        Args:
            value: The current value.

        Returns:
            A valid completion suggestion or `None`.
        """
        if not value:
            # If empty, suggest the first item
            return self._suggestions[0] if self._suggestions else None

        # Split by comma and space, then get the last part (current item being typed)
        if ", " in value:
            parts = value.split(", ")
            current_part = parts[-1]
        else:
            # Handle case where there's no comma-space yet (first item or just comma)
            parts = [value]
            current_part = value

        # If the current part is empty (user just typed a comma), suggest first item
        if not current_part:
            return self._suggestions[0] if self._suggestions else None

        # Look for suggestions that start with the current part
        current_part_for_comparison = (
            current_part if self.case_sensitive else current_part.casefold()
        )

        for idx, suggestion in enumerate(self._for_comparison):
            if suggestion.startswith(current_part_for_comparison):
                # Return the full value with the suggestion replacing the current part
                full_suggestion = self._suggestions[idx]
                # Reconstruct the full value with the suggestion
                if len(parts) > 1:
                    # Join all previous parts with the new suggestion using ", "
                    previous_parts = parts[:-1]
                    return ", ".join(previous_parts) + ", " + full_suggestion
                return full_suggestion

        return None


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

    def __init__(self, parent, issue_key: str, current_labels: list, config: dict):
        super().__init__(parent)
        self.issue_key = issue_key
        self.current_labels = current_labels or []
        self.config = config or {}

    def compose(self) -> ComposeResult:
        current_labels_text = (
            ", ".join(self.current_labels) if self.current_labels else "No labels"
        )
        all_labels = self._parent.jayrah_obj.jira.get_labels()
        if label_excludes := self.config.get("label_excludes"):
            labels_excldues_re = re.compile(label_excludes.strip())
            print(labels_excldues_re)
            all_labels = [
                label
                for label in all_labels
                if label and not labels_excldues_re.match(label)
            ]
        print(f"All labels: {all_labels}")

        with Vertical(id="labels-container"):
            yield Label(f"Edit Labels for {self.issue_key}", id="labels-title")
            yield Label(f"Current: {current_labels_text}", id="labels-current")
            yield EmacsInput(
                placeholder="Enter labels separated by commas (e.g., bug, frontend, urgent)",
                id="labels-input",
                value=", ".join(self.current_labels),
                suggester=SuggestFromListComma(
                    all_labels,
                    case_sensitive=False,
                ),
            )
            yield Label("Press Enter to update, Escape to cancel", id="labels-help")

    def on_input_submitted(self, event: EmacsInput.Submitted) -> None:
        """Handle when user presses Enter in the input field."""
        self.action_apply()

    def action_apply(self) -> None:
        """Apply the label changes."""
        labels_input = self.query_one("#labels-input", EmacsInput).value.strip()

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

        self.safe_pop_screen()


class ComponentsEditScreen(BaseModalScreen):
    """Modal screen for editing issue components."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "apply", "Apply"),
        Binding("f1", "help", "Help"),
    ]

    CSS = """
    #components-container {
        dock: bottom;
        padding: 1;
        width: 100%;
        height: auto;
        background: $surface;
        border-top: thick $primary;
        margin: 0;
    }
    
    #components-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        height: 1;
        content-align: center middle;
    }
    
    #components-current {
        width: 100%;
        margin: 0 0 1 0;
        text-align: center;
        color: $text-muted;
    }
    
    #components-input {
        width: 100%;
        margin: 0;
    }
    
    #components-help {
        text-align: center;
        color: $text-muted;
        margin-top: 0;
    }
    """

    def __init__(self, parent, issue_key: str, current_components: list, config: dict):
        super().__init__(parent)
        self.issue_key = issue_key
        self.current_components = current_components or []
        self.config = config or {}

    def compose(self) -> ComposeResult:
        current_components_text = (
            ", ".join(self.current_components)
            if self.current_components
            else "No components"
        )
        all_components = self._parent.jayrah_obj.jira.get_components()

        with Vertical(id="components-container"):
            yield Label(f"Edit Components for {self.issue_key}", id="components-title")
            yield Label(f"Current: {current_components_text}", id="components-current")
            yield EmacsInput(
                placeholder="Enter components separated by commas (e.g., backend, frontend, api)",
                id="components-input",
                value=", ".join(self.current_components),
                suggester=SuggestFromListComma(
                    all_components,
                    case_sensitive=False,
                ),
            )
            yield Label("Press Enter to update, Escape to cancel", id="components-help")

    def on_input_submitted(self, event: EmacsInput.Submitted) -> None:
        """Handle when user presses Enter in the input field."""
        self.action_apply()

    def action_apply(self) -> None:
        """Apply the component changes."""
        components_input = self.query_one("#components-input", EmacsInput).value.strip()

        # Parse the components from input (split by comma and strip whitespace)
        if components_input:
            new_components = [
                component.strip()
                for component in components_input.split(",")
                if component.strip()
            ]
        else:
            new_components = []

        # Update the issue with new components
        try:
            # Format components for Jira API
            components_data = [{"name": component} for component in new_components]
            self._parent.jayrah_obj.jira.update_issue(
                self.issue_key, {"components": components_data}
            )

            # Update the issue cache to reflect changes
            detail_panel = self._parent.query_one(IssueDetailPanel)
            if detail_panel.ticket == self.issue_key:
                detail_panel.update_issue(
                    self.issue_key, self._parent.config, use_cache=False
                )

            # Show success notification
            components_text = (
                ", ".join(new_components) if new_components else "No components"
            )
            self._parent.notify(f"✅ Components updated: {components_text}")

        except Exception as exc:
            self._parent.notify(f"Error updating components: {exc}", severity="error")

        self.safe_pop_screen()


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
            yield EmacsInput(
                placeholder="Search in issues (fuzzy matching across all fields)",
                id="filter-text",
                value="",
            )
            yield Label("Press Enter to search, Escape to cancel", id="filter-help")

    def on_input_submitted(self, event: EmacsInput.Submitted) -> None:
        """Handle when user presses Enter in the input field."""
        self.action_apply()

    def action_apply(self) -> None:
        """Apply the fuzzy filter."""
        filter_text = self.query_one("#filter-text", EmacsInput).value
        self._parent.apply_fuzzy_filter(filter_text)
        self.safe_pop_screen()


class BoardSelectionScreen(BaseModalScreen):
    """Modal screen for selecting a different board."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "apply", "Apply"),
        Binding("f1", "help", "Help"),
    ]

    CSS = """
    #board-container {
        dock: bottom;
        padding: 1;
        width: 100%;
        height: auto;
        background: $surface;
        border-top: thick $primary;
        margin: 0;
    }
    
    #board-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        height: 1;
        content-align: center middle;
    }
    
    #board-table {
        width: 100%;
        margin: 0;
        height: 10;
    }
    
    #board-help {
        text-align: center;
        color: $text-muted;
        margin-top: 0;
    }
    """

    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self.selected_board = None

    def compose(self) -> ComposeResult:
        with Vertical(id="board-container"):
            yield Label("Select Board", id="board-title")
            table = DataTable(id="board-table")
            table.cursor_type = "row"
            table.add_columns("Name", "Description")

            # Populate the table with available boards
            boards = self.config.get("boards", [])
            for board in boards:
                name = board.get("name", "")
                description = board.get("description", "No description")
                table.add_row(name, description, key=name)

            yield table
            yield Label("Press Enter to select, Escape to cancel", id="board-help")

    def on_data_table_row_selected(self, event):
        """Handle board selection."""
        self.selected_board = (
            event.row_key.value
            if hasattr(event.row_key, "value")
            else str(event.row_key)
        )
        self.action_apply()

    def action_apply(self) -> None:
        """Apply the board selection."""
        if self.selected_board:
            self._parent.change_board(self.selected_board)
        self.safe_pop_screen()


class TransitionSelectionScreen(BaseModalScreen):
    """Modal screen for selecting a transition to apply to an issue."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "apply", "Apply"),
        Binding("f1", "help", "Help"),
    ]

    CSS = """
    #transition-container {
        dock: bottom;
        padding: 1;
        width: 100%;
        height: auto;
        background: $surface;
        border-top: thick $primary;
        margin: 0;
    }
    
    #transition-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        height: 1;
        content-align: center middle;
    }
    
    #transition-table {
        width: 100%;
        margin: 0;
        height: 10;
    }
    
    #transition-help {
        text-align: center;
        color: $text-muted;
        margin-top: 0;
    }
    """

    def __init__(self, parent, issue_key: str, config: dict):
        super().__init__(parent)
        self.config = config
        self.issue_key = issue_key
        self.selected_transition_id = None

    def compose(self) -> ComposeResult:
        with Vertical(id="transition-container"):
            yield Label(
                f"Select Transition for {self.issue_key}", id="transition-title"
            )
            table = DataTable(id="transition-table")
            table.cursor_type = "row"
            table.add_columns("ID", "Name", "To Status", "Description")

            # Get available transitions for the issue
            try:
                transitions_data = self._parent.jayrah_obj.jira.get_transitions(
                    self.issue_key
                )
                transitions = transitions_data.get("transitions", [])

                if not transitions:
                    table.add_row("", "No transitions available", "", "", key="none")
                else:
                    for transition in transitions:
                        transition_id = transition["id"]
                        name = transition["name"]
                        to_status = transition["to"]["name"]
                        description = transition["to"].get(
                            "description", "No description"
                        )

                        table.add_row(
                            transition_id,
                            name,
                            to_status,
                            description,
                            key=transition_id,
                        )

            except Exception as exc:
                table.add_row(
                    "", f"Error loading transitions: {exc}", "", "", key="error"
                )

            yield table
            yield Label(
                "Press Enter to apply transition, Escape to cancel",
                id="transition-help",
            )

    def on_data_table_row_selected(self, event):
        """Handle transition selection."""
        self.selected_transition_id = (
            event.row_key.value
            if hasattr(event.row_key, "value")
            else str(event.row_key)
        )

        # Don't apply if no valid transition selected
        if self.selected_transition_id in ["none", "error"]:
            return

        self.action_apply()

    def action_apply(self) -> None:
        """Apply the selected transition."""
        if not self.selected_transition_id or self.selected_transition_id in [
            "none",
            "error",
        ]:
            self._parent.notify("No valid transition selected", severity="warning")
            self.safe_pop_screen()
            return

        try:
            # Get the transition name for display
            transitions_data = self._parent.jayrah_obj.jira.get_transitions(
                self.issue_key
            )
            transitions = transitions_data.get("transitions", [])
            selected_transition = next(
                (t for t in transitions if t["id"] == self.selected_transition_id), None
            )

            if not selected_transition:
                self._parent.notify("Invalid transition selected", severity="error")
                self.safe_pop_screen()
                return

            transition_name = selected_transition["name"]
            to_status = selected_transition["to"]["name"]

            # Apply the transition
            self._parent.jayrah_obj.jira.transition_issue(
                self.issue_key, self.selected_transition_id
            )

            # Update the issue cache to reflect changes
            detail_panel = self._parent.query_one(IssueDetailPanel)
            if detail_panel.ticket == self.issue_key:
                detail_panel.update_issue(
                    self.issue_key, self._parent.config, use_cache=False
                )

            # Reload the issues table to show updated status
            self._parent.action_reload()

            # Show success notification
            self._parent.notify(
                f"✅ Issue {self.issue_key} transitioned to '{to_status}' via '{transition_name}'"
            )

        except Exception as exc:
            self._parent.notify(f"Error applying transition: {exc}", severity="error")

        self.safe_pop_screen()


class EditSelectionScreen(BaseModalScreen):
    """Modal screen for selecting what to edit (title or description)."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "apply", "Apply"),
        Binding("f1", "help", "Help"),
    ]

    CSS = """
    #edit-container {
        dock: bottom;
        padding: 1;
        width: 100%;
        height: auto;
        background: $surface;
        border-top: thick $primary;
        margin: 0;
    }
    
    #edit-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        height: 1;
        content-align: center middle;
    }
    
    #edit-table {
        width: 100%;
        margin: 0;
        height: 5;
    }
    
    #edit-help {
        text-align: center;
        color: $text-muted;
        margin-top: 0;
    }
    """

    def __init__(self, parent, issue_key: str, config: dict):
        super().__init__(parent)
        self.config = config
        self.issue_key = issue_key
        self.selected_edit_type = None
        self.verbose = self.config.get("verbose", False)

    def compose(self) -> ComposeResult:
        with Vertical(id="edit-container"):
            yield Label(f"Edit Issue {self.issue_key}", id="edit-title")
            table = DataTable(id="edit-table")
            table.cursor_type = "row"
            table.add_columns("Action", "Description")

            # Add edit options
            table.add_row("title", "Edit issue title/summary", key="title")
            table.add_row("description", "Edit issue description", key="description")

            yield table
            yield Label(
                "Press Enter to select edit type, Escape to cancel", id="edit-help"
            )

    def on_data_table_row_selected(self, event):
        """Handle edit type selection."""
        self.selected_edit_type = (
            event.row_key.value
            if hasattr(event.row_key, "value")
            else str(event.row_key)
        )
        self.action_apply()

    def action_apply(self) -> None:
        """Apply the edit selection."""
        if not self.selected_edit_type:
            self._parent.notify("No edit type selected", severity="warning")
            self.safe_pop_screen()
            return

        try:
            if self.selected_edit_type == "title":
                # Get current issue data for title editing
                issue_data = self._parent.jayrah_obj.jira.get_issue(self.issue_key)
                current_title = issue_data.get("fields", {}).get("summary", "")

                # Close this selection screen first
                self.safe_pop_screen()

                # Show the title edit screen
                self._parent.push_screen(
                    TitleEditScreen(
                        self._parent,
                        self.issue_key,
                        current_title,
                        self.config,
                    )
                )
            elif self.selected_edit_type == "description":
                # Get current issue data for description editing
                issue_data = self._parent.jayrah_obj.jira.get_issue(self.issue_key)
                current_description = issue_data.get("fields", {}).get(
                    "description", ""
                )
                # Close this selection screen first
                self.safe_pop_screen()

                # Show the description edit screen
                self._parent.push_screen(
                    DescriptionEditScreen(
                        self._parent,
                        self.issue_key,
                        current_description,
                        self.config,
                    )
                )

        except Exception as exc:
            if self.verbose:
                raise exc
            self._parent.notify(
                f"Error starting edit please try again. {exc} ", severity="error"
            )
            self.safe_pop_screen()


class TitleEditScreen(BaseModalScreen):
    """Modal screen for editing issue title/summary."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "apply", "Apply"),
        Binding("f1", "help", "Help"),
    ]

    CSS = """
    #title-container {
        dock: bottom;
        padding: 1;
        width: 100%;
        height: auto;
        background: $surface;
        border-top: thick $primary;
        margin: 0;
    }
    
    #title-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        height: 1;
        content-align: center middle;
    }
    
    #title-current {
        width: 100%;
        margin: 0 0 1 0;
        text-align: center;
        color: $text-muted;
    }
    
    #title-input {
        width: 100%;
        margin: 0;
    }
    
    #title-help {
        text-align: center;
        color: $text-muted;
        margin-top: 0;
    }
    """

    def __init__(self, parent, issue_key: str, current_title: str, config: dict):
        super().__init__(parent)
        self.config = config
        self.issue_key = issue_key
        self.current_title = current_title

    def compose(self) -> ComposeResult:
        with Vertical(id="title-container"):
            yield Label(f"Edit Title for {self.issue_key}", id="title-title")
            yield Label(
                f"Current: {self.current_title[:60] + '...' if len(self.current_title) > 60 else self.current_title}",
                id="title-current",
            )
            yield EmacsInput(
                placeholder="Enter new title/summary",
                id="title-input",
                value=self.current_title,
            )
            yield Label("Press Enter to update, Escape to cancel", id="title-help")

    def on_input_submitted(self, event: EmacsInput.Submitted) -> None:
        """Handle when user presses Enter in the input field."""
        self.action_apply()

    def action_apply(self) -> None:
        """Apply the title changes."""
        title_input = self.query_one("#title-input", EmacsInput).value.strip()

        # Validate that title is not empty
        if not title_input:
            self._parent.notify("Title cannot be empty", severity="error")
            return

        # Check if there were changes
        if title_input == self.current_title:
            self._parent.notify("No changes made to title", severity="warning")
            self.safe_pop_screen()
            return

        # Update the issue with new title
        try:
            self._parent.jayrah_obj.jira.update_issue(
                self.issue_key, {"summary": title_input}
            )

            # Update the issue cache to reflect changes
            detail_panel = self._parent.query_one(IssueDetailPanel)
            if detail_panel.ticket == self.issue_key:
                detail_panel.update_issue(
                    self.issue_key, self._parent.config, use_cache=False
                )

            # Reload the issues table to show updated title
            self._parent.action_reload()

            # Show success notification
            self._parent.notify(f"✅ Title updated for {self.issue_key}")

        except Exception as exc:
            self._parent.notify(f"Error updating title: {exc}", severity="error")

        self.safe_pop_screen()


class DescriptionEditScreen(BaseModalScreen):
    """Modal screen for editing issue description."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "apply", "Save"),
        Binding("f1", "help", "Help"),
    ]

    CSS = """
    #description-container {
        dock: bottom;
        padding: 1;
        width: 100%;
        height: 100%;
        background: $surface;
        border: thick $primary;
        margin: 0;
    }
    
    #description-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        height: 1;
        content-align: center middle;
    }
    
    #description-current {
        width: 100%;
        margin: 0 0 1 0;
        text-align: center;
        color: $text-muted;
    }
    
    #description-textarea {
        width: 100%;
        height: 1fr;
        margin: 1 0;
    }
    
    #description-help {
        text-align: center;
        color: $text-muted;
        margin-top: 0;
    }
    """

    def __init__(self, parent, issue_key: str, current_description, config: dict):
        super().__init__(parent)
        self.config = config
        self.issue_key = issue_key
        self.verbose = self.config.get("verbose", False)

        # Store original description (could be str or dict for ADF)
        self.original_description = current_description

        # Convert to string if it's a JSON object (ADF format)
        self.is_adf_format = False
        if current_description and isinstance(current_description, dict):
            from ...utils.adf import extract_text_from_adf

            self.is_adf_format = True
            self.current_description = extract_text_from_adf(current_description)
        else:
            self.current_description = current_description or ""

    def compose(self) -> ComposeResult:
        with Vertical(id="description-container"):
            yield Label(
                f"Edit Description for {self.issue_key}", id="description-title"
            )
            yield Label(
                f"Current: {len(self.current_description)} characters",
                id="description-current",
            )

            if self.verbose:
                with open("/tmp/debug.log", "w") as f:
                    f.write(f"{__import__('pprint').pformat(self.current_description)}")

            yield EmacsTextArea(
                text=self.current_description,
                id="description-textarea",
                language="markdown",
            )

            if self.is_adf_format:
                help_text = (
                    "Press Ctrl+S to save, Escape to cancel (ADF format detected)"
                )
            else:
                help_text = "Press Ctrl+S to save, Escape to cancel"

            yield Label(help_text, id="description-help")

    def action_apply(self) -> None:
        """Apply the description changes."""
        # If the screen is unmounted by another action (e.g., quick Escape press)
        # before this method completes, we should not proceed.
        if not self.is_mounted:
            return

        textarea = self.query_one("#description-textarea", EmacsTextArea)
        new_description_text = textarea.text.strip()

        # Check if there were changes to plain text
        if new_description_text == self.current_description.strip():
            self._parent.notify("No changes made to description", severity="warning")
            self.safe_pop_screen()
            return

        # If original was ADF format, convert edited text back to ADF
        if self.is_adf_format:
            new_description = adf.create_adf_from_text(new_description_text)
            if self.verbose:
                with open("/tmp/debug_save.log", "w") as f:
                    f.write(f"New text: {new_description_text}\n")
                    f.write(
                        f"New ADF: {__import__('json').dumps(new_description, indent=2)}"
                    )
        else:
            new_description = new_description_text

        # Update the issue with new description
        try:
            self._parent.jayrah_obj.jira.update_issue(
                self.issue_key, {"description": new_description}
            )

            # Update the issue cache to reflect changes
            detail_panel = self._parent.query_one(IssueDetailPanel)
            if detail_panel.ticket == self.issue_key:
                detail_panel.update_issue(
                    self.issue_key, self._parent.config, use_cache=False
                )

            self._parent.notify(f"✅ Description updated for {self.issue_key}")
            self.safe_pop_screen()

        except Exception as exc:
            self._parent.notify(f"Error updating description: {exc}", severity="error")
            # Do not pop the screen on error, allow user to see the message and manually cancel.


class ActionsPanel(BaseModalScreen):
    """Modal screen for displaying all available actions."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "apply", "Apply"),
        Binding("l", "select_labels", "Labels"),
        Binding("ctrl+c", "select_components", "Components"),
        Binding("c", "select_comments", "Comments"),
        Binding("t", "select_transition", "Transition"),
        Binding("e", "select_edit", "Edit"),
        Binding("f", "select_filter", "Filter"),
        Binding("b", "select_board", "Board"),
        Binding("f1", "help", "Help"),
    ]

    CSS = """
    #actions-container {
        dock: bottom;
        padding: 1;
        width: 100%;
        height: auto;
        background: $surface;
        border-top: thick $primary;
        margin: 0;
    }
    
    #actions-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        height: 1;
        content-align: center middle;
    }
    
    #actions-table {
        width: 100%;
        margin: 0;
        height: 10;
    }
    
    #actions-help {
        text-align: center;
        color: $text-muted;
        margin-top: 0;
    }
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.selected_action = None

    def compose(self) -> ComposeResult:
        with Vertical(id="actions-container"):
            yield Label("Available Actions", id="actions-title")
            table = DataTable(id="actions-table")
            table.cursor_type = "row"
            table.add_columns("Key", "Action", "Description")

            # Add action options with keybindings
            table.add_row(
                "l",
                "Labels",
                "Add/edit labels for the selected issue",
                key="add_labels",
            )
            table.add_row(
                "Ctrl+C",
                "Components",
                "Edit components for the selected issue",
                key="edit_components",
            )
            table.add_row(
                "c",
                "Comments",
                "View comments for the selected issue",
                key="view_comments",
            )
            table.add_row(
                "t",
                "Transition",
                "Change status of the selected issue",
                key="transition_issue",
            )
            table.add_row(
                "e",
                "Edit",
                "Edit title or description of the selected issue",
                key="edit_issue",
            )
            table.add_row(
                "f", "Filter", "Apply fuzzy filter to search issues", key="filter"
            )
            table.add_row(
                "b", "Board", "Switch to a different board", key="change_board"
            )

            yield table
            yield Label(
                "Press Enter to select action or use the key directly, Escape to cancel",
                id="actions-help",
            )

    def on_data_table_row_selected(self, event):
        """Handle action selection."""
        self.selected_action = (
            event.row_key.value
            if hasattr(event.row_key, "value")
            else str(event.row_key)
        )
        self.action_apply()

    def action_apply(self) -> None:
        """Apply the selected action."""
        if not self.selected_action:
            self._parent.notify("No action selected", severity="warning")
            self.safe_pop_screen()
            return

        # Close this panel first
        self.safe_pop_screen()

        # Execute the corresponding action
        if self.selected_action == "add_labels":
            self._parent.action_add_labels()
        elif self.selected_action == "edit_components":
            self._parent.action_edit_components()
        elif self.selected_action == "view_comments":
            self._parent.action_view_comments()
        elif self.selected_action == "transition_issue":
            self._parent.action_transition_issue()
        elif self.selected_action == "edit_issue":
            self._parent.action_edit_issue()
        elif self.selected_action == "filter":
            self._parent.action_filter()
        elif self.selected_action == "change_board":
            self._parent.action_change_board()

    def action_select_labels(self) -> None:
        """Shortcut to select labels action."""
        self.selected_action = "add_labels"
        self.action_apply()

    def action_select_components(self) -> None:
        """Shortcut to select components action."""
        self.selected_action = "edit_components"
        self.action_apply()

    def action_select_comments(self) -> None:
        """Shortcut to select comments action."""
        self.selected_action = "view_comments"
        self.action_apply()

    def action_select_transition(self) -> None:
        """Shortcut to select transition action."""
        self.selected_action = "transition_issue"
        self.action_apply()

    def action_select_edit(self) -> None:
        """Shortcut to select edit action."""
        self.selected_action = "edit_issue"
        self.action_apply()

    def action_select_filter(self) -> None:
        """Shortcut to select filter action."""
        self.selected_action = "filter"
        self.action_apply()

    def action_select_board(self) -> None:
        """Shortcut to select board action."""
        self.selected_action = "change_board"
        self.action_apply()
