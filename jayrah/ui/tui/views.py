"""UI views and screens for the issue browser."""

import re

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.suggester import SuggestFromList
from textual.widgets import Input, Label, Markdown, DataTable, TextArea

from jayrah.commands import issue_view

from .base import BaseModalScreen


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
                else:
                    # First item, just return the suggestion
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
            yield Input(
                placeholder="Enter labels separated by commas (e.g., bug, frontend, urgent)",
                id="labels-input",
                value=", ".join(self.current_labels),
                suggester=SuggestFromListComma(
                    all_labels,
                    case_sensitive=False,
                ),
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
            yield Input(
                placeholder="Enter components separated by commas (e.g., backend, frontend, api)",
                id="components-input",
                value=", ".join(self.current_components),
                suggester=SuggestFromListComma(
                    all_components,
                    case_sensitive=False,
                ),
            )
            yield Label("Press Enter to update, Escape to cancel", id="components-help")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle when user presses Enter in the input field."""
        self.action_apply()

    def action_apply(self) -> None:
        """Apply the component changes."""
        components_input = self.query_one("#components-input", Input).value.strip()

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
        self._parent.pop_screen()


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
            self._parent.pop_screen()
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
                self._parent.pop_screen()
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

        self._parent.pop_screen()


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
            self._parent.pop_screen()
            return

        try:
            if self.selected_edit_type == "title":
                # Get current issue data for title editing
                issue_data = self._parent.jayrah_obj.jira.get_issue(self.issue_key)
                current_title = issue_data.get("fields", {}).get("summary", "")

                # Close this selection screen first
                self._parent.pop_screen()

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
                self._parent.pop_screen()

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
            self._parent.notify(f"Error starting edit: {exc}", severity="error")
            self._parent.pop_screen()


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
            yield Input(
                placeholder="Enter new title/summary",
                id="title-input",
                value=self.current_title,
            )
            yield Label("Press Enter to update, Escape to cancel", id="title-help")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle when user presses Enter in the input field."""
        self.action_apply()

    def action_apply(self) -> None:
        """Apply the title changes."""
        title_input = self.query_one("#title-input", Input).value.strip()

        # Validate that title is not empty
        if not title_input:
            self._parent.notify("Title cannot be empty", severity="error")
            return

        # Check if there were changes
        if title_input == self.current_title:
            self._parent.notify("No changes made to title", severity="warning")
            self._parent.pop_screen()
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

        self._parent.pop_screen()


class DescriptionEditScreen(BaseModalScreen):
    """Modal screen for editing issue description."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "apply", "Save"),
        Binding("f1", "help", "Help"),
    ]

    CSS = """
    #description-container {
        dock: fill;
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

    def __init__(self, parent, issue_key: str, current_description: str, config: dict):
        super().__init__(parent)
        self.config = config
        self.issue_key = issue_key
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
            yield TextArea(
                text=self.current_description,
                id="description-textarea",
                language="markdown",
            )
            yield Label("Press Ctrl+S to save, Escape to cancel", id="description-help")

    def action_apply(self) -> None:
        """Apply the description changes."""
        textarea = self.query_one("#description-textarea", TextArea)
        new_description = textarea.text.strip()

        # Check if there were changes
        if new_description == self.current_description.strip():
            self._parent.notify("No changes made to description", severity="warning")
            self._parent.pop_screen()
            return

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

            # Show success notification
            self._parent.notify(f"✅ Description updated for {self.issue_key}")

        except Exception as exc:
            self._parent.notify(f"Error updating description: {exc}", severity="error")

        self._parent.pop_screen()
