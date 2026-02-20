# pylint: disable=no-member
"""Action handlers for the issue browser application."""

from __future__ import annotations

from typing import Any, cast

from jayrah import utils

from .views import (
    ActionsPanel,
    BoardSelectionScreen,
    CommentsViewScreen,
    ComponentsEditScreen,
    EditSelectionScreen,
    FuzzyFilterScreen,
    IssueDetailPanel,
    LabelsEditScreen,
    TransitionSelectionScreen,
)


# pylint: disable=too-many-public-methods
class IssueBrowserActions:
    """
    Mixin class containing all action handlers for the issue browser.

    This class should be mixed with a Textual App that has the following attributes:
    - notify, run_worker, push_screen, query_one, exit, log, app (from Textual App)
    - selected_issue, jayrah_obj, config, verbose, jql, order_by, issues (app-specific)
    - apply_fuzzy_filter method
    """

    command: str = ""  # Default command for this app
    jql: str = ""  # JQL query for fetching issues
    order_by: str = ""  # Order by clause for fetching issues
    issues: list = []  # List of issues fetched from JIRA
    selected_issue: str | None = None  # Currently selected issue

    def action_reload(self) -> None:
        """Reload issues asynchronously with loading state."""
        # Show loading state
        cast(Any, self).notify("🔄 Reloading issues...")

        # Run the reload in a worker thread
        # pylint: disable=unnecessary-lambda
        cast(Any, self).run_worker(
            lambda: self._reload_issues(),
            exclusive=True,
            thread=True,
        )

    def action_add_labels(self) -> None:
        """Open modal to edit labels for the selected issue."""
        if not cast(Any, self).selected_issue:
            cast(Any, self).notify("No issue selected", severity="warning")
            return

        # Get the current issue data to retrieve existing labels
        try:
            issue_data = cast(Any, self).jayrah_obj.jira.get_issue(
                cast(Any, self).selected_issue
            )
            current_labels = issue_data.get("fields", {}).get("labels", [])

            # Show the labels edit screen
            cast(Any, self).push_screen(
                LabelsEditScreen(
                    self,
                    cast(Any, self).selected_issue,
                    current_labels,
                    cast(Any, self).config,
                )
            )
        except Exception as exc:
            cast(Any, self).notify(f"Error loading issue data: {exc}", severity="error")

    def action_edit_components(self) -> None:
        """Open modal to edit components for the selected issue."""
        if not cast(Any, self).selected_issue:
            cast(Any, self).notify("No issue selected", severity="warning")
            return

        # Get the current issue data to retrieve existing components
        try:
            issue_data = cast(Any, self).jayrah_obj.jira.get_issue(
                cast(Any, self).selected_issue
            )
            current_components_data = issue_data.get("fields", {}).get("components", [])
            current_components = [
                comp.get("name", "") for comp in current_components_data
            ]

            # Show the components edit screen
            cast(Any, self).push_screen(
                ComponentsEditScreen(
                    self,
                    cast(Any, self).selected_issue,
                    current_components,
                    cast(Any, self).config,
                )
            )
        except Exception as exc:
            cast(Any, self).notify(f"Error loading issue data: {exc}", severity="error")

    def action_transition_issue(self) -> None:
        """Open modal to transition the selected issue to a new status."""
        if not cast(Any, self).selected_issue:
            cast(Any, self).notify("No issue selected", severity="warning")
            return

        # Show the transition selection screen
        try:
            cast(Any, self).push_screen(
                TransitionSelectionScreen(
                    self,
                    cast(Any, self).selected_issue,
                    cast(Any, self).config,
                )
            )
        except Exception as exc:
            cast(Any, self).notify(
                f"Error loading transitions: {exc}", severity="error"
            )

    def action_edit_issue(self) -> None:
        """Open modal to edit the selected issue (title or description)."""
        if not cast(Any, self).selected_issue:
            cast(Any, self).notify("No issue selected", severity="warning")
            return

        # Show the edit selection screen
        try:
            cast(Any, self).push_screen(
                EditSelectionScreen(
                    self,
                    cast(Any, self).selected_issue,
                    cast(Any, self).config,
                )
            )
        except Exception as exc:
            cast(Any, self).notify(
                f"Error opening edit dialog: {exc}", severity="error"
            )

    def action_view_comments(self) -> None:
        """Open modal to view comments for the selected issue."""
        if not cast(Any, self).selected_issue:
            cast(Any, self).notify("No issue selected", severity="warning")
            return

        # Show the comments view screen
        try:
            cast(Any, self).push_screen(
                CommentsViewScreen(
                    self,
                    cast(Any, self).selected_issue,
                    cast(Any, self).config,
                )
            )
        except Exception as exc:
            cast(Any, self).notify(f"Error loading comments: {exc}", severity="error")

    def action_filter(self) -> None:
        """Open a simple filter dialog to search across all visible fields."""
        # Show the filter screen
        cast(Any, self).push_screen(FuzzyFilterScreen(self))

    def action_change_board(self) -> None:
        """Open modal to select a different board."""
        # Show the board selection screen
        cast(Any, self).push_screen(BoardSelectionScreen(self, cast(Any, self).config))

    def action_show_actions(self) -> None:
        """Show a panel with all available actions."""
        # Show the actions panel
        cast(Any, self).push_screen(ActionsPanel(self))

    def action_cursor_down(self) -> None:
        """Move cursor down in the issues table."""
        table = cast(Any, self).query_one("#issues-table")
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up in the issues table."""
        table = cast(Any, self).query_one("#issues-table")
        table.action_cursor_up()

    def action_scroll_down(self) -> None:
        """Scroll down the issue detail panel content."""
        detail_panel = cast(Any, self).query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_down()

    def action_scroll_up(self) -> None:
        """Scroll up the issue detail panel content."""
        detail_panel = cast(Any, self).query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_up()

    def action_page_scroll_down(self) -> None:
        """Scroll down one page in the issue detail panel content."""
        detail_panel = cast(Any, self).query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_page_down()

    def action_page_scroll_up(self) -> None:
        """Scroll up one page in the issue detail panel content."""
        detail_panel = cast(Any, self).query_one(IssueDetailPanel)
        markdown_widget = detail_panel.query_one("#detail-markdown")
        markdown_widget.scroll_page_up()

    def action_open_issue(self) -> None:
        """Open the selected issue in the browser."""
        if not cast(Any, self).selected_issue:
            cast(Any, self).notify("No issue selected", severity="error")
            return
        try:
            utils.browser_open_ticket(
                cast(Any, self).selected_issue, cast(Any, self).config
            )
            cast(Any, self).notify(
                f"Opening {cast(Any, self).selected_issue} in browser"
            )
        except Exception as exc:
            cast(Any, self).notify(f"Error opening issue: {exc}", severity="error")

    def action_copy_url(self) -> None:
        """Copy the URL of the selected issue to clipboard."""
        if not cast(Any, self).selected_issue:
            cast(Any, self).notify("No issue selected", severity="error")
            return

        try:
            from jayrah.utils.clipboard import copy_to_clipboard, get_clipboard_command

            # Get the Jira server URL from config
            server = cast(Any, self).config.get("jira_server")
            if not server:
                cast(Any, self).notify("Jira server not configured", severity="error")
                return

            # Construct the full URL
            url = utils.make_full_url(cast(Any, self).selected_issue, server)

            # Check if clipboard is available for the platform
            clipboard_cmd = get_clipboard_command()
            if not clipboard_cmd:
                cast(Any, self).notify(
                    "Clipboard not supported on this platform",
                    severity="warning",
                )
                return

            # Copy to clipboard
            if copy_to_clipboard(url):
                cast(Any, self).notify(
                    f"✅ Copied URL to clipboard: {cast(Any, self).selected_issue}"
                )
            else:
                cast(Any, self).notify(
                    f"Failed to copy URL (clipboard command: {clipboard_cmd})",
                    severity="error",
                )

        except Exception as exc:
            cast(Any, self).notify(f"Error copying URL: {exc}", severity="error")

    def action_confirm_selection(self) -> None:
        """Confirm the currently highlighted issue when auto choose is enabled."""
        if not getattr(self, "auto_choose", False):
            self.action_open_issue()
            return

        if not cast(Any, self).selected_issue:
            cast(Any, self).notify("No issue selected", severity="warning")
            return

        cast(Any, self).exit(cast(Any, self).selected_issue)

    def action_quit(self) -> None:
        """Quit the application."""
        cast(Any, self).exit()  # *app.selected_issue* persists after exit

    def action_help(self) -> None:
        """Show the help panel with key bindings."""
        from textual.css.query import NoMatches
        from textual.widgets import HelpPanel

        try:
            help_panel = cast(Any, self).query_one(HelpPanel)
            print(dir(help_panel))
            if help_panel.is_on_screen:
                cast(Any, self).query_one(HelpPanel).remove()
        except NoMatches:
            cast(Any, self).mount(HelpPanel())

    def change_board(self, board_name: str) -> None:
        """Change to a different board and reload issues."""
        cast(Any, self).notify(f"🔄 Switching to board: {board_name}...")

        # Run the board change in a worker thread
        cast(Any, self).run_worker(
            lambda: self._change_board_worker(board_name),
            exclusive=True,
            thread=True,
        )

    def _change_board_worker(self, board_name: str) -> None:
        """Worker method to change board and reload issues."""
        try:
            # Import here to avoid circular imports
            from jayrah.ui import boards

            # Get the new board's JQL and order_by
            jql, order_by = boards.check(board_name, cast(Any, self).config)
            if not jql or not order_by:
                cast(Any, self).app.call_from_thread(
                    lambda: cast(Any, self).notify(
                        f"Error: Invalid board or missing JQL: {board_name}",
                        severity="error",
                    )
                )
                return

            # Update the command for this app instance
            cast(Any, self).command = board_name
            cast(Any, self).jql = jql
            cast(Any, self).order_by = order_by

            # Clear cache and fetch new issues
            cast(Any, self).jayrah_obj.jira.cache.clear()
            new_issues = cast(Any, self).jayrah_obj.issues_client.list_issues(
                jql, order_by=order_by, use_cache=False
            )

            # Update the UI in the main thread
            cast(Any, self).app.call_from_thread(
                lambda: self._update_issues_after_board_change(new_issues, board_name)
            )
        except Exception as e:
            err = str(e)
            cast(Any, self).app.call_from_thread(
                lambda err=err: cast(Any, self).notify(
                    f"Error changing board: {err}", severity="error"
                )
            )

    def _update_issues_after_board_change(
        self, new_issues: list, board_name: str
    ) -> None:
        """Update the UI after changing boards."""
        if cast(Any, self).verbose:
            cast(Any, self).log(
                f"Board changed to {board_name}. New issues: {len(new_issues)}"
            )

        cast(Any, self).issues = new_issues
        cast(Any, self).apply_fuzzy_filter("", msg=f"Switched to board: {board_name}")

        # Clear the detail panel
        detail_panel = cast(Any, self).query_one(IssueDetailPanel)
        detail_panel.ticket_cache = {}
        detail_panel.update_issue(None, cast(Any, self).config)
        cast(Any, self).selected_issue = None

        cast(Any, self).notify(
            f"✅ Switched to board: {board_name} ({len(new_issues)} issues)"
        )

    def _reload_issues(self) -> None:
        """Worker method to reload issues."""
        try:
            # Clear cache and fetch new issues
            cast(Any, self).jayrah_obj.jira.cache.clear()
            new_issues = cast(Any, self).jayrah_obj.issues_client.list_issues(
                cast(Any, self).jql, order_by=cast(Any, self).order_by, use_cache=False
            )

            # Update the UI in the main thread
            cast(Any, self).app.call_from_thread(
                lambda: self._update_issues_after_reload(new_issues)
            )
        except Exception as e:
            err = str(e)
            cast(Any, self).app.call_from_thread(
                lambda err=err: cast(Any, self).notify(
                    f"Error reloading issues: {err}", severity="error"
                )
            )

    def _update_issues_after_reload(self, new_issues: list) -> None:
        """Update the UI after reloading issues."""
        if cast(Any, self).verbose:
            cast(Any, self).log(f"Reloaded Issues are {new_issues}")

        cast(Any, self).issues = new_issues
        cast(Any, self).apply_fuzzy_filter(
            "", msg="Reloading issues and clearing cache"
        )

        detail_panel = cast(Any, self).query_one(IssueDetailPanel)
        detail_panel.ticket_cache = {}
        detail_panel.update_issue(
            detail_panel.ticket, cast(Any, self).config, use_cache=False
        )

        cast(Any, self).notify("✅ Issues reloaded successfully")
